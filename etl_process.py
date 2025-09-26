
import pandas as pd
import streamlit as st
from db_connection import get_connection, get_dwh_connection
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta


@st.cache_data(ttl=3600)
def load_dm_order():
    print("--- [ETL] Membaca dari DATAMART: public.dm_dashboard_master ---")
    try:
        with get_connection() as conn:
            df_order= pd.read_sql("SELECT * FROM public.dm_order;", conn)
            
            if df_order.empty:
                st.error("Tabel Datamart (dm_order) kosong. Jalankan workflow n8n terlebih dahulu.")
                return pd.DataFrame()

            df_order['order_date'] = pd.to_datetime(df_order['order_date'])
            
            numeric_cols = [
                'gmv_order', 'cogs_order', 'gross_revenue_order', 'quantity_sold', 
                'revenue_product', 'cogs_product', 'gross_profit_product'
            ]
            for col in numeric_cols:
                if col in df_order.columns:
                    df_order[col] = pd.to_numeric(df_order[col], errors='coerce').fillna(0)
            
            print(f"Berhasil mengambil {len(df_order)} baris dari dm_order.")
            return df_order
    except Exception as e:
        st.error(f"Gagal total memuat data dari DATAMART: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def load_dm_outlet():
    print("--- [ETL] Membaca dari DATAMART: public.dm_outlet ---")
    try:
        with get_connection() as conn:
            df_outlet = pd.read_sql("SELECT * FROM public.dm_outlet;", conn)
            
            if df_outlet.empty:
                st.error("Tabel Datamart (dm_order) kosong. Jalankan workflow n8n terlebih dahulu.")
                return pd.DataFrame()

            df_outlet['go_live'] = pd.to_datetime(df_outlet['go_live'])
            
            print(f"Berhasil mengambil {len(df_outlet)} baris dari dm_order.")
            return df_outlet
    except Exception as e:
        st.error(f"Gagal total memuat data dari DATAMART: {e}")
        return pd.DataFrame()

@st.cache_data
def get_outlet_performance_metrics_v2(start_date, end_date):
    print("\n--- [ETL-KHUSUS] Menghitung metrik outlet dari dwh-2 ---")
    metrics = {'activation_rate': None, 'retention_rate': None, 'avg_activation_time_days': None}
    
    if not start_date or not end_date:
        return metrics

    delta = (end_date - start_date).days
    prev_end_date = start_date - timedelta(days=1)
    prev_start_date = prev_end_date - timedelta(days=delta)

    query = """
    WITH
    -- 1. Tentukan tanggal sinkronisasi pertama untuk setiap outlet
    outlet_first_sync AS (
        SELECT 
            outlet_id, 
            MIN(created_at) AS first_sync_date 
        FROM public.raw_sfwc_menu_sync_logs
        GROUP BY outlet_id
    ),
    
    -- 2. Tentukan outlet yang aktif (pernah sync) di periode saat ini dan sebelumnya
    current_active AS (
        SELECT DISTINCT outlet_id 
        FROM public.raw_sfwc_menu_sync_logs
        WHERE created_at >= %(start_date)s AND created_at <= %(end_date)s
    ),
    previous_active AS (
        SELECT DISTINCT outlet_id 
        FROM outlet_first_sync 
        WHERE first_sync_date >= %(prev_start_date)s AND first_sync_date <= %(prev_end_date)s
    ),
    
    -- 3. Tentukan outlet yang baru diaktifkan di periode ini (first sync-nya ada di periode ini)
    newly_activated AS (
        SELECT outlet_id 
        FROM outlet_first_sync 
        WHERE first_sync_date >= %(start_date)s AND first_sync_date <= %(end_date)s
    ),
    
    -- 4. Tentukan outlet yang diverifikasi
    -- Asumsi: Outlet verifikasi adalah outlet_id di `raw_sfwc_outlet_owners`
    total_verified AS (
        SELECT COUNT(DISTINCT oo.outlet_id) AS count
        FROM public.raw_sfwc_outlet_owners oo
        LEFT JOIN outlet_first_sync fs ON oo.outlet_id = fs.outlet_id
        WHERE fs.outlet_id IS NULL 
    ),
    
    -- 5. Tentukan outlet yang churn sebelum aktif (deleted_at sebelum first_sync_date)
    churn_before_activation AS (
        SELECT COUNT(DISTINCT oo.outlet_id) AS count
        FROM public.raw_sfwc_outlet_owners oo -- Berganti ke outlet_owners
        LEFT JOIN public.raw_sfwc_users u ON oo.owner_id = u.id -- Asumsi relasi
        LEFT JOIN outlet_first_sync fs ON oo.outlet_id = fs.outlet_id
        WHERE u.deleted_at IS NOT NULL AND u.deleted_at < fs.first_sync_date
    )
    
    SELECT
    -- Retention Rate: (Outlet aktif di kedua periode) / (Outlet aktif di periode sebelumnya)
    (SELECT COUNT(*) FROM newly_activated)::FLOAT/ NULLIF((SELECT COUNT(*) FROM previous_active)::FLOAT, 0) AS retention_rate,
    
    -- Activation Rate: (Jumlah outlet yang baru diaktifkan) / (Jumlah outlet yang diverifikasi - churn sebelum aktif)
    (SELECT COUNT(DISTINCT outlet_id) FROM newly_activated)::FLOAT / NULLIF(((SELECT count FROM total_verified) - (SELECT count FROM churn_before_activation))::FLOAT, 0) AS activation_rate
    """
    
    params = {'start_date': start_date, 'end_date': end_date, 'prev_start_date': prev_start_date, 'prev_end_date': prev_end_date}

    try:
        with get_dwh_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            result = cur.fetchone()
            if result:
                metrics['retention_rate'], metrics['activation_rate'] = result
            cur.close()
    except Exception as e:
        print(f"ERROR saat menghitung metrik outlet: {e}")
        st.error(f"Error: Gagal mengambil data metrik outlet. Pesan: {e}")
    
    # Untuk avg_activation_time, kita masih perlu query terpisah atau gabungkan.
    # Karena definisi Anda fokus pada sync, kita bisa pakai `first_sync_date`
    avg_act_time_query = """
    WITH 
    outlet_first_sync AS (
        SELECT 
            outlet_id, 
            MIN(created_at) AS first_sync_date 
        FROM public.raw_sfwc_menu_sync_logs
        GROUP BY outlet_id
    )
    SELECT AVG(EXTRACT(EPOCH FROM (fs.first_sync_date - oo.created_at))) / 86400.0 AS avg_activation_days
    FROM outlet_first_sync fs
    JOIN public.raw_sfwc_outlet_owners oo ON fs.outlet_id = oo.outlet_id
    WHERE fs.first_sync_date >= %(start_date)s AND fs.first_sync_date <= %(end_date)s
    """
    try:
        with get_dwh_connection() as conn:
            cur = conn.cursor()
            cur.execute(avg_act_time_query, params)
            avg_time_result = cur.fetchone()
            if avg_time_result:
                metrics['avg_activation_time_days'] = avg_time_result[0]
            cur.close()
    except Exception as e:
        print(f"ERROR saat menghitung rata-rata waktu aktivasi: {e}")
        st.error(f"Error: Gagal mengambil data rata-rata waktu aktivasi. Pesan: {e}")

    return metrics


@st.cache_data
def get_outlet_metrics_trend(start_date, end_date, granularity='daily'):
    print(f"\n--- [ETL] Menghitung tren metrik outlet per {granularity} ---")
    
    if not start_date or not end_date:
        return pd.DataFrame()

    try:
        with get_dwh_connection() as conn:
            query_churn = """
            SELECT
                id AS user_id,
                deleted_at
            FROM public.raw_sfwc_users
            WHERE deleted_at::date BETWEEN %(start_date)s AND %(end_date)s;
            """
            df_churn = pd.read_sql(query_churn, conn, params={'start_date': start_date, 'end_date': end_date})
            
            query_orders = """
            SELECT
                date_created_gmt,
                outlet_id
            FROM public.raw_sfwc_orders
            WHERE status IN ('wc-completed','wc-disbursement-completed', 'wc-disbursement-proress')
            AND date_created_gmt::date BETWEEN %(start_date)s AND %(end_date)s;
            """
            df_orders = pd.read_sql(query_orders, conn, params={'start_date': start_date, 'end_date': end_date})
            
    except Exception as e:
        st.error(f"Error: Gagal mengambil data mentah. Pesan: {e}")
        return pd.DataFrame()

    df_churn['deleted_at'] = pd.to_datetime(df_churn['deleted_at'])
    df_orders['date_created_gmt'] = pd.to_datetime(df_orders['date_created_gmt'])
    
    if granularity == 'daily':
        period_range = pd.date_range(start=start_date, end=end_date, freq='D')
    else: 
        period_range = pd.period_range(start=start_date, end=end_date, freq='M').to_timestamp('s').to_list()
    
    trend_data = []

    # Lakukan perulangan untuk setiap periode
    for p_timestamp in period_range:
        if granularity == 'daily':
            current_start = p_timestamp.normalize()
            current_end = p_timestamp.normalize() + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            period_str = p_timestamp.strftime('%Y-%m-%d')
        else:
            current_start = p_timestamp.normalize().replace(day=1)
            current_end = current_start + pd.offsets.MonthEnd(1)
            period_str = p_timestamp.strftime('%Y-%m')

        # Filter data untuk periode saat ini
        df_orders_period = df_orders[
            (df_orders['date_created_gmt'] >= current_start) & 
            (df_orders['date_created_gmt'] <= current_end)
        ].copy()
        
        df_churn_period = df_churn[
            (df_churn['deleted_at'] >= current_start) & 
            (df_churn['deleted_at'] <= current_end)
        ].copy()

        # Hitung Churn dan Retained
        churn_count = df_churn_period['user_id'].nunique()
        retained_outlets = df_orders_period['outlet_id'].nunique()
        
        trend_data.append({
            'date': p_timestamp, 
            'Retained': retained_outlets,
            'Churn': churn_count
        })

    df_trend = pd.DataFrame(trend_data)
    df_trend['date'] = pd.to_datetime(df_trend['date'])

    return df_trend

@st.cache_data
def get_open_closed_ratio_working(start_date, end_date):
    query = """
        WITH raw_hours AS (
            SELECT 
                user_id AS outlet_id,
                meta_value
            FROM public.raw_sfwc_usermeta 
            WHERE meta_key = 'wcfm_vendor_store_hours'
              AND meta_value IS NOT NULL
              AND meta_value != ''
              AND meta_value != 'a:0:{}'
        ),
        -- Extract semua start dan end times
        time_slots AS (
            SELECT 
                outlet_id,
                unnest(regexp_matches(meta_value, 's:5:"start";s:\\d+:"([0-9]{2}:[0-9]{2})"', 'g')) AS start_time,
                unnest(regexp_matches(meta_value, 's:3:"end";s:\\d+:"([0-9]{2}:[0-9]{2})"', 'g')) AS end_time
            FROM raw_hours
        ),
        -- Hitung operational minutes per outlet per hari
        daily_minutes AS (
            SELECT 
                outlet_id,
                EXTRACT(EPOCH FROM (end_time::time - start_time::time)) / 60 AS minutes_per_day
            FROM time_slots
            WHERE start_time IS NOT NULL 
              AND end_time IS NOT NULL
              AND start_time::time < end_time::time
        ),
        -- Total operational minutes (asumsi 5 hari kerja dalam seminggu)
        operational_minutes AS (
            SELECT 
                outlet_id,
                AVG(minutes_per_day) * 6 AS ideal_minutes  -- 5 hari kerja per minggu
            FROM daily_minutes
            GROUP BY outlet_id
        ),
        -- Hitung waktu pause dengan window function terpisah
        pause_windows AS (
            SELECT 
                outlet_id,
                status,
                created_at,
                LEAD(created_at) OVER (PARTITION BY outlet_id ORDER BY created_at) AS next_time
            FROM public.raw_sfwc_pause_stores 
            WHERE created_at BETWEEN %(start_date)s AND %(end_date)s
              AND status IN ('PAUSED', 'UNPAUSED')
        ),
        -- Hitung total paused minutes
        paused_intervals AS (
            SELECT 
                outlet_id,
                EXTRACT(EPOCH FROM (
                    COALESCE(next_time, %(end_date)s) - created_at
                )) / 60.0 AS paused_minutes
            FROM pause_windows
            WHERE status = 'PAUSED'
              AND created_at < COALESCE(next_time, %(end_date)s)
        ),
        paused_minutes AS (
            SELECT 
                outlet_id,
                SUM(paused_minutes) AS total_paused_minutes
            FROM paused_intervals
            GROUP BY outlet_id
        )
        -- Final calculation
        SELECT 
            o.outlet_id,
            ROUND(o.ideal_minutes, 2) AS ideal_minutes,
            ROUND(COALESCE(p.total_paused_minutes, 0), 2) AS paused_minutes,
            ROUND(GREATEST(o.ideal_minutes - COALESCE(p.total_paused_minutes, 0), 0), 2) AS uptime_minutes,
            CASE 
                WHEN o.ideal_minutes > 0 THEN
                    ROUND(100.0 * GREATEST(o.ideal_minutes - COALESCE(p.total_paused_minutes, 0), 0) / o.ideal_minutes, 2)
                ELSE 0
            END AS open_closed_ratio
        FROM operational_minutes o
        LEFT JOIN paused_minutes p ON o.outlet_id = p.outlet_id
        WHERE o.ideal_minutes > 0
        ORDER BY o.outlet_id;
    """
    
    params = {"start_date": start_date, "end_date": end_date}
    
    try:
        with get_dwh_connection() as conn:
            df = pd.read_sql(query, conn, params=params)          
            if len(df) == 0:
                st.warning("Tidak ada data jam operasional outlet yang valid ditemukan.")
                return pd.DataFrame()           
            df['open_closed_ratio'] = df['open_closed_ratio'].fillna(0)
            
            return df
            
    except Exception as e:
        st.error(f"Gagal menghitung Open vs Closed Outlet Ratio: {e}")
        return pd.DataFrame(columns=['outlet_id', 'uptime_minutes', 'paused_minutes', 'open_closed_ratio'])

def get_open_closed_daily_trend(start_date, end_date, granularity):
    """
    Menghitung jumlah outlet yang Open vs. Paused per hari atau per bulan.
    """
    print(f"\n--- [ETL] Menghitung jumlah outlet Open vs Closed dari {start_date} hingga {end_date} dengan granularitas {granularity} ---")

    try:
        with get_dwh_connection() as conn:
            query_pause_events = """
            SELECT
                outlet_id,
                created_at,
                status
            FROM public.raw_sfwc_pause_stores
            WHERE created_at::date BETWEEN %(start_date)s AND %(end_date)s
            ORDER BY created_at ASC;
            """
            df_pause_events = pd.read_sql(
                query_pause_events,
                conn,
                params={'start_date': start_date, 'end_date': end_date}
            )
            
            query_all_outlets = "SELECT DISTINCT outlet_id FROM public.raw_sfwc_pause_stores;"
            df_all_outlets = pd.read_sql(query_all_outlets, conn)

    except Exception as e:
        st.error(f"Error: Gagal mengambil data mentah. Pesan: {e}")
        return pd.DataFrame()

    if df_pause_events.empty or df_all_outlets.empty:
        return pd.DataFrame()

    df_pause_events['created_at'] = pd.to_datetime(df_pause_events['created_at'])
    all_outlets = df_all_outlets['outlet_id'].unique()

    # Logika untuk agregasi harian
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    daily_data = []
    
    for d in date_range:
        current_date = d.normalize()
        
        daily_paused_outlets = df_pause_events[
            (df_pause_events['created_at'].dt.date == current_date.date()) &
            (df_pause_events['status'] == 'PAUSED')
        ]['outlet_id'].unique()

        paused_count = len(daily_paused_outlets)
        open_count = len(all_outlets) - paused_count
        
        daily_data.append({
            'date': current_date,
            'Open': open_count,
            'Close': paused_count})

    df_result = pd.DataFrame(daily_data)

    if granularity.lower() == "monthly":
        df_result['period'] = df_result['date'].dt.to_period('M').astype(str)
        df_final = df_result.groupby('period').agg(
            Open=('Open', 'sum'),
            Close=('Close', 'sum')
        ).reset_index()
    else: # Daily
        df_result['period'] = df_result['date'].dt.strftime('%Y-%m-%d')
        df_final = df_result[['period', 'Open', 'Close']].copy()

    return df_final