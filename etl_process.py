
import pandas as pd
import streamlit as st
from db_connection import get_connection, get_dwh_connection
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import calendar



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
                'revenue_product', 'cogs_product', 'gross_profit_product']
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
    metrics = {'activation_rate': None, 'retention_rate': None}
    
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
    
    return metrics


@st.cache_data
def get_outlet_metrics_retention_trend(start_date, end_date, granularity="monthly"):
    granularity = granularity.lower()
    print(f"\n--- [ETL] Menghitung trend Retained vs Churned ({granularity}) (Metode CTE) ---")
    
    if granularity == "monthly":
        interval = '1 month'
        sql_trunc = 'month'
    elif granularity == "weekly":
        interval = '1 week'
        sql_trunc = 'week'
    elif granularity == "daily":
        interval = '1 day'
        sql_trunc = 'day'
    else:
        raise ValueError("Granularity harus 'monthly', 'weekly', atau 'daily'.")

    query = f"""
    WITH
    -- 1. Tentukan tanggal sinkronisasi pertama untuk setiap outlet (First Activation)
    outlet_first_sync AS (
        SELECT outlet_id, MIN(created_at) AS first_sync_date 
        FROM public.raw_sfwc_menu_sync_logs
        GROUP BY outlet_id
    ),
    
    -- 2. Buat seri tanggal/periode yang akan dianalisis
    date_series AS (
        SELECT DATE_TRUNC('{sql_trunc}', generate_series(
            %(start_date)s::date, 
            %(end_date)s::date, 
            '{interval}'::interval
        ))::date AS period_date
    ),
    
    -- 3. Hitung tanggal batas (boundary dates) untuk setiap periode
    retention_metrics AS (
        SELECT
            ds.period_date,
            (ds.period_date + INTERVAL '{interval}' - INTERVAL '1 day')::date AS current_end_date,
            (ds.period_date - INTERVAL '1 day')::date AS prev_end_date
        FROM date_series ds
    )
    
    -- 4. Hitung Retained, Previous Active, dan Current Active untuk setiap periode
    SELECT
        t.period_date AS date,
        
        -- A. Total Outlet yang Aktif di Periode Sebelumnya (P-1)
        COUNT(DISTINCT 
            CASE 
                -- Aktif di P-1: first_sync <= prev_end_date DAN belum dihapus di prev_end_date
                WHEN ofs.first_sync_date <= t.prev_end_date
                AND (u.deleted_at IS NULL OR u.deleted_at > t.prev_end_date) -- Kriteria Aktif P-1
                THEN ofs.outlet_id 
                ELSE NULL 
            END
        ) AS previous_active_count,
        
        -- B. Total Outlet yang Retained (Aktif di P-1 DAN Aktif di P)
        COUNT(DISTINCT 
            CASE 
                -- Syarat 1 (Aktif di P-1)
                WHEN ofs.first_sync_date <= t.prev_end_date
                AND (u.deleted_at IS NULL OR u.deleted_at > t.prev_end_date)
                
                -- Syarat 2 (Aktif di P)
                AND ofs.first_sync_date <= t.current_end_date -- Selalu benar jika syarat 1 terpenuhi
                AND (u.deleted_at IS NULL OR u.deleted_at > t.current_end_date) -- Kriteria Aktif P
                
                THEN ofs.outlet_id 
                ELSE NULL 
            END
        ) AS retained_count
        
    FROM retention_metrics t
    LEFT JOIN outlet_first_sync ofs ON TRUE 
    LEFT JOIN public.raw_sfwc_users u ON ofs.outlet_id = u.id
    WHERE ofs.first_sync_date <= t.current_end_date 
    GROUP BY 1
    ORDER BY 1
    """

    params = {'start_date': start_date, 'end_date': end_date}
    
    try:
        with get_dwh_connection() as conn:
            df = pd.read_sql(query, conn, params=params)

        df['Churn'] = df['previous_active_count'] - df['retained_count']
        df['Churn'] = df['Churn'].clip(lower=0) 
        
        df.rename(columns={'retained_count': 'Retained'}, inplace=True)
        df['date'] = pd.to_datetime(df['date']).dt.date
        
        return df[['date', 'Retained', 'Churn']].copy()

    except Exception as e:
        print(f"ERROR saat menghitung tren retensi outlet: {e}")
        return pd.DataFrame({'date': [], 'Retained': [], 'Churn': []})
    
    

