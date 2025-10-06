
import pandas as pd
import streamlit as st
from db_connection import get_connection, get_dwh_connection
from datetime import datetime, timedelta
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
def get_outlet_performance_metrics(start_date, end_date):
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
    previous_active AS (
        SELECT DISTINCT u.id AS outlet_id
        FROM outlet_first_sync f
        JOIN raw_sfwc_users u ON f.outlet_id = u.id
        WHERE f.first_sync_date <= %(prev_end_date)s
            AND (u.deleted_at IS NULL OR u.deleted_at > %(prev_end_date)s)
    ),

    -- Outlet aktif bulan ini
    current_active AS (
        SELECT DISTINCT u.id AS outlet_id
        FROM outlet_first_sync f
        JOIN raw_sfwc_users u ON f.outlet_id = u.id
        WHERE f.first_sync_date <= %(end_date)s
            AND (u.deleted_at IS NULL OR u.deleted_at > %(end_date)s)
    ),

    -- Outlet retained (aktif di dua bulan berturut-turut)
    retained_outlets AS (
        SELECT c.outlet_id
        FROM current_active c
        INNER JOIN previous_active p ON c.outlet_id = p.outlet_id
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
    (SELECT COUNT(*) FROM retained_outlets)::FLOAT/ NULLIF((SELECT COUNT(*) FROM previous_active)::FLOAT, 0) AS retention_rate,
    
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
def get_outlet_metrics_retention_trend(start_date, end_date, granularity='daily'):
    print(f"\n--- [ETL] Menghitung tren retensi outlet per {granularity} ---")

    if not start_date or not end_date:
        return pd.DataFrame()

    try:
        with get_dwh_connection() as conn:
            # Ambil data outlet (go live & deleted)
            query_outlet = """
            SELECT 
                id AS outlet_id,
                go_live,
                deleted_at AS outlet_deleted_at
            FROM public.raw_sfwc_users
            WHERE go_live IS NOT NULL
            AND (go_live::date <= %(end_date)s);
            """
            df_outlet = pd.read_sql(query_outlet, conn, params={'end_date': end_date})

            # Ambil data churn
            query_churn = """
            SELECT
                id AS user_id,
                deleted_at
            FROM public.raw_sfwc_users
            WHERE deleted_at::date BETWEEN %(start_date)s AND %(end_date)s;
            """
            df_churn = pd.read_sql(query_churn, conn, params={'start_date': start_date, 'end_date': end_date})

    except Exception as e:
        st.error(f"Error: Gagal mengambil data mentah. Pesan: {e}")
        return pd.DataFrame()

    # Pastikan kolom tanggal dalam format datetime
    df_outlet['go_live'] = pd.to_datetime(df_outlet['go_live'])
    df_outlet['outlet_deleted_at'] = pd.to_datetime(df_outlet['outlet_deleted_at'])
    df_churn['deleted_at'] = pd.to_datetime(df_churn['deleted_at'])

    # Tentukan rentang analisis
    if granularity == 'daily':
        period_range = pd.date_range(start=start_date, end=end_date, freq='D')
    else:
        period_range = pd.period_range(start=start_date, end=end_date, freq='M').to_timestamp('s').to_list()

    trend_data = []

    for p_timestamp in period_range:
        if granularity == 'daily':
            current_start = p_timestamp.normalize()
            current_end = p_timestamp.normalize() + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
            period_str = p_timestamp.strftime('%Y-%m-%d')
        else:
            current_start = p_timestamp.normalize().replace(day=1)
            current_end = current_start + pd.offsets.MonthEnd(1)
            period_str = p_timestamp.strftime('%Y-%m')

        # Outlet aktif = sudah go live dan belum dihapus sebelum periode ini berakhir
        active_outlets = df_outlet[
            (df_outlet['go_live'] <= current_end) &
            ((df_outlet['outlet_deleted_at'].isna()) | (df_outlet['outlet_deleted_at'] > current_end))
        ]['outlet_id'].nunique()

        # Outlet churn = yang dihapus dalam periode ini
        churn_count = df_churn[
            (df_churn['deleted_at'] >= current_start) &
            (df_churn['deleted_at'] <= current_end)
        ]['user_id'].nunique()

        trend_data.append({
            'date': p_timestamp,
            'Retained': active_outlets,
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


@st.cache_data
def get_open_closed_trend(start_date, end_date, granularity="daily"):
    """
    Menghitung persentase open vs closed outlet per periode.

    Returns:
        DataFrame dengan kolom: period, Open (%), Close (%)
    """

    if granularity == "daily":
        date_trunc = "day"
    elif granularity == "monthly":
        date_trunc = "month"
    else:
        raise ValueError("granularity harus 'daily' atau 'monthly'")

    query = f"""
    WITH raw_hours AS (
        SELECT 
            user_id AS outlet_id,
            meta_value
        FROM public.raw_sfwc_usermeta
        WHERE meta_key = 'wcfm_vendor_store_hours'
          AND meta_value ~ 's:9:"day_times";a:[1-7]:{{.*}}'
    ),
    time_slots AS (
        SELECT 
            outlet_id,
            unnest(regexp_matches(meta_value, 's:5:"start";s:[0-9]+:"([0-9]{{2}}:[0-9]{{2}})"', 'g')) AS start_time,
            unnest(regexp_matches(meta_value, 's:3:"end";s:[0-9]+:"([0-9]{{2}}:[0-9]{{2}})"', 'g')) AS end_time
        FROM raw_hours
    ),
    daily_minutes AS (
        SELECT 
            outlet_id,
            EXTRACT(EPOCH FROM (end_time::time - start_time::time)) / 60 AS minutes_per_day
        FROM time_slots
        WHERE start_time::time < end_time::time
    ),
    operational_minutes AS (
        SELECT 
            outlet_id,
            AVG(minutes_per_day) * 6 AS ideal_minutes  -- asumsi 6 hari per minggu
        FROM daily_minutes
        GROUP BY outlet_id
    ),
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
    paused_intervals AS (
        SELECT 
            outlet_id,
            DATE_TRUNC('{date_trunc}', created_at) AS period,
            LEAST(EXTRACT(EPOCH FROM (COALESCE(next_time, %(end_date)s) - created_at)) / 60.0, 24*60) AS paused_minutes
        FROM pause_windows
        WHERE status = 'PAUSED'
          AND created_at < COALESCE(next_time, %(end_date)s)
    ),
    paused_minutes AS (
        SELECT 
            outlet_id,
            period,
            SUM(paused_minutes) AS total_paused_minutes
        FROM paused_intervals
        GROUP BY outlet_id, period
    )
    SELECT 
        period,
        ROUND(AVG(GREATEST(o.ideal_minutes - COALESCE(p.total_paused_minutes, 0), 0) / o.ideal_minutes * 100), 2) AS Open,
        ROUND(AVG(LEAST(COALESCE(p.total_paused_minutes, 0), o.ideal_minutes) / o.ideal_minutes * 100), 2) AS Close
    FROM operational_minutes o
    LEFT JOIN paused_minutes p ON o.outlet_id = p.outlet_id AND p.period IS NOT NULL
    GROUP BY period
    ORDER BY period;
    """

    params = {"start_date": start_date, "end_date": end_date}

    try:
        with get_dwh_connection() as conn:
            df = pd.read_sql(query, conn, params=params)

            if df.empty:
                st.warning("Tidak ada data open/closed outlet yang valid ditemukan.")
                return pd.DataFrame(columns=['period', 'Open', 'Close'])

            return df

    except Exception as e:
        st.error(f"Gagal menghitung Open vs Close Outlet Trend: {e}")
        return pd.DataFrame(columns=['period', 'Open', 'Close'])


def get_menu_availability_ratio(start_date, end_date, granularity="daily"):
    """
    Menghitung rasio ketersediaan menu dengan granularity harian atau bulanan.
    
    Args:
        start_date (str/datetime): tanggal mulai
        end_date (str/datetime): tanggal akhir
        granularity (str): "daily" atau "monthly"
    """
    
    if granularity == "daily":
        date_trunc = "day"
    elif granularity == "monthly":
        date_trunc = "month"
    else:
        raise ValueError("granularity harus 'daily' atau 'monthly'")
    
    query = f"""
    WITH raw_hours AS (
        SELECT 
            user_id AS outlet_id,
            meta_value
        FROM public.raw_sfwc_usermeta
        WHERE meta_key = 'wcfm_vendor_store_hours'
          AND meta_value ~ 's:9:"day_times";a:[1-7]:{{.*}}'
    ),
    time_slots AS (
        SELECT 
            outlet_id,
            unnest(regexp_matches(meta_value, 's:5:"start";s:[0-9]+:"([0-9]{{2}}:[0-9]{{2}})"', 'g')) AS start_time,
            unnest(regexp_matches(meta_value, 's:3:"end";s:[0-9]+:"([0-9]{{2}}:[0-9]{{2}})"', 'g')) AS end_time
        FROM raw_hours
    ),
    daily_minutes AS (
        SELECT 
            outlet_id,
            EXTRACT(EPOCH FROM (end_time::time - start_time::time)) / 60.0 AS minutes_per_slot
        FROM time_slots
    ),
    product_counts AS (
        SELECT outlet_id, COUNT(ID) AS total_menus
        FROM public.raw_sfwc_posts
        WHERE post_type = 'product'
        GROUP BY outlet_id
    ),
    ideal_minutes AS (
        SELECT 
            pc.outlet_id,
            pc.total_menus,
            SUM(dm.minutes_per_slot) AS weekly_ideal_minutes,
            (SUM(dm.minutes_per_slot) * 4 * pc.total_menus) AS total_ideal_minutes_menu
        FROM daily_minutes dm
        JOIN product_counts pc ON dm.outlet_id = pc.outlet_id
        GROUP BY pc.outlet_id, pc.total_menus
    ),
    unavailable_minutes AS (
        SELECT
            product_id,
            DATE_TRUNC('{date_trunc}', t1.created_at) AS period,
            SUM(EXTRACT(EPOCH FROM (
                (SELECT created_at 
                 FROM public.raw_sfwc_menu_pause_logs 
                 WHERE product_id = t1.product_id 
                   AND created_at > t1.created_at 
                   AND status = 'AVAILABLE' 
                 ORDER BY created_at ASC LIMIT 1) 
                - t1.created_at
            )))/60.0 AS total_unavailable_minutes
        FROM public.raw_sfwc_menu_pause_logs t1 
        WHERE 
            status = 'UNAVAILABLE'
            AND created_at BETWEEN %(start_date)s AND %(end_date)s
        GROUP BY product_id, DATE_TRUNC('{date_trunc}', t1.created_at)
    )
    SELECT 
        im.outlet_id,
        DATE_TRUNC('{date_trunc}', COALESCE(um.period, %(start_date)s)) AS period,
        im.total_menus,
        im.total_ideal_minutes_menu,
        COALESCE(SUM(um.total_unavailable_minutes), 0) AS total_unavailable_minutes,
        (im.total_ideal_minutes_menu - COALESCE(SUM(um.total_unavailable_minutes), 0)) AS total_available_minutes,
        CASE 
            WHEN im.total_ideal_minutes_menu > 0 THEN
                ROUND(
                    ((im.total_ideal_minutes_menu - COALESCE(SUM(um.total_unavailable_minutes), 0)) / im.total_ideal_minutes_menu) * 100,
                    2
                )
            ELSE 0 
        END AS availability_ratio_percent
    FROM ideal_minutes im
    LEFT JOIN public.raw_sfwc_posts p ON im.outlet_id = p.outlet_id
    LEFT JOIN unavailable_minutes um ON p.ID = um.product_id
    GROUP BY im.outlet_id, im.total_menus, im.total_ideal_minutes_menu, DATE_TRUNC('{date_trunc}', COALESCE(um.period, %(start_date)s))
    ORDER BY im.outlet_id, period;
    """
    
    params = {"start_date": start_date, "end_date": end_date}
    
    try:
        with get_dwh_connection() as conn: 
            df = pd.read_sql(query, conn, params=params)
        
        if df.empty:
            print("Tidak ada data rasio ketersediaan yang valid ditemukan.")
            return pd.DataFrame(columns=[
                'outlet_id', 'period', 'total_menus', 'total_ideal_minutes_menu', 
                'total_unavailable_minutes', 'total_available_minutes', 
                'availability_ratio_percent'
            ]) 
        return df
            
    except Exception as e:
        print(f"Gagal menghitung Rasio Ketersediaan Menu: {e}")


def get_menu_availability_trend(start_date, end_date, granularity="daily"):
    """
    Menghitung persentase ketersediaan menu dengan granularity harian atau bulanan.
    Output: persen available vs unavailable siap untuk chart stacked bar.
    
    Memperbaiki masalah pada tanggal awal dengan memastikan setiap periode dalam 
    rentang memiliki baris, meskipun tidak ada log 'UNAVAILABLE'.
    """

    # --- Konversi tanggal string ke datetime ---
    if isinstance(start_date, str):
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
    else:
        start_date_obj = start_date

    if isinstance(end_date, str):
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
    else:
        end_date_obj = end_date
        
    if granularity == "daily":
        date_trunc = "day"
        interval = '1 day'
    elif granularity == "monthly":
        date_trunc = "month"
        interval = '1 month'
    else:
        raise ValueError("granularity harus 'daily' atau 'monthly'")

    # Perhatikan: Query SQL telah dimodifikasi (lihat di bawah)
    query = f"""
    WITH raw_hours AS (
        SELECT 
            user_id AS outlet_id,
            meta_value
        FROM public.raw_sfwc_usermeta
        WHERE meta_key = 'wcfm_vendor_store_hours'
          AND meta_value ~ 's:9:"day_times";a:[1-7]:{{.*}}'
    ),
    time_slots AS (
        SELECT 
            outlet_id,
            unnest(regexp_matches(meta_value, 's:5:"start";s:[0-9]+:"([0-9]{{2}}:[0-9]{{2}})"', 'g'))::time AS start_time,
            unnest(regexp_matches(meta_value, 's:3:"end";s:[0-9]+:"([0-9]{{2}}:[0-9]{{2}})"', 'g'))::time AS end_time
        FROM raw_hours
    ),
    daily_minutes AS (
        SELECT 
            outlet_id,
            EXTRACT(EPOCH FROM (end_time - start_time)) / 60.0 AS minutes_per_slot
        FROM time_slots
    ),
    product_counts AS (
        SELECT outlet_id, COUNT(ID) AS total_menus
        FROM public.raw_sfwc_posts
        WHERE post_type = 'product'
        GROUP BY outlet_id
    ),
    ideal_minutes AS (
        -- Menghitung Total Ideal Minutes per hari per menu per outlet
        SELECT 
            pc.outlet_id,
            p.ID AS product_id,
            (SUM(dm.minutes_per_slot)) AS daily_open_minutes, -- Ideal per hari per menu
            (SUM(dm.minutes_per_slot)) AS total_ideal_minutes_menu
        FROM daily_minutes dm
        JOIN product_counts pc ON dm.outlet_id = pc.outlet_id
        JOIN public.raw_sfwc_posts p ON pc.outlet_id = p.outlet_id -- Join ke level product
        WHERE p.post_type = 'product'
        GROUP BY pc.outlet_id, p.ID
    ),
    unavailable_minutes AS (
        -- Menghitung Total Unavailable Minutes per periode per menu
        SELECT
            product_id,
            DATE_TRUNC('{date_trunc}', t1.created_at) AS period,
            SUM(
                EXTRACT(EPOCH FROM (
                    COALESCE(
                        (SELECT MIN(t2.created_at)
                           FROM public.raw_sfwc_menu_pause_logs t2
                           WHERE t2.product_id = t1.product_id
                             AND t2.created_at > t1.created_at
                             AND t2.status = 'AVAILABLE'
                             AND DATE_TRUNC('{date_trunc}', t2.created_at) = DATE_TRUNC('{date_trunc}', t1.created_at)),
                        -- Jika log AVAILABLE tidak ada dalam periode, gunakan akhir periode (atau end_date)
                        (DATE_TRUNC('{date_trunc}', t1.created_at) + interval '{interval}')::timestamp - interval '1 second'
                    ) - t1.created_at
                )) / 60.0
            ) AS total_unavailable_minutes
        FROM public.raw_sfwc_menu_pause_logs t1
        WHERE t1.status = 'UNAVAILABLE'
          AND t1.created_at BETWEEN %(start_date)s AND %(end_date)s
        GROUP BY product_id, DATE_TRUNC('{date_trunc}', t1.created_at)
    ),
    -- **SOLUSI UTAMA:** Buat seri tanggal/bulan sebagai basis
    date_series AS (
        SELECT 
            DATE_TRUNC('{date_trunc}', generate_series(%(start_date)s::timestamp, %(end_date)s::timestamp, interval '{interval}')) AS period_date
    )
    
    SELECT 
        ds.period_date AS period,
        ROUND(
            CASE WHEN SUM(im.total_ideal_minutes_menu) > 0
                 THEN (SUM(im.total_ideal_minutes_menu) - COALESCE(SUM(um.total_unavailable_minutes),0))
                      / SUM(im.total_ideal_minutes_menu) * 100
                 ELSE 0 END, 2
        ) AS available,
        ROUND(
            CASE WHEN SUM(im.total_ideal_minutes_menu) > 0
                 THEN COALESCE(SUM(um.total_unavailable_minutes),0)
                      / SUM(im.total_ideal_minutes_menu) * 100
                 ELSE 0 END, 2
        ) AS unavailable
    FROM date_series ds
    -- Join semua menu ideal ke setiap periode
    LEFT JOIN ideal_minutes im ON 1=1 
    -- Join data unavailable yang sudah dihitung per periode dan per menu
    LEFT JOIN unavailable_minutes um ON um.period = ds.period_date AND um.product_id = im.product_id
    GROUP BY ds.period_date
    ORDER BY period;
    """

    params = {"start_date": start_date_obj, "end_date": end_date_obj}

    try:
        # Gunakan fungsi koneksi database Anda di sini
        with get_dwh_connection() as conn: 
            # Pastikan Anda mengimplementasikan get_dwh_connection()
            df = pd.read_sql(query, conn, params=params)
            
            if df.empty:
                print("⚠️ Tidak ada data rasio ketersediaan menu ditemukan.")
                return pd.DataFrame(columns=['period','available','unavailable'])

            df['period'] = pd.to_datetime(df['period'])

            # 🔧 Normalisasi untuk granularity monthly → tampilkan sebagai "YYYY-MM"
            if granularity == "monthly":
                # Mengubah timestamp menjadi format YYYY-MM
                df['period'] = df['period'].dt.to_period('M').dt.to_timestamp()

            return df

    except NotImplementedError:
        print("❌ Error: Fungsi 'get_dwh_connection' belum diimplementasikan.")
        return pd.DataFrame(columns=['period','available','unavailable'])
    except Exception as e:
        print(f"❌ Error hitung menu availability trend: {e}")
        return pd.DataFrame(columns=['period','available','unavailable'])