@st.cache_data
def get_open_closed_ratio_working(start_date, end_date):
    period_days = (end_date - start_date).days + 1
    conversion_factor = period_days / 7.0 
    
    params = {
        "start_date": start_date, 
        "end_date": end_date,
        "conversion_factor": conversion_factor}
    
    query = f"""
        WITH raw_hours AS (
            SELECT 
                user_id AS outlet_id,
                meta_value
            FROM public.raw_sfwc_usermeta 
            WHERE meta_key = 'wcfm_vendor_store_hours'
              AND meta_value IS NOT NULL
              AND meta_value != ''
              AND meta_value != 'a:0:{{}}'
        ),
        -- Extract semua start dan end times
        time_slots AS (
            SELECT 
                outlet_id,
                unnest(regexp_matches(meta_value, 's:5:"start";s:\\d+:"([0-9]{{2}}:[0-9]{{2}})"', 'g')) AS start_time,
                unnest(regexp_matches(meta_value, 's:3:"end";s:\\d+:"([0-9]{{2}}:[0-9]{{2}})"', 'g')) AS end_time
            FROM raw_hours
        ),
        -- Hitung minutes per slot/hari
        daily_minutes AS (
            SELECT 
                outlet_id,
                EXTRACT(EPOCH FROM (end_time::time - start_time::time)) / 60.0 AS minutes_per_slot
            FROM time_slots
            -- Tambahkan kembali filter robustness (start < end)
            WHERE start_time IS NOT NULL 
              AND end_time IS NOT NULL
              AND start_time::time < end_time::time
        ),
        -- Menghitung Total Menit Ideal Mingguan (SUM)
        ideal_weekly_minutes AS (
             SELECT 
                outlet_id,
                -- SUM jauh lebih akurat untuk total jam buka mingguan (ideal)
                SUM(minutes_per_slot) AS weekly_ideal_minutes
             FROM daily_minutes
             GROUP BY outlet_id
        ),
        -- 2. MENSKALAKAN IDEAL MINUTES ke durasi periode filter (P)
        operational_minutes AS (
            SELECT
                iwm.outlet_id,
                -- Skalakan Minutes Mingguan Ideal ke Menit Ideal Periode Filter
                (iwm.weekly_ideal_minutes * %(conversion_factor)s) AS ideal_minutes 
            FROM ideal_weekly_minutes iwm
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
              -- Potong interval pause agar tidak melewati end_date filter
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
            -- Uptime: Ideal - Paused (dibatasi minimal 0)
            ROUND(GREATEST(o.ideal_minutes - COALESCE(p.total_paused_minutes, 0), 0), 2) AS uptime_minutes,
            CASE 
                WHEN o.ideal_minutes > 0 THEN
                    -- Rasio: (Uptime / Ideal) * 100
                    ROUND(100.0 * GREATEST(o.ideal_minutes - COALESCE(p.total_paused_minutes, 0), 0) / o.ideal_minutes, 2)
                ELSE 0
            END AS open_closed_ratio
        FROM operational_minutes o
        LEFT JOIN paused_minutes p ON o.outlet_id = p.outlet_id
        WHERE o.ideal_minutes > 0
        ORDER BY o.outlet_id;
    """
    
    try:
        with get_dwh_connection() as conn:
            df = pd.read_sql(query, conn, params=params) 
            if len(df) == 0:
                return pd.DataFrame() 
            df['open_closed_ratio'] = df['open_closed_ratio'].fillna(0)
            return df
            
    except Exception as e:
        st.error(f"Gagal menghitung Open vs Closed Outlet Ratio: {e}")
        return pd.DataFrame(columns=['outlet_id', 'uptime_minutes', 'paused_minutes', 'open_closed_ratio'])


@st.cache_data
def get_open_closed_trend(start_date, end_date, granularity="daily"):
    granularity = granularity.lower()
    all_periods = []
    
    current_start = start_date
    while current_start <= end_date:
        
        if granularity == "monthly":
            days_in_month = calendar.monthrange(current_start.year, current_start.month)[1]
            current_end = current_start + timedelta(days=days_in_month - 1)
            period_label = current_start.strftime("%Y-%m") # Label: 2024-01

        elif granularity == "weekly":
            current_end = current_start + timedelta(days=6)
            period_label = f"{current_start.strftime('%Y-%m-%d')} - {current_end.strftime('%Y-%m-%d')}" # Label: 2024-01-01 - 2024-01-07

        elif granularity == "daily":
            current_end = current_start
            period_label = current_start.strftime("%Y-%m-%d") # Label: 2024-01-01
            
        else:
            raise ValueError("Granularity harus 'monthly', 'weekly', atau 'daily'.")

        if current_end > end_date:
            current_end = end_date
        
        all_periods.append({
            'start': current_start,
            'end': current_end,
            'period': period_label})

        if granularity == "monthly":
            if current_end == end_date:
                break 
            current_start = (current_end + timedelta(days=1)).replace(day=1)
        
        elif granularity == "weekly":
            current_start = current_end + timedelta(days=1)
            
        elif granularity == "daily":
            current_start = current_end + timedelta(days=1)
            
        if current_start > end_date:
            break

    final_df_list = []
    
    print(f"Menghitung Open vs Closed Trend untuk {len(all_periods)} periode ({granularity})...")

    for p in all_periods:
        df_metrics = get_open_closed_ratio_working(p['start'], p['end'])
        
        if not df_metrics.empty:
            avg_open_ratio = df_metrics['open_closed_ratio'].mean()
            
            avg_close_ratio = 100.0 - avg_open_ratio
            
            final_df_list.append({
                'period': p['period'],
                'open': round(avg_open_ratio, 2),
                'close': round(avg_close_ratio, 2)})

    if not final_df_list:
        print("Tidak ada data yang tersedia untuk rentang periode ini.")
        return pd.DataFrame({'period': [], 'open': [], 'close': []})
        
    df_trend = pd.DataFrame(final_df_list)
    return df_trend


@st.cache_data
def get_menu_availability_ratio(start_date, end_date, granularity="daily"):
    """
    Menghitung rasio ketersediaan menu dengan granularity harian, mingguan, atau bulanan.
    """

    if granularity == "daily":
        date_trunc = "day"
        multiplier = 1
    elif granularity == "weekly":
        date_trunc = "week"
        multiplier = 7
    elif granularity == "monthly":
        date_trunc = "month"
        multiplier = 4
    else:
        raise ValueError("granularity harus 'daily', 'weekly', atau 'monthly'")

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
            SUM(dm.minutes_per_slot) AS total_daily_minutes,
            (SUM(dm.minutes_per_slot) * {multiplier} * pc.total_menus) AS total_ideal_minutes_menu
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
        st.error(f"Gagal menghitung Rasio Ketersediaan Menu: {e}")
        return pd.DataFrame(columns=[
            'outlet_id', 'period', 'total_menus', 'total_ideal_minutes_menu', 
            'total_unavailable_minutes', 'total_available_minutes', 
            'availability_ratio_percent'
        ])



@st.cache_data
def get_menu_availability_trend(start_date, end_date, granularity="daily"):
    """
    Menghitung tren ketersediaan menu (available vs unavailable)
    dengan pendekatan yang konsisten seperti `get_open_closed_trend`.
    
    Perhitungan dilakukan per periode (daily / weekly / monthly)
    dengan memanggil `get_menu_availability_ratio()` untuk setiap rentang waktu.
    """

    granularity = granularity.lower()
    all_periods = []

    current_start = start_date
    while current_start <= end_date:
        if granularity == "monthly":
            days_in_month = calendar.monthrange(current_start.year, current_start.month)[1]
            current_end = current_start + timedelta(days=days_in_month - 1)
            period_label = current_start.strftime("%Y-%m")

        elif granularity == "weekly":
            current_end = current_start + timedelta(days=6)
            period_label = f"{current_start.strftime('%Y-%m-%d')} - {current_end.strftime('%Y-%m-%d')}"

        elif granularity == "daily":
            current_end = current_start
            period_label = current_start.strftime("%Y-%m-%d")

        else:
            raise ValueError("Granularity harus 'monthly', 'weekly', atau 'daily'.")

        if current_end > end_date:
            current_end = end_date

        all_periods.append({
            'start': current_start,
            'end': current_end,
            'period': period_label
        })

        # Naikkan tanggal ke periode berikutnya
        if granularity == "monthly":
            if current_end == end_date:
                break
            current_start = (current_end + timedelta(days=1)).replace(day=1)
        else:
            current_start = current_end + timedelta(days=1)

        if current_start > end_date:
            break

    final_df_list = []

    print(f"Menghitung Menu Availability Trend untuk {len(all_periods)} periode ({granularity})...")

    for p in all_periods:
        df_metrics = get_menu_availability_ratio(p['start'], p['end'], granularity="daily")

        if not df_metrics.empty:
            avg_avail_ratio = df_metrics['availability_ratio_percent'].mean()

            avg_unavail_ratio = 100.0 - avg_avail_ratio

            final_df_list.append({
                'period': p['period'],
                'available': round(avg_avail_ratio, 2),
                'unavailable': round(avg_unavail_ratio, 2)})

    if not final_df_list:
        print("Tidak ada data yang tersedia untuk rentang periode ini.")
        return pd.DataFrame({'period': [], 'available': [], 'unavailable': []})

    df_trend = pd.DataFrame(final_df_list)
    return df_trend

def get_zombie_product_ratio(start_date, end_date):
    """
    Menghitung persentase Zombie Product:
    Produk tanpa penjualan selama sebulan penuh pada outlet aktif.
    Hanya menghitung produk milik outlet aktif (first sync < end_date dan deleted_at IS NULL).
    """

    query = """
    WITH outlet_first_sync AS (
        SELECT 
            outlet_id, 
            MIN(created_at) AS first_sync_date 
        FROM public.raw_sfwc_menu_sync_logs
        GROUP BY outlet_id
    ),

    active_outlets AS (
        SELECT 
            ofs.outlet_id
        FROM outlet_first_sync ofs
        JOIN public.raw_sfwc_users u ON ofs.outlet_id = u.ID
        WHERE ofs.first_sync_date < %(end_date)s
          AND (u.deleted_at IS NULL OR u.deleted_at >= %(start_date)s)
    ),

    product_sales AS (
        SELECT 
            oi.product_id,
            o.outlet_id,
            SUM(oim.meta_value::INTEGER) AS total_qty
        FROM public.raw_sfwc_woocommerce_order_items oi
        JOIN public.raw_sfwc_orders o ON oi.order_id = o.id
        JOIN public.raw_sfwc_woocommerce_order_itemmeta oim 
            ON oi.order_item_id = oim.order_item_id
        WHERE oim.meta_key = '_qty'
          AND o.date_created_gmt BETWEEN %(start_date)s AND %(end_date)s
          AND o.outlet_id IN (SELECT outlet_id FROM active_outlets)
        GROUP BY oi.product_id, o.outlet_id
    ),

    all_products AS (
        SELECT 
            p.ID AS product_id,
            p.post_title AS product_name,
            p.outlet_id
        FROM public.raw_sfwc_posts p
        WHERE p.post_type = 'product'
          AND p.outlet_id IN (SELECT outlet_id FROM active_outlets)
          AND (p.deleted_at IS NULL OR p.deleted_at >= %(start_date)s)
    ),

    zombie_status AS (
        SELECT 
            ap.product_id,
            ap.product_name,
            ap.outlet_id,
            COALESCE(ps.total_qty, 0) AS total_sales,
            CASE 
                WHEN COALESCE(ps.total_qty, 0) = 0 THEN 1 
                ELSE 0 
            END AS is_zombie
        FROM all_products ap
        LEFT JOIN product_sales ps 
            ON ap.product_id = ps.product_id AND ap.outlet_id = ps.outlet_id
    )

    SELECT 
        COUNT(*) AS total_products,
        SUM(is_zombie) AS total_zombie,
        ROUND((SUM(is_zombie)::NUMERIC / COUNT(*) * 100), 2) AS zombie_percentage
    FROM zombie_status;
    """

    params = {"start_date": start_date, "end_date": end_date}

    try:
        with get_dwh_connection() as conn:
            df = pd.read_sql(query, conn, params=params)

        if df.empty:
            print("Tidak ada data zombie product ditemukan.")
            return pd.DataFrame(columns=["total_products", "total_zombie", "zombie_percentage"])

        return df

    except Exception as e:
        print(f"Gagal menghitung Zombie Product Ratio: {e}")
        return pd.DataFrame()