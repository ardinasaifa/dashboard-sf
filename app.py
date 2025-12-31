import streamlit as st
import pandas as pd
import plotly.express as px
import folium
import json, os, re
from shapely.geometry import shape
from shapely.geometry import shape as shapely_shape
from shapely.ops import unary_union
from prophet.plot import plot_plotly
from streamlit_option_menu import option_menu


from streamlit_folium import st_folium
from datetime import date, timedelta
from etl_process import load_dm_order, load_dm_outlet, load_dm_brands, get_outlet_performance_metrics, get_outlet_metrics_retention_trend, get_open_closed_ratio_working, get_open_closed_trend, get_menu_availability_ratio, get_menu_availability_trend, get_zombie_product_ratio
from forecasting import prepare_forecast_data, run_prophet_forecast

# ========================================== LOAD DATA ======================================================
df_order = load_dm_order()
df_outlet = load_dm_outlet()
df_brands = load_dm_brands()

# FILE_PROVINSI = '38 Provinsi Indonesia - Provinsi.json'
BASE_DIR = "indonesia-district-master" 

# CSS Configuration
st.set_page_config(layout="wide", page_title="Superfood Dashboard", initial_sidebar_state="expanded")
st.markdown("""
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        /* --- Global Styles --- */
        html, body, .stApp { font-family: 'Poppins', sans-serif; background-color: #F0F2F6; color: #333; }
        h1, h2, h3 { font-weight: 600; color: #111; }
        
        /* --- Sidebar Styling --- */
        section[data-testid="stSidebar"] {background-color: #FFFFFF; padding-left: 0px; padding-right: 0px; border-right: 0.5px solid #E0E0E0; padding: 8px 0px; }
        
        /* --- Main Content Styling --- */
        .st-emotion-cache-1y4p8pa { padding: 2rem 3rem; }
        [data-testid="stMetric"] { background-color: #FFFFFF; border: 1px solid #E0E0E0; border-radius: 10px; padding: 1.25rem; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
        [data-testid="stMetricLabel"] { color: #6c757d; font-size: 1em; font-weight: 500; }
        [data-testid="stMetricValue"] { font-size: 1.8em; font-weight: 600;  }
        [data-testid="stMetricDelta"] {background: none !important}
        
        /* --- Tabs Styling --- */
        .stTabs [data-baseweb="tab-list"] { 
            gap: 10px;
            border-bottom: none; 
            padding: 6px;
            background: #F0F2F6;
            border-radius: 1px;
            margin-bottom: 1px;
            width: 100%;          
            display: flex;
            justify-content: space-between}

        .stTabs [data-baseweb="tab-list"] button { 
            flex: 1;                       
            max-width: 100%;                
            background-color: white; 
            border: none; 
            padding: 25px 10px; 
            font-weight: 1000; 
            color: #475569; 
            border-radius: 8px;
            transition: all 0.2s ease;
            font-size: 100px;
            border-bottom: none !important; 
            text-align: center;}

        .stTabs [data-baseweb="tab-list"] button:hover { 
            background-color: #FFEBEB;
            color: #FF4B4B; 
            border-bottom: none !important; }

        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] { 
            background-color: #FFEBEB !important;
            color: #FF4B4B !important; 
            font-weight: 800; 
            background-color: white;
            box-shadow: 0 2px 4px rgba(255, 75, 75, 0.3);
            border-bottom: none !important; }

        .stTabs [data-baseweb="tab-highlight"] {
            display: none !important; }

        .stTabs [data-baseweb="tab-border"] {
            display: none !important; }

        .stTabs [data-baseweb="tab-list"] button:focus {
            outline: none !important;
            border: none !important;
            box-shadow: 0 2px 4px rgba(255, 75, 75, 0.3);}
        
         /* --- Charts Styling --- */
        .stPlotlyChart { border: 1px solid #E0E0E0; 
            border-radius: 10px; 
            padding: 1rem; 
            background-color: #FFFFFF; 
            box-shadow: 0 4px 12px rgba(0,0,0,0.05); 
            margin: 0 !important; 
            box-sizing: border-box !important; 
            max-width: 100% !important;
            width: 100% !important; }
            
        .stMultiSelect div[data-baseweb="select"] > div {
            /* Wadah utama, untuk border dan sedikit padding */
            background-color: #FFFFFF; 
            border-radius: 8px;
            border: 1px solid #E0E0E0;}

        .stMultiSelect div[data-baseweb="select"] input {
            /* Area input teks sebenarnya (background) */
            background-color: #FFFFFF !important;
            color: black !important;}

        span[data-baseweb="tag"] {
            color: black; 
            font-size: 17px;
            background-color: #F0F2F6;}
        
        .stSelectbox > div > div {
            background-color: #FFFFFF !important;
            border: 1px solid #E0E0E0 !important;
            border-radius: 8px !important;} 
        .stDateInput > div > div { background-color: #FFFFFF; border-radius: 8px; border: 1px solid #E0E0E0; }
        .main > div { padding-left: 2rem; padding-right: 2rem; }
    </style>
""", unsafe_allow_html=True)

@st.cache_data
def load_geojson_dynamic(base_dir, level, selected_province_folder=None, selected_city_folder=None, selected_district_file=None):

    geojson_path = None

    if level == "Province":
        geojson_path = os.path.join(base_dir, "prov 37.geojson")

    elif level == "City":
        geojson_path = os.path.join(base_dir, "kab 37.geojson")

    elif level == "District" and selected_province_folder and selected_city_folder:
        city_path = os.path.join(base_dir, selected_province_folder, selected_city_folder)
        
        if selected_district_file:
            geojson_path = os.path.join(city_path, selected_district_file)
        else:
            direct_district_file = os.path.join(city_path, "district.geojson")
            if os.path.exists(direct_district_file):
                geojson_path = direct_district_file
            else:
                district_files = [
                    os.path.join(city_path, f)
                    for f in os.listdir(city_path)
                    if f.endswith(".geojson")]
                if district_files:
                    geojson_path = district_files[0]

    if geojson_path and os.path.exists(geojson_path):
        try:
            with open(geojson_path, encoding="utf-8") as f:
                geojson_data = json.load(f)
        except Exception as e:
            st.error(f"Error loading GeoJSON file {geojson_path}: {e}")
            return None, [], None

        region_names = []
        key_name = None

        possible_keys = {
            "Province": ["prov_name", "province", "name"],
            "City": ["regency", "city", "kabupaten", "name"],
            "District": ["district", "kecamatan", "name"]}

        features = geojson_data.get("features", [])
        if features:
            props = features[0].get("properties", {})
            for k in possible_keys.get(level, ["name"]):
                if k in props:
                    key_name = k
                    break

            if key_name:
                region_names = sorted({
                    normalize_region_name(f["properties"].get(key_name))
                    for f in features
                    if f["properties"].get(key_name)})

        return geojson_data, region_names, key_name

    else:
        st.error(f"GeoJSON file tidak ditemukan untuk level {level}")
        return None, [], None

@st.cache_data
def normalize_region_name(name: str):
    if not name:
        return ""
    name = name.upper().strip()

    prefixes = [
        "KABUPATEN ", "KOTA ", 
        "KAB ", "KAB. ", 
        "KOTA ", "KOTA. "]

    for p in prefixes:
        if name.startswith(p):
            name = name[len(p):]
    return name.strip()


@st.cache_data
def get_filter_options(_df_order, _df_outlet, _df_brands=None):
    if _df_order.empty and _df_outlet.empty and (_df_brands is None or _df_brands.empty):
        return {"brands": [], "outlets": [], "owners": [], "sources": [], "statuses": []}
    
    def format_status(s): 
        return s.replace('wc-', '').replace('-', ' ').title() if isinstance(s, str) else s
    
    if _df_brands is not None and not _df_brands.empty:
        brands = sorted([b for b in _df_brands['name'].dropna().unique() if b])
    else:
        brands = sorted([b for b in _df_order['name'].dropna().unique() if b])
    
    return {
        "brands": brands,
        "outlets": sorted([o for o in _df_outlet['outlet_name'].dropna().unique() if o]),
        "owners": sorted([o for o in _df_outlet['owner_name'].dropna().unique() if o]),
        "sources": sorted([s for s in _df_order['order_source'].dropna().unique() if s]),
        "statuses": sorted(list(set(format_status(s) for s in _df_order['status'].dropna().unique() if s)))}

filter_options = get_filter_options(df_order, df_outlet, df_brands)


# FUNGSI UNTUK AMBIL OUTLET METRIC TREND BUAT CHART
@st.cache_data
def get_outlet_trend_metrics(df_outlet, df_order, start_date, end_date, granularity):
    df_outlet['go_live'] = pd.to_datetime(df_outlet['go_live'], errors='coerce')
    df_outlet['outlet_deleted_at'] = pd.to_datetime(df_outlet['outlet_deleted_at'], errors='coerce')
    df_order['order_date'] = pd.to_datetime(df_order['order_date'], errors='coerce')

    trend_data = []

    # periode
    if granularity == 'daily':
        period_range = pd.date_range(start=start_date, end=end_date, freq='D')
    elif granularity == 'weekly':
        period_range = pd.date_range(start=start_date, end=end_date, freq='7D')
    else:  # monthly
        period_range = pd.period_range(start=start_date, end=end_date, freq='M').to_timestamp('s')

    for p_timestamp in period_range:
        if granularity == 'daily':
            current_start = current_end = p_timestamp.date()
            period_str = p_timestamp.strftime('%Y-%m-%d')
        elif granularity == 'weekly':
            current_start = p_timestamp.date()
            current_end = current_start + pd.Timedelta(days=6)
            period_str = f"{current_start} - {current_end}"
        else:  # monthly
            current_start = p_timestamp.date().replace(day=1)
            current_end = (p_timestamp.date().replace(day=28) + pd.Timedelta(days=4)).replace(day=1) - pd.Timedelta(days=1)
            period_str = p_timestamp.strftime('%Y-%m')

        # outlet aktif di periode ini
        active_outlets = df_outlet[
            (df_outlet['go_live'].dt.date <= current_end) & 
            (df_outlet['outlet_deleted_at'].isna() | (df_outlet['outlet_deleted_at'].dt.date > current_end))
        ]['outlet_id'].unique()

        # outlet yang ada order = produktif (ini blm kepake)
        productive_outlets = df_order[
            (df_order['order_date'].dt.date >= current_start) &
            (df_order['order_date'].dt.date <= current_end)
        ]['outlet_id'].unique()

        num_active = len(set(active_outlets))
        num_inactive = len(set(df_outlet['outlet_id']) - set(active_outlets))

        # avg activation days
        avg_activation_days = df_outlet[
            (df_outlet['go_live'].dt.date <= current_end) & 
            (df_outlet['outlet_deleted_at'].isna() | (df_outlet['outlet_deleted_at'].dt.date > current_end))
        ]['outlet_activation_time_days'].mean()
        if pd.isna(avg_activation_days):
            avg_activation_days = 0

        current_activated_outlets_df = df_outlet[
            (df_outlet['go_live'].dt.date >= current_start) &
            (df_outlet['go_live'].dt.date <= current_end)]
        
        current_avg_activation_days = current_activated_outlets_df['outlet_activation_time_days'].mean()
        if pd.isna(current_avg_activation_days):
            current_avg_activation_days = 0
        
        trend_data.append({
            'period_str': period_str,
            'Active': num_active,
            'Inactive': num_inactive,
            'avg_activation_days': avg_activation_days, #ini ga dipake (tapi siapa tau butuh)
            'current_avg_activation_days': current_avg_activation_days})
    df_trend = pd.DataFrame(trend_data).fillna(0)
    return df_trend

def calculate_growth(current, prev):
                if prev is not None and prev > 0:
                    return (current - prev) / prev * 100
                return 0

# ================================================================= SIDEBAR NAVIGASI =================================================================
with st.sidebar:
    st.image("FINISH - SUPERFOOD-05.png", width=200)

    selected_tab = option_menu(
        menu_title=None,
        options=[
            "Overview",
            "Order Details",
            "Lifecycle & Status",
            "Menu Performance",
            "Location",
            "Forecasting"],
        icons=[
            "bar-chart-line",
            "cart",
            "shop",
            "grid",
            "geo-alt",
            "graph-up-arrow"],
        default_index=0,
        styles={
            "container": {
                "padding": "0px !important",  
                "margin": "0px !important", 
                "border-radius": "0px",       
                "background-color": "#FFFFFF", 
                "width": "100%",},
            "icon": {
                "font-size": "14px",},
            "nav-link": {
                "font-size": "14px",
                "text-align": "left",
                "--hover-color": "#F0F2F6",},
            "nav-link-selected": {
                "background-color": "#fee2e2",
                "color": "#E53935",
                "font-weight": "530",},
        })
    

# ========================== FILTER HALAMAN UTAMA ==========================
FINANCIAL_STATUSES = ('wc-disbursement-completed', 'wc-completed', 'wc-disbursement-progress')
TOTAL_ORDER_COUNT_STATUSES = ('wc-disbursement-completed', 'wc-disbursement-progress', 'wc-completed', 'wc-processing', 'wc-cancelled')


if selected_tab != "Forecasting":
    st.markdown("##### Filter 🔍")
    col_date, col, col_outlet, col_owner, col_brand, col_source = st.columns([2, 1.6, 1.5, 1.5, 1, 1])

    with col_date:
        if not df_order.empty:
            min_date = df_order['order_date'].min().date()
            max_date = df_order['order_date'].max().date()
            date_range_val = st.date_input(
                "Date Range",
                value=(max_date - timedelta(days=7), max_date),
                min_value=min_date,
                max_value=max_date,
                key="overview_date"
            )
        else:
            date_range_val = st.date_input(
                "Date Range",
                value=(date.today() - timedelta(days=7), date.today()),
                key="overview_date_empty"
            )

    with col_brand:
        selected_brands = st.multiselect(
            "Virtual Brand",
            options=['All'] + filter_options.get('brands', []),
            default=['All'],
            key="overview_brands"
        )

    with col_source:
        selected_order_sources = st.multiselect(
            "Channel (OFD)",
            options=['All'] + filter_options.get('sources', []),
            default=['All'],
            key="overview_sources"
        )

    with col_outlet:
        selected_outlets = st.multiselect(
            "Outlet",
            options=['All'] + filter_options.get('outlets', []),
            default=['All'],
            key="overview_outlets"
        )

    with col_owner:
        selected_owners = st.multiselect(
            "Owner Name",
            options=['All'] + filter_options.get('owners', []),
            default=['All'],
            key="overview_owners"
        )


# ========================== Calculation ============================

    df_filtered_order = pd.DataFrame()
    df_filtered_outlet = pd.DataFrame()
    df_orders_filtered = pd.DataFrame()
    df_financial_base = pd.DataFrame()
    df_order_count_base = pd.DataFrame()

    total_gmv, total_gross_revenue, total_orders = 0, 0, 0
    active_outlets = 0
    gmv_growth, gross_revenue_growth, orders_growth = 0, 0, 0
    active_outlets_growth = 0

    if not df_order.empty:
        start_date_filter, end_date_filter = date_range_val if len(date_range_val) == 2 else (date.today() - timedelta(days=7), date.today())
        
        if not df_outlet.empty:
            df_outlet['go_live'] = pd.to_datetime(df_outlet['go_live'])
            
            active_outlets = df_outlet[
                df_outlet['go_live'].dt.date <= end_date_filter]['outlet_id'].nunique()
        else:
            active_outlets = 0
        
        delta = end_date_filter - start_date_filter
        start_date_prev = start_date_filter - delta
        end_date_prev = start_date_filter - timedelta(days=1)
        
        df_filtered_order = df_order[(df_order['order_date'].dt.date >= start_date_filter) & (df_order['order_date'].dt.date <= end_date_filter)].copy()
        
        df_filtered_order_prev = df_order[(df_order['order_date'].dt.date >= start_date_prev) & (df_order['order_date'].dt.date <= end_date_prev)].copy()
        
        if 'All' not in selected_brands: 
            df_filtered_order = df_filtered_order[df_filtered_order['brand_name'].isin(selected_brands)]
            df_filtered_order_prev = df_filtered_order_prev[df_filtered_order_prev['brand_name'].isin(selected_brands)]
        if 'All' not in selected_order_sources: 
            df_filtered_order = df_filtered_order[df_filtered_order['order_source'].isin(selected_order_sources)]
            df_filtered_order_prev = df_filtered_order_prev[df_filtered_order_prev['order_source'].isin(selected_order_sources)]
        
        # Merge order data with outlet data to filter by selected outlets/owners
        if not df_outlet.empty:
            df_outlet['go_live'] = pd.to_datetime(df_outlet['go_live'], errors='coerce')

            df_merged = pd.merge(df_filtered_order, df_outlet, on='outlet_id', how='left', suffixes=('_order', '_outlet'))
            df_merged_prev = pd.merge(df_filtered_order_prev, df_outlet, on='outlet_id', how='left', suffixes=('_order', '_outlet'))

            if 'All' not in selected_outlets: 
                df_merged = df_merged[df_merged['outlet_name_outlet'].isin(selected_outlets)]
                df_merged_prev = df_merged_prev[df_merged_prev['outlet_name_outlet'].isin(selected_outlets)]
            if 'All' not in selected_owners:
                df_merged = df_merged[df_merged['owner_name_outlet'].isin(selected_owners)]
                df_merged_prev = df_merged_prev[df_merged_prev['owner_name_outlet'].isin(selected_owners)]
            
            df_filtered_order = df_merged.copy()
            df_filtered_order_prev = df_merged_prev.copy()
            
            active_outlets = df_outlet[
                (df_outlet['go_live'].dt.date <= end_date_filter) &
                (df_outlet['outlet_deleted_at'].isna() | (df_outlet['outlet_deleted_at'].dt.date > end_date_filter))
            ]['outlet_id'].nunique()
            
            active_outlets_prev = df_outlet[
                (df_outlet['go_live'].dt.date <= end_date_prev) &
                (df_outlet['outlet_deleted_at'].isna() | (df_outlet['outlet_deleted_at'].dt.date > end_date_prev))
            ]['outlet_id'].nunique()
            active_outlets_growth = ((active_outlets - active_outlets_prev) / active_outlets_prev * 100) if active_outlets_prev > 0 else 0
            productive_outlets = df_filtered_order['outlet_id'].nunique()
            productive_outlets_prev = df_filtered_order_prev['outlet_id'].nunique()

    df_orders_filtered = df_filtered_order.drop_duplicates(subset=['order_id']).copy()
    df_orders_filtered_prev = df_filtered_order_prev.drop_duplicates(subset=['order_id']).copy()

    df_items_filtered = df_filtered_order.copy()
    df_items_filtered_prev = df_filtered_order_prev.copy()
        
    # calculation all metric in overview tab
    if not df_orders_filtered.empty:
        FINANCIAL_STATUSES = ('wc-disbursement-completed', 'wc-completed', 'wc-disbursement-progress')
        TOTAL_ORDER_COUNT_STATUSES = ('wc-disbursement-completed', 'wc-disbursement-progress', 'wc-completed', 'wc-processing', 'wc-cancelled')

        df_financial_base = df_orders_filtered[df_orders_filtered['status'].isin(FINANCIAL_STATUSES)] 
        df_order_count_base = df_orders_filtered[df_orders_filtered['status'].isin(TOTAL_ORDER_COUNT_STATUSES)] 
        df_outlet_filtered = df_outlet.copy()
        if 'All' not in selected_outlets:
            df_outlet_filtered = df_outlet_filtered[df_outlet_filtered['outlet_name'].isin(selected_outlets)]
        if 'All' not in selected_owners:
            df_outlet_filtered = df_outlet_filtered[df_outlet_filtered['owner_name'].isin(selected_owners)]

        df_outlet_filtered['avg_rating'] = df_outlet_filtered['avg_rating'].fillna(df_outlet_filtered['avg_rating_global'])


        total_gmv = df_financial_base['gmv_order'].sum()
        total_cogs = df_financial_base['cogs_order'].sum()
        
        total_gross_revenue = df_financial_base['gross_revenue_order'].sum()
        total_orders = df_order_count_base['order_id'].nunique()
        total_orders_success = df_financial_base['order_id'].nunique() #total order success ('wc-disbursement-completed', 'wc-completed', 'wc-disbursement-progress')
        productive_outlets = df_financial_base['outlet_id'].nunique()
        success_order_count = df_orders_filtered[df_orders_filtered['status'].isin(['wc-completed', 'wc-disbursement-completed', 'wc-disbursement-progress'])]['order_id'].nunique()
        success_ratio = (success_order_count / total_orders * 100) if total_orders > 0 else 0.0
        avg_order_value = total_gross_revenue / success_order_count if success_order_count > 0 else 0 

        df_orders_filtered['order_date'] = pd.to_datetime(df_orders_filtered['order_date'], errors='coerce')
        df_orders_filtered['order_month'] = df_orders_filtered['order_date'].dt.to_period('M')

        order_counts = (df_orders_filtered.groupby(['customer_id', 'order_month'])['order_id'].nunique().reset_index(name='order_count'))

        repeat_customers = order_counts[order_counts['order_count'] >= 2]['customer_id'].nunique()
        total_customers = order_counts['customer_id'].nunique()
        same_month_repeat_rate = (repeat_customers / total_customers * 100) if total_customers > 0 else 0.0
        avg_rating = df_outlet_filtered['avg_rating'].mean().round(2)
        
        
    if not df_orders_filtered_prev.empty:
        df_financial_base_prev = df_orders_filtered_prev[df_orders_filtered_prev['status'].isin(FINANCIAL_STATUSES)] 
        df_order_count_base_prev = df_orders_filtered_prev[df_orders_filtered_prev['status'].isin(TOTAL_ORDER_COUNT_STATUSES)] 
        total_gmv_prev = df_financial_base_prev['gmv_order'].sum()
        total_gross_revenue_prev = df_financial_base_prev['gross_revenue_order'].sum()
        
        total_orders_prev = df_order_count_base_prev['order_id'].nunique()
        success_order_count_prev = df_financial_base_prev['order_id'].nunique()
        avg_order_value_prev = total_gross_revenue_prev / success_order_count_prev if success_order_count_prev > 0 else 0
        
        success_ratio_prev = (success_order_count_prev / total_orders_prev * 100) if total_orders_prev > 0 else 0.0
        df_orders_filtered_prev['order_date'] = pd.to_datetime(df_orders_filtered_prev['order_date'], errors='coerce')
        df_orders_filtered_prev['order_month'] = df_orders_filtered_prev['order_date'].dt.to_period('M')

        order_counts_prev = (df_orders_filtered_prev.groupby(['customer_id', 'order_month'])['order_id'].nunique().reset_index(name='order_count'))

        repeat_customers_prev = order_counts_prev[order_counts_prev['order_count'] >= 2]['customer_id'].nunique()
        total_customers_prev = order_counts_prev['customer_id'].nunique()

        same_month_repeat_rate_prev = (repeat_customers_prev / total_customers_prev * 100) if total_customers_prev > 0 else 0.0
            
    # calculation growth
    gmv_growth = ((total_gmv - total_gmv_prev) / total_gmv_prev * 100) if total_gmv_prev > 0 else 0
    gross_revenue_growth = ((total_gross_revenue - total_gross_revenue_prev) / total_gross_revenue_prev * 100) if total_gross_revenue_prev > 0 else 0
    orders_growth = ((total_orders - total_orders_prev) / total_orders_prev * 100) if total_orders_prev > 0 else 0
    aov_growth = ((avg_order_value - avg_order_value_prev) / avg_order_value_prev * 100) if avg_order_value_prev != 0 else 0
    success_order_count_growth = ((success_order_count - success_order_count_prev)/success_order_count_prev * 100) if success_order_count_prev > 0 else 0
    success_ratio_growth = ((success_ratio - success_ratio_prev) / success_ratio_prev * 100) if success_ratio_prev != 0 else 0
    same_month_repeat_rate_growth = ((same_month_repeat_rate - same_month_repeat_rate_prev) / same_month_repeat_rate_prev * 100) if same_month_repeat_rate_prev != 0 else 0

    # status breakdown
    status_breakdown = df_order_count_base['status'].value_counts()
    completed_count = status_breakdown.get('wc-completed', 0)
    disbursement_completed_count = status_breakdown.get('wc-disbursement-completed', 0)
    disbursement_progress_count = status_breakdown.get('wc-disbursement-progress', 0)
    processing_count = status_breakdown.get('wc-processing', 0)
    cancelled_count = status_breakdown.get('wc-cancelled', 0)

    help_text = f"""Order Status Breakdown:
    - Completed: {completed_count:,}
    - Disbursement Completed: {disbursement_completed_count:,}
    - Disbursement Progress: {disbursement_progress_count:,}
    - Processing: {processing_count:,}
    - Cancelled: {cancelled_count:,}

    Total Success Orders: {success_order_count:,}"""    



    # overview tab
    if selected_tab == "Overview":
        st.subheader("Overview")

        kpi_cols = st.columns(4)
        with kpi_cols[0]:
            st.metric("Gross Merchandise Value (GMV)", f"Rp {total_gmv:,.0f}", delta=f"{gmv_growth:,.1f}% From last month", help="Total Gross Merchandise Value")
        with kpi_cols[1]:
            st.metric("Total Gross Revenue", f"Rp {total_gross_revenue:,.0f}", delta=f"{gross_revenue_growth:,.1f}% From last month", help="GMV-COGS")
        with kpi_cols[2]:
            st.metric("Total Orders", f"{total_orders:,.0f}", delta=f"{orders_growth:,.1f}% From last month", help=help_text)
        with kpi_cols[3]:
            st.metric("Average Order Value (AOV)", f"Rp {avg_order_value:,.0f}", delta=f"{aov_growth:.1f}% From last month", help="Nilai rata-rata transaksi per order.")

        st.write("---")
        col1, col2, col3 = st.columns([10, 2, 1.5])
        with col3:
            financial_selection = st.selectbox("View Trend By:", ("Monthly", "Weekly", "Daily"))
            granularity_for_query = financial_selection.lower()
        with col1:
            selected_metric_to_plot = st.segmented_control("Show Trend For:", options=["Gross Merchandise Value","Gross Revenue", "Total Orders", "Average Order Value"], 
                                                            default= "Gross Merchandise Value", key="financial_trend_control")
        with col2:
            trend_view = st.selectbox("View Chart By:", ("General", "Platform (OFD)"))
            
        # data trend for overview tab chart
        df_trend_source = df_financial_base.copy()
        df_trend_source['aov'] = df_trend_source['gross_revenue_order'] / df_trend_source.groupby('order_date')['order_id'].transform('nunique')
        df_trend_source["platform"] = df_trend_source["order_source"].map({
            "grabfood": "GrabFood",
            "shopeefood": "ShopeeFood",
            "gofood": "GoFood"})

        if granularity_for_query == 'daily':
            df_trend_source['period_str'] = df_trend_source['order_date'].dt.strftime('%Y-%m-%d')
        elif granularity_for_query == 'weekly':
            df_trend_source['period_str'] = df_trend_source['order_date'].dt.to_period('W').apply(lambda r: r.start_time.strftime('%Y-%m-%d'))
        else: 
            df_trend_source['period_str'] = df_trend_source['order_date'].dt.to_period('M').astype(str)

        if trend_view == "General":
            df_trend = df_trend_source.groupby('period_str').agg(
                gmv=('gmv_order', 'sum'),
                gross_revenue=('gross_revenue_order', 'sum'),
                orders=('order_id', 'nunique'),
                aov=('aov', 'mean')).reset_index()

        else:  
            df_trend = df_trend_source.groupby(['period_str', 'platform']).agg(
                gmv=('gmv_order', 'sum'),
                gross_revenue=('gross_revenue_order', 'sum'),
                orders=('order_id', 'nunique'),
                aov=('aov', 'mean')).reset_index()
            df_trend = df_trend.sort_values(by=['platform', 'period_str'])
            
        if trend_view == "Platform (OFD)":
            platform_colors = {
                "GrabFood": "#00B14F",
                "ShopeeFood": "#EE4D2D",
                "GoFood": "#D50000"}

            all_platforms = ["GrabFood", "ShopeeFood", "GoFood"]
            all_periods = sorted(df_trend_source["period_str"].unique())

            full_frame = (
                pd.MultiIndex.from_product(
                    [all_periods, all_platforms],
                    names=["period_str", "platform"])
                .to_frame(index=False))

            df_trend = full_frame.merge(df_trend, on=["period_str", "platform"], how="left")
            df_trend = df_trend.fillna({
                "gmv": 0,
                "gross_revenue": 0,
                "orders": 0,
                "aov": 0})

        plot_mapping = {
            "Gross Merchandise Value": ("gmv", "GMV Growth", total_gmv, gmv_growth),
            "Gross Revenue": ("gross_revenue", "Gross Revenue Growth", total_gross_revenue, gross_revenue_growth),
            "Total Orders": ("orders", "Total Orders", total_orders, orders_growth),
            "Average Order Value": ("aov", "Average Order Value Growth", avg_order_value, aov_growth)}

        y_axis, title, display_value, growth_value = plot_mapping.get(
            selected_metric_to_plot, 
            ("gmv_order", "GMV Growth", total_gmv, gmv_growth))

        is_currency_metric = selected_metric_to_plot in ["Gross Merchandise Value", "Gross Revenue", "Average Order Value"]
        currency_prefix = "Rp " if is_currency_metric else ""

        color = "green" if growth_value >= 0 else "red"
        arrow = "↑" if growth_value >= 0 else "↓"

        st.markdown(f"""
            <div style="font-size:24px; font-weight:600;">Total {selected_metric_to_plot}</div>
            <div style="display:flex; align-items:center; gap:16px;">
                <div style="font-size:32px; font-weight:700;">{currency_prefix}{display_value:,.0f}</div>
                <div style="font-size:16px; color:{color};">
                    {arrow} {growth_value:,.1f}% from last period
                </div>
            </div>
        """, unsafe_allow_html=True)

        if not df_trend.empty:
            if trend_view == "General":
                fig = px.line(
                    df_trend,
                    x='period_str',
                    y=y_axis,
                    title=title,
                    labels={'period_str': financial_selection, y_axis: selected_metric_to_plot},
                    markers=True)
            else:
                fig = px.line(
                    df_trend,
                    x='period_str',
                    y=y_axis,
                    color='platform', 
                    title=title + " by Platform",
                    labels={'period_str': financial_selection, y_axis: selected_metric_to_plot},
                    markers=True,
                    color_discrete_map=platform_colors )

            if any(keyword in selected_metric_to_plot for keyword in ["Gross Merchandise Value", "Gross Revenue", "Average Order Value"]):
                fig.update_yaxes(tickprefix="Rp ", tickformat=",.0f")
        else:
            st.info("No trend data available for the selected filters.")
            fig = None

            
        if fig is not None:
            fig.update_layout(
                margin=dict(t=60, l=40, r=190, b=25),
                autosize=True,
                width=None,
                xaxis_title=None,
                yaxis_title=None,
                hovermode="x unified",
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)')
            if trend_view == "General":
                fig.update_traces(line_color='#FF4B4B') 
                fig.update_layout(
                margin=dict(t=60, l=40, r=80, b=25))

            st.plotly_chart(fig, use_container_width=True)

        #top 10 outlet by gmv
        st.write("---")
        if not df_financial_base.empty and not df_outlet.empty:
            df_financial_base_merged = pd.merge(
                df_financial_base,
                df_outlet[['outlet_id', 'outlet_name', 'owner_name']],
                on='outlet_id',
                how='left')

            top_outlets = df_financial_base_merged.groupby(['outlet_id', 'outlet_name', 'owner_name'])['gmv_order'].sum().reset_index()
            top_outlets = top_outlets.sort_values(by='gmv_order', ascending=False).head(10)  # Top 10

            st.subheader("🏆 Top Outlets by GMV")

            for idx, (_, row) in enumerate(top_outlets.iterrows(), start=1):
                outlet_name = row['outlet_name']
                owner_name = row['owner_name']
                gmv_value = row['gmv_order']

                if idx == 1:
                    medal = "🥇"
                elif idx == 2:
                    medal = "🥈"
                elif idx == 3:
                    medal = "🥉"
                else:
                    medal = ""  

                st.markdown(f"""
                <div style="
                    border:1px solid #ddd; 
                    padding:12px; 
                    margin-bottom:8px; 
                    border-radius:8px;
                    background-color:#f9f9f9;
                    display:flex;
                    justify-content:space-between;
                    align-items:center;
                ">
                    <div>
                        <div style="font-size:16px; font-weight:600;">{medal} {outlet_name}</div>
                        <div style="font-size:14px; color:#555;">Owner: {owner_name}</div>
                    </div>
                    <div style="font-size:17px; font-weight:600;">Rp {gmv_value:,.0f}</div>
                </div>
                """, unsafe_allow_html=True)
                
    # order tab     
    if selected_tab == "Order Details":
        st.subheader("Order Details")
        
        kpi_order_cols = st.columns(5)
        kpi_order_cols[0].metric("Total Order Success", f"{success_order_count}", delta=f"{success_order_count_growth:.1f}% From last month", help=f"{help_text}")
        kpi_order_cols[1].metric("Success Order Ratio", f"{success_ratio:.1f}%", delta=f"{success_ratio_growth:.1f}% From last month",help="Total order success (completed, disbursement completed, and disbursement progress) divide total orders.")
        kpi_order_cols[2].metric("Same-Month 2x Repeat",f"{same_month_repeat_rate:.1f}%", delta=f"{same_month_repeat_rate_growth:.1f}% From last month",help="Percentage of customers who made ≥2 orders in the same month.")
        kpi_order_cols[3].metric("Average Order Value", f"Rp {avg_order_value:,.0f}", delta=f"{aov_growth:.1f}% From last month", help="Nilai rata-rata transaksi per order.")
        kpi_order_cols[4].metric("Average Rating", f"⭐ {avg_rating}", delta=f"0% From last month", help="Average customer rating.")
        
        st.write("---")
        col1, col2 = st.columns([7, 1])
        with col1:
            selected_metric_to_plot_outlet = st.segmented_control("Show Trend For:", 
                options=["Total Orders", "Same Month 2x Repeat", "Average Order Value"], 
                default="Total Orders",
                key="order_trend_control")
        with col2:
            order_granularity_selection = st.selectbox(
                "View Trend By:", ("Monthly", "Weekly", "Daily"),
                key="order_granularity")
        
        if order_granularity_selection == 'Monthly':
            period_range = pd.period_range(start=start_date_filter, end=end_date_filter, freq='M')
            all_periods = pd.DataFrame({'period_str': period_range.astype(str)})
        elif order_granularity_selection == 'Weekly':
            period_range = pd.date_range(start=start_date_filter, end=end_date_filter, freq='W-MON')  
            all_periods = pd.DataFrame({'period_str': period_range.strftime('%Y-%m-%d')})
        else:  # daily
            period_range = pd.date_range(start=start_date_filter, end=end_date_filter, freq='D')
            all_periods = pd.DataFrame({'period_str': period_range.strftime('%Y-%m-%d')})

        df_trend_source2 = df_financial_base.copy()
        df_trend_source2['order_date'] = pd.to_datetime(df_trend_source2['order_date'], errors='coerce')

        if order_granularity_selection == 'Daily':
            df_trend_source2['period_str'] = df_trend_source2['order_date'].dt.strftime('%Y-%m-%d')
        elif order_granularity_selection == 'Weekly':
            df_trend_source2['period_str'] = df_trend_source2['order_date'].dt.to_period('W').apply(lambda r: r.start_time.strftime('%Y-%m-%d'))
        else:  # monthly
            df_trend_source2['period_str'] = df_trend_source2['order_date'].dt.to_period('M').astype(str)

        if selected_metric_to_plot_outlet == "Average Order Value":
            color = "green" if aov_growth >= 0 else "red"
            arrow = "↑" if aov_growth >= 0 else "↓"
            st.markdown(f"""
                        <div style="font-size:24px; font-weight:600;">Average Order Value</div>
                        <div style="display:flex; align-items:center; gap:16px;">
                            <div style="font-size:32px; font-weight:700;">Rp {avg_order_value:,.0f}</div>
                            <div style="font-size:16px; color:{color};">
                                {arrow} {aov_growth:,.1f}% From last month
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
            df_agg = df_trend_source2.groupby('period_str').agg(
                gross_revenue=('gross_revenue_order', 'sum'),
                orders=('order_id', 'nunique')).reset_index()
            df_agg['aov'] = df_agg['gross_revenue'] / df_agg['orders'].replace(0, 1)
            y_col = 'aov'
            title = "Average Order Value"
        elif selected_metric_to_plot_outlet == "Total Orders":
            color = "green" if success_order_count_growth >= 0 else "red"
            arrow = "↑" if success_order_count_growth >= 0 else "↓"
            st.markdown(f"""
                        <div style="font-size:24px; font-weight:600;">Total Order Success</div>
                        <div style="display:flex; align-items:center; gap:16px;">
                            <div style="font-size:32px; font-weight:700;">{success_order_count}</div>
                            <div style="font-size:16px; color:{color};">
                                {arrow} {success_order_count_growth:,.1f}% From last month
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
            df_agg = df_trend_source2.groupby('period_str').agg(orders=('order_id', 'nunique')).reset_index()
            y_col = 'orders'
            title = "Total Orders"
        elif selected_metric_to_plot_outlet == "Same Month 2x Repeat":
            color = "green" if same_month_repeat_rate_growth >= 0 else "red"
            arrow = "↑" if same_month_repeat_rate_growth >= 0 else "↓"
            st.markdown(f"""
                        <div style="font-size:24px; font-weight:600;">Same Month 2x Repeat</div>
                        <div style="display:flex; align-items:center; gap:16px;">
                            <div style="font-size:32px; font-weight:700;">{same_month_repeat_rate:,.1f}%</div>
                            <div style="font-size:16px; color:{color};">
                                {arrow} {same_month_repeat_rate_growth:,.1f}% From last month
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
            order_counts = df_trend_source2.groupby(['customer_id', 'period_str'])['order_id'].nunique().reset_index(name='order_count')
            repeat_counts = order_counts.groupby('period_str').apply(lambda x: (x['order_count']>=2).sum()).reset_index(name='repeat_customers')
            total_customers = order_counts.groupby('period_str')['customer_id'].nunique().reset_index(name='total_customers')
            df_agg = pd.merge(repeat_counts, total_customers, on='period_str', how='left')
            df_agg['repeat_rate'] = df_agg['repeat_customers'] / df_agg['total_customers'].replace(0, 1) * 100
            y_col = 'repeat_rate'
            title = "Same Month 2x Repeat Rate (%)"

        df_trend2 = pd.merge(all_periods, df_agg, on='period_str', how='left').fillna(0)
        df_trend2 = df_trend2.sort_values('period_str').reset_index(drop=True)

        if not df_trend2.empty and y_col in df_trend2.columns:
            fig = px.line(
                df_trend2, 
                x='period_str', 
                y=y_col, 
                title=title, 
                labels={'period_str': 'Period', y_col: title},
                markers=True)
            if selected_metric_to_plot_outlet in ["Average Order Value", "Total Orders"]:
                fig.update_yaxes(tickprefix="Rp " if selected_metric_to_plot_outlet=="Average Order Value" else "", tickformat=",.0f")
            fig.update_layout(margin=dict(t=60, l=40, r=80, b=25), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
            fig.update_traces(line_color='#FF4B4B')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(f"No data for {title} trend.")
        
        st.write("---")
        col1, col2, col3, col4 = st.columns([6.5, 1.5, 3, 1])
        with col1:
            st.markdown(f"""
            <div style="font-size:24px; font-weight:600;">Success Order Ratio</div>
            <div style="display:flex; align-items:center; gap:16px;">
                <div style="font-size:32px; font-weight:700;">{success_ratio:.1f}%</div>
                <div style="font-size:16px; color:{color};">
                    {arrow} {success_ratio_growth:.1f}% From last month
                </div>
            </div>
        """, unsafe_allow_html=True)

        with col2:
            order_granularity_selection2 = st.selectbox(
                "View Trend By:", ("Monthly", "Weekly", "Daily"),
                key="order_granularity2")
        
        if order_granularity_selection2 == 'Daily':
            period_format = '%Y-%m-%d'
        elif order_granularity_selection2 == 'Weekly':
            period_format = '%Y-%m-%d' 
        else:
            period_format = '%Y-%m'

        df_trend_ratio = df_orders_filtered.copy()
        success_statuses = ['wc-completed', 'wc-disbursement-completed', 'wc-disbursement-progress']
        cancelled_status = 'wc-cancelled'
        other_statuses = 'wc-processing'
        
        df_trend_ratio['status_group'] = df_trend_ratio['status'].apply(
            lambda x: 'Success' if x in success_statuses 
            else ('Cancelled' if x == cancelled_status 
            else ('Processing' if x in other_statuses else None)))
        df_trend_ratio.dropna(subset=['status_group'], inplace=True)
        
        if order_granularity_selection2 == 'Daily':
            df_trend_ratio['period_str'] = df_trend_ratio['order_date'].dt.strftime('%Y-%m-%d')
        elif order_granularity_selection2 == 'Weekly':
            df_trend_ratio['period_str'] = df_trend_ratio['order_date'].dt.to_period('W').apply(
                lambda r: r.start_time.strftime('%Y-%m-%d'))
        else:  
            df_trend_ratio['period_str'] = df_trend_ratio['order_date'].dt.to_period('M').astype(str)

        df_trend_data = df_trend_ratio.groupby(['period_str', 'status_group']).agg(
            order_count=('order_id', 'nunique')).reset_index()
        
        #order time
        df_orders_filtered['order_hour'] = df_orders_filtered['order_date'].dt.hour
        def get_time_slot(hour):
            if 6 <= hour < 12:
                return 'Morning (06:00-11:59)'
            elif 12 <= hour < 18:
                return 'Afternoon (12:00-17:59)'
            else:
                return 'Night (18:00-05:59)'

        df_orders_filtered['time_slot'] = df_orders_filtered['order_hour'].apply(get_time_slot)

        df_time_slot = df_orders_filtered.groupby('time_slot')['order_id'].nunique().reset_index(name='Total Orders')
        
        order_list = ['Morning (06:00-11:59)', 'Afternoon (12:00-17:59)', 'Night (18:00-05:59)']
        df_time_slot['time_slot'] = pd.Categorical(df_time_slot['time_slot'], categories=order_list, ordered=True)
        df_time_slot = df_time_slot.sort_values('time_slot')
        
        df_time_slot['time_slot_clean'] = df_time_slot['time_slot'].replace({
            'Morning (06:00-11:59)': 'Morning',
            'Afternoon (12:00-17:59)': 'Afternoon',
            'Night (18:00-05:59)': 'Night'})

        if not df_trend_data.empty:
            col1, col2 = st.columns([2, 1])
            with col1:
                fig_bar = px.bar(
                    df_trend_data,
                    x='period_str',
                    y='order_count',
                    color='status_group',
                    title='Success vs. Cancelled Orders Ratio',
                    labels={'order_count': 'Total Orders', 'period_str': 'Period', 'status_group':'Status'},
                    color_discrete_map={'Success': '#87d499', 'Cancelled': '#fa7878', 'Processing':'#ede891'})
                fig_bar.update_layout(barmode='stack', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(t=60, l=80, r=160, b=25))
                fig_bar.update_traces(textposition='inside', insidetextfont_color='white')
                st.plotly_chart(fig_bar, use_container_width=True)
            
            with col2:
                fig_donut_time = px.pie(
                    df_time_slot,
                    values='Total Orders',
                    names='time_slot',
                    color='time_slot_clean',
                    color_discrete_sequence=px.colors.qualitative.Pastel1, 
                    hole=0.4, 
                    labels={'Total Orders': 'Total Orders', 'time_slot': 'Slot Waktu'})
                
                fig_donut_time.update_traces(textinfo='none', 
                                            hovertemplate="<b>%{label}</b><br>" +
                                                        "Total Order: %{value:,.0f}<br>" +
                                                        "Precentage: %{percent}<extra></extra>")
                
                fig_donut_time.update_layout(
                    margin=dict(t=70, l=20, r=200, b=30), 
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    title='Order Time by Value') 
                    
                st.plotly_chart(fig_donut_time, use_container_width=True)

        else:
            st.info("Tidak ada data pesanan yang tersedia untuk rentang waktu ini.")
            

    # lifecycle tab  
    if selected_tab == "Lifecycle & Status":
        st.subheader("Lifecycle & Status")
        outlet_performance_data = get_outlet_performance_metrics(start_date_filter, end_date_filter)
        outlet_performance_data_prev = get_outlet_performance_metrics(start_date_prev, end_date_prev)
        
        df_outlet_current = df_outlet[
            (df_outlet['go_live'].dt.date >= start_date_filter) &
            (df_outlet['go_live'].dt.date <= end_date_filter)]
        df_outlet_prev = df_outlet[
            (df_outlet['go_live'].dt.date >= start_date_prev) &
            (df_outlet['go_live'].dt.date <= end_date_prev)]
        
        ret_rate = outlet_performance_data.get('retention_rate')
        churn_rate = 1 - ret_rate
        avg_act_time = df_outlet_current['outlet_activation_time_days'].mean()
        
        # ini pakai cumulative active outlet
        total_outlet = df_outlet['outlet_id'].nunique()
        active_inactive = (active_outlets/total_outlet * 100) if total_outlet > 0 else 0
        df_ratio = get_open_closed_ratio_working(start_date_filter, end_date_filter)
        open_close_ratio = df_ratio["open_closed_ratio"].mean()
        df_ratio_prev = get_open_closed_ratio_working(start_date_prev, end_date_prev)
        open_close_ratio_prev = df_ratio_prev["open_closed_ratio"].mean()

        #ini untuk previous
        active_outlets_prev = df_outlet[
            (df_outlet['go_live'].dt.date <= end_date_prev) &
            ((df_outlet['outlet_deleted_at'].isna()) | (df_outlet['outlet_deleted_at'].dt.date > end_date_prev))]['outlet_id'].nunique()
        
        active_inactive_prev = (active_outlets_prev / total_outlet * 100) if total_outlet > 0 else 0
        ret_rate_prev = outlet_performance_data_prev.get('retention_rate')
        if ret_rate_prev is not None:
            churn_rate_prev = 1 - ret_rate_prev
        else:
            churn_rate_prev = None
        # churn_rate_prev = 1 - ret_rate_prev
        avg_act_time_prev = df_outlet_prev['outlet_activation_time_days'].mean()

        # calculate growth
        active_inactive_growth = calculate_growth(active_inactive, active_inactive_prev)
        ret_rate_growth = calculate_growth(ret_rate, ret_rate_prev)
        churn_rate_growth = calculate_growth(churn_rate, churn_rate_prev)
        avg_act_time_growth = calculate_growth(avg_act_time, avg_act_time_prev) 
        open_close_ratio_growth = calculate_growth(open_close_ratio, open_close_ratio_prev)
        
        ret_rate_display = f"{ret_rate:.1%}" if ret_rate is not None else "0.00%"
        avg_act_time_display = f"{avg_act_time:.1f} Days" if not pd.isna(avg_act_time) else "0 Days"
        open_close_ratio_display = f"{open_close_ratio:.1f}%" if open_close_ratio > 0 else "0.00%"
        
        productivity_outlets = st.columns(3)
        productivity_outlets[0].metric("Active vs. Inactive", f"{active_inactive:,.1f}%", 
            delta=f"{active_inactive_growth:,.1f}% From last month",
            help="Active outlet = has ≥1 order in the last 1 month.")
        productivity_outlets[1].metric("Retention Rate", ret_rate_display, 
            delta=f"{ret_rate_growth:.1f}% From last month",
            help="Persentase outlet yang tetap aktif per periode.")
        productivity_outlets[2].metric("Churn Rate", f"{churn_rate:.1%}", 
            delta=f"{churn_rate_growth:.1f}% From last month",
            help="Percentage of outlets that ceased activity this month.")
        
        productivity_outlets1 = st.columns(3)
        productivity_outlets[0].metric("Active Outlets", f"{active_outlets:,.0f}", 
            delta=f"{active_outlets_growth:,.1f}% From last month",
            help="Active outlet = has ≥1 order in the last 1 month.")
        productivity_outlets[1].metric("Open vs. Closed Ratio", open_close_ratio_display, 
            delta=f"{open_close_ratio_growth:.1f}% From last month",
            help="Persentase waktu outlet benar-benar beroperasi (uptime).")
        productivity_outlets[2].metric("Average Activation Time", avg_act_time_display, 
            delta=f"{avg_act_time_growth:.1f}% From last month",
            help="Jumlah hari sejak outlet mendaftar hingga outlet go-live")

        st.write("---")
        col1, col2 = st.columns([7, 1])
        with col1:
            selected_metric_to_plot_outlet = st.segmented_control("Show Trend For:", 
                options=["Active vs. Inactive", "Retention vs. Churned", "Open vs. Closed Ratio"], 
                default="Active vs. Inactive",
                key="outlet_trend_control")
        with col2:
            outlet_granularity_selection = st.selectbox(
                "View Trend By:", ("Monthly", "Weekly", "Daily"),
                key="outlet_granularity")
            
        df_outlet_trend_metrics = get_outlet_trend_metrics(df_outlet, df_order, start_date_filter, end_date_filter, outlet_granularity_selection.lower())

        # displayed chart
        if selected_metric_to_plot_outlet == "Active vs. Inactive":
            color = "green" if active_inactive_growth >= 0 else "red"
            arrow = "↑" if active_inactive_growth >= 0 else "↓"

            st.markdown(f"""
                <div style="font-size:24px; font-weight:600;">Active vs. Inactive</div>
                <div style="display:flex; align-items:center; gap:16px;">
                    <div style="font-size:32px; font-weight:700;">{active_inactive:.1f}%</div>
                    <div style="font-size:16px; color:{color};">
                        {arrow} {active_inactive_growth:.1f}% From last month
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            try:
                col1, col2 = st.columns([2, 1])
                with col1:
                    df_plot = df_outlet_trend_metrics.melt(
                        id_vars=['period_str'], 
                        value_vars=['Inactive', 'Active'],
                        var_name='Category',
                        value_name='Count')
                    
                    fig = px.bar(
                        df_plot, 
                        x='period_str', 
                        y='Count', 
                        color='Category',
                        title="Active vs. Inactive Outlets",
                        labels={'period_str': 'Period', 'Count': 'Number of Outlets'},
                        color_discrete_map={'Inactive': '#fa7878', 'Active': '#fcd4d4'})
                    fig.update_layout(barmode='stack', legend_title_text='Outlet Status', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(t=60, l=80, r=160, b=25))
                    fig.update_traces(
                        hovertemplate="<b>%{x}</b><br>" + 
                                    "Status: %{fullData.name}<br>" + 
                                    "Jumlah Outlet: %{y:,.0f}<br>" + 
                                    "<extra></extra>")
                    st.plotly_chart(fig, use_container_width=True)

                with col2:
                    pie_data = df_outlet_trend_metrics.iloc[-1][['Inactive', 'Active']].to_frame().T.melt(var_name='Category', value_name='Count')

                    pie_fig = px.pie(
                        pie_data,
                        values='Count',
                        names='Category',
                        color='Category',
                        color_discrete_map={'Inactive': '#fa7878', 'Active': '#fcd4d4'},
                        labels={'Count': 'Outlet Count', 'Category': 'Status'})
                    pie_fig.update_traces(textinfo='none', hovertemplate="<b>%{label}</b><br>" + "Total Outlet: %{value:,.0f}<br>" + "Percent: %{percent}%<extra></extra>")
                    pie_fig.update_layout(showlegend=True, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(r=140, l=20, t=60, b=0))
                    st.plotly_chart(pie_fig, use_container_width=True)
            except Exception as e:
                st.warning(f"Error: Data tidak mencukupi untuk membuat grafik. {e}")

        elif selected_metric_to_plot_outlet == "Retention vs. Churned":
            color = "green" if ret_rate_growth >= 0 else "red"
            arrow = "↑" if ret_rate_growth >= 0 else "↓"

            st.markdown(f"""
                <div style="font-size:24px; font-weight:600;">Retention vs. Churned</div>
                <div style="display:flex; align-items:center; gap:16px;">
                    <div style="font-size:32px; font-weight:700;">{ret_rate_display}</div>
                    <div style="font-size:16px; color:{color};">
                        {arrow} {ret_rate_growth:.1f}% From last month
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            try:
                df_retention_data = get_outlet_metrics_retention_trend(start_date_filter, end_date_filter, outlet_granularity_selection.lower())
                df_retention_data["date"] = pd.to_datetime(df_retention_data["date"]).dt.strftime(
                    "%Y-%m" if outlet_granularity_selection=="Monthly" else "%Y-%m-%d")
                df_retention_data_monthly = get_outlet_metrics_retention_trend(start_date_filter, end_date_filter, "monthly" )
                
                col1, col2 = st.columns([2, 1])
                with col1:
                    df_plot = df_retention_data.melt(
                        id_vars=['date'], 
                        value_vars=['Churn', 'Retained'],
                        var_name='Category',
                        value_name='Count')
                    
                    fig = px.bar(df_plot, 
                                x='date', 
                                y='Count', 
                                color='Category',
                                title="Retained vs. Churned Outlets",
                                labels={'date': 'Period', 'Count': 'Number of Outlets'},
                                color_discrete_map={'Churn': '#fa7878','Retained': '#fcd4d4'})
                    fig.update_layout(barmode='stack', legend_title_text='Retention Status', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(t=60, l=80, r=150, b=25))
                    fig.update_traces(hovertemplate="<b>%{x}</b><br>" + "Status: %{fullData.name}<br>" + "Jumlah Outlet: %{y:,.0f}<br>" + "<extra></extra>")
                    st.plotly_chart(fig, use_container_width=True)

                with col2:
                    pie_data = df_retention_data_monthly.iloc[-1][['Retained', 'Churn']].to_frame().T.melt(var_name='Category', value_name='Count')
                    
                    pie_fig = px.pie(
                        pie_data,
                        values='Count',
                        names='Category',
                        color='Category',
                        color_discrete_map={'Retained': '#fcd4d4', 'Churn': '#fa7878'},
                        labels={'Count': 'Outlet Count', 'Category': 'Status'})
                    pie_fig.update_traces(textinfo='none', hovertemplate="<b>%{label}</b><br>" + "Total Outlet: %{value:,.0f}<br>" + "Percent: %{percent}<extra></extra>")
                    pie_fig.update_layout(showlegend=True, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(r=140, l=20, t=60, b=0))
                    st.plotly_chart(pie_fig, use_container_width=True)

            except Exception as e:
                st.warning(f"Error: Data retensi tidak tersedia. Pastikan fungsi ETL mengembalikan data yang benar. Pesan: {e}")    
        
        elif selected_metric_to_plot_outlet == "Open vs. Closed Ratio":
            color = "green" if open_close_ratio_growth >= 0 else "red"
            arrow = "↑" if open_close_ratio_growth >= 0 else "↓"

            st.markdown(f"""
                <div style="font-size:24px; font-weight:600;">Open vs. Closed Ratio</div>
                <div style="display:flex; align-items:center; gap:16px;">
                    <div style="font-size:32px; font-weight:700;">{open_close_ratio_display}</div>
                    <div style="font-size:16px; color:{color};">
                        {arrow} {open_close_ratio_growth:.1f}% From last month
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            try:
                df_open_closed = get_open_closed_trend(start_date_filter, end_date_filter, outlet_granularity_selection.lower())
                df_open_closed_monthly = get_open_closed_trend(start_date_filter, end_date_filter, "monthly" )
                
                col1, col2 = st.columns([2, 1])
                with col1:
                    df_plot = df_open_closed.melt(
                        id_vars=['period'], 
                        value_vars=['close', 'open'],
                        var_name='Status Outlet',
                        value_name='percent')
                    
                    fig = px.bar(df_plot, 
                                x='period', 
                                y='percent', 
                                color='Status Outlet',
                                title="Open vs. Closed Time by Outlet",
                                labels={'period': 'Period', 'percent': 'Percent',  'Status': 'Status'},
                                color_discrete_map={'open': '#fcd4d4', 'close': '#fa7878'},
                                hover_data={'percent'})
                    fig.update_layout(barmode='stack', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(t=60, l=80, r=180, b=25))
                    st.plotly_chart(fig, use_container_width=True)

                with col2:
                    pie_data = df_open_closed_monthly.iloc[-1][['open', 'close']].to_frame().T.melt(var_name='Status Outlet', value_name='Percent')
                    
                    pie_fig = px.pie(
                        pie_data,
                        values='Percent',
                        names='Status Outlet',
                        color='Status Outlet',
                        color_discrete_map={'open': '#fcd4d4', 'close': '#fa7878'},
                        labels={'Percent': 'Percent', 'Status Outlet': 'Status'})
                    pie_fig.update_traces(textinfo='none', hovertemplate="<b>%{label}</b><br>" + "Total Outlet: %{value:,.0f}<br>" + "Percent: %{percent}<extra></extra>")
                    pie_fig.update_layout(showlegend=True, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(r=140, l=20, t=60, b=0))
                    st.plotly_chart(pie_fig, use_container_width=True)

            except Exception as e:
                st.warning(f"Error: Data rasio Open vs. closed tidak tersedia. Pastikan fungsi ETL mengembalikan data yang benar. Pesan: {e}")

        st.write("---")
        col1, col2 = st.columns([7, 1])
        with col1:
            selected_metric_to_plot_outlet2 = st.segmented_control("Show Trend For:", 
                options=[ "Active Outlets", "Activation Time"], 
                default="Active Outlets",
                key="outlet_trend_control2")
        with col2:
            outlet_granularity_selection2 = st.selectbox(
                "View Trend By:", ("Monthly", "Weekly", "Daily"),
                key="outlet_granularity2")
            outlet_granularity_selection2 = outlet_granularity_selection2.lower()
        
        df_outlet_trend_metrics2 = get_outlet_trend_metrics(df_outlet, df_order, start_date_filter, end_date_filter, outlet_granularity_selection2)
        if not df_outlet_trend_metrics2.empty:
            if selected_metric_to_plot_outlet2 == "Activation Time":
                color = "green" if avg_act_time_growth >= 0 else "red"
                arrow = "↑" if avg_act_time_growth >= 0 else "↓"

                st.markdown(f"""
                    <div style="font-size:24px; font-weight:600;">Outlet Activation Time</div>
                    <div style="display:flex; align-items:center; gap:16px;">
                        <div style="font-size:32px; font-weight:700;">{avg_act_time_display}</div>
                        <div style="font-size:16px; color:{color};">
                            {arrow} {avg_act_time_growth:.1f}% From last month
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                selected_column = 'current_avg_activation_days'
                chart_title = "Average Outlet Activation Time"
                y_axis_label = "Average days activation"
                yaxis_tickformat = ',.1f'
                
            elif selected_metric_to_plot_outlet2 == "Active Outlets":
                color = "green" if active_outlets_growth >= 0 else "red"
                arrow = "↑" if active_outlets_growth >= 0 else "↓"

                st.markdown(f"""
                    <div style="font-size:24px; font-weight:600;">Active Outlets</div>
                    <div style="display:flex; align-items:center; gap:16px;">
                        <div style="font-size:32px; font-weight:700;">{active_outlets:,.0f}</div>
                        <div style="font-size:16px; color:{color};">
                            {arrow} {active_outlets_growth:.1f}% From last month
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                selected_column = 'Active'
                chart_title = "Active Outlets"
                y_axis_label = "Total Active Outlets"
                yaxis_tickformat = ',.0f'  
        
            
            fig = px.line(
                df_outlet_trend_metrics2, 
                x='period_str', 
                y=selected_column, 
                title=chart_title,
                labels={'period_str': "Period", selected_column: y_axis_label},
                markers=True)
            
            fig.update_traces(line_color='#FF4B4B')
            fig.update_layout(yaxis_tickformat=yaxis_tickformat, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(t=60, l=80, r=80, b=25))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Tidak ada data untuk periode yang dipilih.")
                            

    # menu tab  
    if selected_tab == "Menu Performance":  
        df_menu_ratio = get_menu_availability_ratio(start_date_filter, end_date_filter)
        menu_ratio = df_menu_ratio["availability_ratio_percent"].mean()
        df_zombie_ratio = get_zombie_product_ratio(start_date_filter, end_date_filter)
        zombie_ratio = df_zombie_ratio["zombie_percentage"].mean() if not df_zombie_ratio.empty else 0
        
        df_menu_ratio_prev = get_menu_availability_ratio(start_date_prev, end_date_prev)
        menu_ratio_prev= df_menu_ratio_prev["availability_ratio_percent"].mean()
        df_zombie_ratio_prev = get_zombie_product_ratio(start_date_prev, end_date_prev)
        zombie_ratio_prev = df_zombie_ratio_prev["zombie_percentage"].mean() if not df_zombie_ratio_prev.empty else 0

        menu_ratio_growth = calculate_growth(menu_ratio, menu_ratio_prev)
        menu_ratio_display = f"{menu_ratio:.1f}%" if menu_ratio > 0 else "0.00%"
        zombie_ratio_growth = calculate_growth(zombie_ratio, zombie_ratio_prev)
        zombie_ratio_display = f"{zombie_ratio:.1f}%" if zombie_ratio > 0 else "0.00%"

        st.subheader("Menu Performance")
        
        menu_cols = st.columns(2)
        menu_cols[0].metric("Product Availability Rate", menu_ratio_display, 
            delta=f"{menu_ratio_growth:.1f}% From last month",
            help="The precentage of time a product is available when the outlet is open")
        menu_cols[1].metric("Zombie Product Rate", zombie_ratio_display, 
            delta=f"{zombie_ratio_growth:.1f}% From last month",
            help="The precentage of time a product is available when the outlet is open")
        
        st.write("---")
        col1, col2 = st.columns([7, 1])
        color = "green" if menu_ratio_growth >= 0 else "red"
        arrow = "↑" if menu_ratio_growth >= 0 else "↓"

        with col1:
            st.markdown(f"""
                <div style="font-size:24px; font-weight:600;">Product Availability</div>
                <div style="display:flex; align-items:center; gap:16px;">
                    <div style="font-size:32px; font-weight:700;">{menu_ratio_display}</div>
                    <div style="font-size:16px; color:{color};">
                        {arrow} {menu_ratio_growth:.1f}% From last month
                    </div>
                </div>
            """, unsafe_allow_html=True)
        with col2:
            menu_granularity_selection = st.selectbox(
                "View Trend By:", ("Monthly", "Weekly", "Daily"),
                key="menu_granularity")
        
        try:
            df_menu_trend = get_menu_availability_trend(start_date_filter, end_date_filter, menu_granularity_selection.lower())
            
            if df_menu_trend.empty:
                st.warning("Data Menu Availability Trend (Harian) kosong.")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                df_plot = df_menu_trend.melt(
                    id_vars=['period'], 
                    value_vars=['available', 'unavailable'],
                    var_name='Status Menu',
                    value_name='percent')
                
                fig = px.bar(df_plot, 
                            x='period', 
                            y='percent', 
                            color='Status Menu',
                            title="Menu Available vs Unavailable Ratio",
                            labels={'period': 'Period', 'percent': 'Percent'},
                            color_discrete_map={'available': '#fcd4d4', 'unavailable': '#fa7878'},
                            hover_data={'percent'})
                fig.update_layout(barmode='stack', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(t=60, l=80, r=180, b=25))
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                avg_available = df_menu_trend['available'].mean()
                avg_unavailable = df_menu_trend['unavailable'].mean()
                pie_data = pd.DataFrame({
                    'Status Menu': ['available', 'unavailable'],
                    'Count': [round(avg_available, 1), round(avg_unavailable, 1)]})

                pie_fig = px.pie(
                    pie_data,
                    values='Count',
                    names='Status Menu',
                    color='Status Menu',
                    color_discrete_map={'available': '#fcd4d4', 'unavailable': '#fa7878'},
                    labels={'Count': 'Total Menit'})
                pie_fig.update_traces(textinfo='none',hovertemplate="<b>%{label}</b><br>" + "Percent: %{percent}<extra></extra>" )
                pie_fig.update_layout(showlegend=True, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(r=140, l=20, t=60, b=0))
                st.plotly_chart(pie_fig, use_container_width=True)

        except Exception as e:
            st.warning(f"Error: Menu Availability Ratio tidak tersedia. Pastikan fungsi ETL mengembalikan data yang benar. Pesan: {e}")

        if not df_items_filtered.empty:
            st.write("---")

            col1, col2, col3 = st.columns([7.1,1.8,1.3])
            with col1:
                st.subheader("🏆 Best Products / Options")
            with col3:
                sort_by_prod = st.selectbox(
                    "Sort By:",
                    ["Total Amount", "Total Quantity Sold"],
                    key="menu_leaderboard_sort")
            with col2:
                selected_view = st.segmented_control(
                    "Show Trend For:",
                    options=["Best Products","Best Options"], 
                    default="Best Products",
                    key="menu_leaderboard_control")

            sort_mapping = {
                "Total Amount": "total_revenue",
                "Total Quantity Sold": "total_quantity_sold"}

            if selected_view == "Best Products":
                df_agg = df_items_filtered.groupby(['product_name', 'outlet_name_outlet']).agg(
                    total_quantity_sold=('quantity_sold', 'sum'),
                    total_revenue=('revenue_product', 'sum')).reset_index()
            else:  # Best Options
                df_agg = df_items_filtered.groupby(['variant_name', 'product_name', 'outlet_name_outlet']).agg(
                    total_quantity_sold=('quantity_sold', 'sum'),
                    total_revenue=('cogs_variant', 'sum')).reset_index()

            sorted_df = df_agg.sort_values(by=sort_mapping[sort_by_prod], ascending=False).reset_index(drop=True)

            # Top 3 cards
            top3 = sorted_df.head(3)
            cols_top3 = st.columns(len(top3))
            for i, (_, row) in enumerate(top3.iterrows()):
                icon_display = "🥇" if i == 0 else ("🥈" if i == 1 else "🥉")
                value_display = row[sort_mapping[sort_by_prod]]
                if sort_by_prod == "Total Amount":
                    value_display = f"Rp {value_display:,.0f}"
                else:
                    value_display = f"{value_display:,.0f} pcs"

                with cols_top3[i]:
                    name_display = row['product_name']
                    if selected_view == "Best Options" and 'variant_name' in row:
                        name_display += f" - {row['variant_name']}"
                    st.markdown(f"""
                    <div style='
                        background-color: #ffffff;
                        border: 1px solid #e0e0e0;
                        border-radius: 12px;
                        padding: 8px;
                        text-align: center;
                        box-shadow: 0 2px 6px rgba(0,0,0,0.05);
                        margin: 12px 1.2px;'>
                        <div style='font-size:26px;'>{icon_display}</div>
                        <div style='font-weight:600; font-size:15px; margin-top:4px;'>{name_display}</div>
                        <div style='font-size:12px; color:#808080; margin-top:2px;'>{row['outlet_name_outlet']}</div>
                        <div style='font-weight:600; font-size:14px; color:#007BFF; margin-top:6px;'>{value_display}</div>
                    </div>
                    """, unsafe_allow_html=True)

            # Top 10 bar chart
            top10 = sorted_df.head(10)
            if selected_view == "Best Products":
                top10['product_combo'] = top10.apply(
                    lambda row: f"{row['product_name']} - {row['outlet_name_outlet']})", axis=1)
                y_col = 'product_combo'
            else:
                top10['variant_combo'] = top10.apply(
                    lambda row: f"{row['variant_name']} ({row['product_name']} - {row['outlet_name_outlet']})", axis=1)
                y_col = 'variant_combo'
            hover_cols = ['outlet_name_outlet', 'product_name']

            fig_leaderboard = px.bar(
                top10,
                x=sort_mapping[sort_by_prod],
                y=y_col,
                orientation='h',
                text=sort_mapping[sort_by_prod],
                title=f"Top 10 {'Products' if selected_view=='Best Products' else 'Options'} by {sort_by_prod}",
                labels={sort_mapping[sort_by_prod]: sort_by_prod,
                        'product_name': 'Product',
                        'variant_name': 'Option'},
                color=y_col, 
                hover_data={col: True for col in hover_cols})

            if selected_view == "Best Options":
                hover_template = "<b>%{y}</b><br>Total: %{x:,.0f}<br>Product: %{customdata[1]}<br>Outlet: %{customdata[0]}<extra></extra>"
            else: 
                hover_template = "<b>%{y}</b><br>Total: %{x:,.0f}<br>Outlet: %{customdata[0]}<extra></extra>"
                
            fig_leaderboard.update_traces(
                textposition='outside', hovertemplate=hover_template)

            if selected_view == "Best Options":
                fig_leaderboard.update_yaxes(
                    tickvals=top10['variant_combo'],
                    ticktext=top10['variant_name'])
            else:
                fig_leaderboard.update_yaxes(
                    tickvals=top10['product_combo'],
                    ticktext=top10['product_name'])
            
            fig_leaderboard.update_layout(
                yaxis={'categoryorder': 'total ascending'},
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                showlegend=False,
                height=420,
                margin=dict(t=60, l=100, r=50, b=30))

            st.plotly_chart(fig_leaderboard, use_container_width=True)
            
            # Detailed Breakdown
            if not sorted_df.empty:
                trend_dict = {}
                key_name = 'product_name' if selected_view=="Best Products" else 'variant_name'
                for name in sorted_df[key_name].unique():
                    df_trend = (
                        df_items_filtered[df_items_filtered[key_name] == name]
                        .groupby("order_date")
                        .agg({"quantity_sold": "sum"})
                        .reset_index()
                        .sort_values("order_date"))
                    trend_dict[name] = df_trend["quantity_sold"].tolist()

                sorted_df_display = sorted_df.copy()
                sorted_df_display["total_revenue"] = sorted_df_display["total_revenue"].map(lambda x: f"Rp {x:,.0f}")
                sorted_df_display["total_quantity_sold"] = sorted_df_display["total_quantity_sold"].map(lambda x: f"{x:,} pcs")
                sorted_df_display["Sales Trend"] = sorted_df_display[key_name].map(trend_dict)

                st.markdown("### 📊 Detailed Breakdown")
                st.dataframe(
                    sorted_df_display.rename(columns={
                        "product_name": "Product",
                        "variant_name": "Option",
                        "outlet_name_outlet": "Outlet",
                        "total_revenue": "Amount",
                        "total_quantity_sold": "Quantity Sold",}),
                    use_container_width=True,
                    height=380,
                    column_config={
                        "Product": st.column_config.TextColumn("Product", width="medium"),
                        "Option": st.column_config.TextColumn("Option", width="medium"),
                        "Outlet": st.column_config.TextColumn("Outlet", width="medium"),
                        "Amount": st.column_config.TextColumn("Amount"),
                        "Quantity Sold": st.column_config.TextColumn("Quantity Sold"),
                        "Sales Trend": st.column_config.LineChartColumn(
                            "Sales Trend (Qty per day)",
                            y_min=0,
                            y_max=None,
                            width="medium")})
            else:
                st.info("Tidak ada data produk atau option yang tersedia untuk leaderboard.")


    if selected_tab == "Location":
        # Regional GMV Contribution
        df_financial_base["outlet_province"] = df_financial_base["outlet_province"].apply(normalize_region_name)
        df_financial_base["outlet_city"] = df_financial_base["outlet_city"].apply(normalize_region_name)
        df_financial_base["outlet_district"] = df_financial_base["outlet_district"].apply(normalize_region_name)

        st.write("---")
        province_options = sorted([
            (f, re.sub(r'^id\d+_', '', f).replace("_", " ").title().upper())
            for f in os.listdir(BASE_DIR)
            if os.path.isdir(os.path.join(BASE_DIR, f)) and f.startswith("id")])

        all_city_options = []
        for prov_folder, prov_name in province_options:
            province_path = os.path.join(BASE_DIR, prov_folder)
            for city_folder in os.listdir(province_path):
                city_path = os.path.join(province_path, city_folder)
                if os.path.isdir(city_path):
                    city_name = re.sub(r'^id\d+_', '', city_folder).replace("_", " ").title().upper()
                    all_city_options.append((prov_folder, city_folder, f"{city_name} ({prov_name})"))

        all_district_options = []
        for prov_folder, prov_name in province_options:
            province_path = os.path.join(BASE_DIR, prov_folder)
            for city_folder in os.listdir(province_path):
                city_path = os.path.join(province_path, city_folder)
                if os.path.isdir(city_path):
                    for district_file in os.listdir(city_path):
                        if district_file.endswith(".geojson"):
                            district_name = re.sub(r'^id\d+_', '', district_file).replace("_", " ").replace(".geojson", "").title().upper()
                            all_district_options.append((prov_folder, city_folder, district_file, f"{district_name} ({prov_name})"))

        col1, col2, col3, col4 = st.columns([4, 1.5, 1.5, 1.5])

        with col1:
            st.subheader("Regional GMV Contribution")
        with col2:
            selected_province_display = st.selectbox(
                "Select Province:",
                ["All Province"] + [name for _, name in province_options])

        with col3:
            if selected_province_display != "All Province":
                selected_province_folder = next(f for f, name in province_options if name == selected_province_display)
                filtered_city_options = [
                    (p, c, label) for (p, c, label) in all_city_options if p == selected_province_folder]
            else:
                filtered_city_options = all_city_options

            selected_city_display = st.selectbox(
                "Select City/Regency:",
                ["All City/Regency"] + [label for _, _, label in filtered_city_options])

        with col4:
            if selected_city_display != "All City/Regency":
                selected_city_folder = next(c for _, c, label in filtered_city_options if label == selected_city_display)
                selected_province_folder = next(p for p, c, label in filtered_city_options if label == selected_city_display)
                filtered_district_options = [
                    (p, c, d, label)
                    for (p, c, d, label) in all_district_options
                    if p == selected_province_folder and c == selected_city_folder]
            else:
                filtered_district_options = all_district_options

            selected_district_display = st.selectbox(
                "Select District:",
                ["All District"] + [label for _, _, _, label in filtered_district_options])

        geojson_data = None
        key_name = None
        selected_region_to_highlight = None

        if selected_district_display != "All District":
            p, c, d, _ = next(item for item in filtered_district_options if item[3] == selected_district_display)
            geojson_data, _, key_name = load_geojson_dynamic(BASE_DIR, "District", p, c, d)
            selected_region_to_highlight = normalize_region_name(re.sub(r'\s*\(.*\)', '', selected_district_display))

        elif selected_city_display != "All City/Regency":
            p, c, _ = next(item for item in filtered_city_options if item[2] == selected_city_display)
            geojson_data, _, key_name = load_geojson_dynamic(BASE_DIR, "City")
            province_name_to_filter = selected_province_display.upper()
            filtered_features = [
                f for f in geojson_data.get("features", [])
                if f.get("properties", {}).get("prov_name", "").upper() == province_name_to_filter]
            geojson_data = {"type": "FeatureCollection", "features": filtered_features}
            selected_region_to_highlight = normalize_region_name(re.sub(r'\s*\(.*\)', '', selected_city_display))

        elif selected_province_display != "All Province":
            geojson_data, _, key_name = load_geojson_dynamic(BASE_DIR, "Province")
            selected_region_to_highlight = normalize_region_name(selected_province_display)

        else:
            geojson_data, _, key_name = load_geojson_dynamic(BASE_DIR, "Province")
            selected_region_to_highlight = None

        if geojson_data:
            if selected_district_display != "All District":
                group_col = "outlet_district"
            elif selected_city_display != "All City/Regency":
                group_col = "outlet_city"
            elif selected_province_display != "All Province":
                group_col = "outlet_province"
            else:
                group_col = "outlet_province"

            if group_col in df_financial_base.columns:
                total_gmv_all = df_financial_base["gmv_order"].sum()
                for feature in geojson_data["features"]:
                    region_name = normalize_region_name(feature["properties"].get(key_name))
                    feature["properties"][key_name] = region_name
                    if region_name:
                        df_region = df_financial_base[df_financial_base[group_col] == region_name]
                        gmv_region = df_region["gmv_order"].sum()
                        orders_region = df_region["order_id"].nunique()
                        gmv_pct_region = (gmv_region / total_gmv_all * 100) if total_gmv_all != 0 else 0
                        feature["properties"]["gmv"] = f"Rp {gmv_region:,.0f}"
                        feature["properties"]["orders"] = orders_region
                        feature["properties"]["gmv_pct"] = f"{gmv_pct_region:.2f}%"

            def style_function(feature):
                region_name = feature['properties'].get(key_name)
                if selected_region_to_highlight and region_name == selected_region_to_highlight:
                    return {'fillColor': '#fa7878', 'color': 'transparent', 'weight': 1, 'fillOpacity': 0.8}
                return {'fillColor': '#ffffff00', 'color': 'transparent', 'weight': 0.5, 'fillOpacity': 0.1}

            # map
            center = [-2.5, 118.0]
            zoom_start = 5
            shapes = []

            if selected_region_to_highlight:
                for feature in geojson_data["features"]:
                    geom_data = feature.get("geometry")
                    region_name = normalize_region_name(feature["properties"].get(key_name))
                    feature["properties"][key_name] = region_name
                    if geom_data and region_name == selected_region_to_highlight:
                        try:
                            g = shapely_shape(geom_data)
                            if not g.is_valid:
                                g = g.buffer(0)
                            shapes.append(g)
                        except Exception:
                            pass

            if shapes:
                try:
                    combined = unary_union(shapes)
                    bounds = combined.bounds
                    center_lat = (bounds[1] + bounds[3]) / 2
                    center_lon = (bounds[0] + bounds[2]) / 2
                    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_start, tiles="OpenStreetMap")
                    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
                except Exception:
                    m = folium.Map(location=center, zoom_start=zoom_start, tiles="OpenStreetMap")
            else:
                m = folium.Map(location=center, zoom_start=zoom_start, tiles="OpenStreetMap")

            folium.GeoJson(
                geojson_data,
                name='Batas Wilayah',
                style_function=style_function,
                tooltip=folium.GeoJsonTooltip(
                    fields=[key_name, "gmv", "orders", "gmv_pct"],
                    aliases=['Nama Wilayah:', 'Total GMV:', 'Total Orders:', 'GMV Contribution (%):'],
                    localize=True)).add_to(m)

            st_folium(m, width="100%", height=650)
            
            # metric
            if group_col and group_col in df_financial_base.columns:
                if selected_region_to_highlight:
                    df_filtered_region = df_financial_base[
                        df_financial_base[group_col].apply(normalize_region_name) == normalize_region_name(selected_region_to_highlight)
                    ]
                    df_filtered_region_prev = df_financial_base_prev[
                        df_financial_base_prev[group_col].apply(normalize_region_name) == normalize_region_name(selected_region_to_highlight)
                    ]
                else:
                    df_filtered_region = df_financial_base.copy()
                    df_filtered_region_prev = df_financial_base_prev.copy()

                total_gmv_region = df_filtered_region["gmv_order"].sum()
                total_orders_region = df_filtered_region["order_id"].nunique()
                gmv_percentage_region = (total_gmv_region / total_gmv_all * 100) if total_gmv_all != 0 else 0

                total_gmv_region_prev = df_filtered_region_prev["gmv_order"].sum()
                total_orders_region_prev = df_filtered_region_prev["order_id"].nunique()
                gmv_percentage_region_prev = (total_gmv_region_prev / total_gmv_all * 100) if total_gmv_all != 0 else 0

                total_gmv_region_growth = calculate_growth(total_gmv_region, total_gmv_region_prev)
                total_orders_region_growth = calculate_growth(total_orders_region, total_orders_region_prev)
                gmv_percentage_region_growth = calculate_growth(gmv_percentage_region, gmv_percentage_region_prev)

                col_metrics= st.columns(3)
                with col_metrics[0]:
                    st.metric("Gross Merchandise Value (GMV)", f"Rp {total_gmv_region:,.0f}", delta=f"{total_gmv_region_growth:,.1f}% From last month")
                with col_metrics[1]: 
                    st.metric("Total Orders", f"{total_orders_region:,.0f}", delta=f"{total_orders_region_growth:,.1f}% From last month", help="Total Order Success")
                with col_metrics[2]:
                    st.metric("GMV Contribution (%)", f"{gmv_percentage_region:.2f}%", delta=f"{gmv_percentage_region_growth:,.1f}% From last month")


    # forecasting tab
if selected_tab == "Forecasting":
        df_forecast_base = df_order.copy()

        st.divider()
        col1, col2, col3, col4 = st.columns([9, 3, 1.5, 2.7])

        with col1:
            st.header("📈 Sales & GMV Forecasting")
        with col3:
            forecast_level = st.selectbox(
                "Forecast Level:",
                ["All Data", "Owner", "Outlet"])
        with col4:
            metric_label = st.segmented_control(
                "Metric to Predict:",
                ["Total GMV", "Total Orders"],
                default="Total GMV")

        metric_map = {
            "Total GMV": "gmv_order",
            "Total Orders": "Total Orders"}
        metric_to_forecast = metric_map[metric_label]

        # LOCAL FILTER BASED ON LEVEL
        col_button, col_level = st.columns([10, 3.5])
        
        with col_level:
            if forecast_level == "Owner":
                owner_list = sorted(df_order['owner_name'].dropna().unique())
                owner_options = ["Select Owner"] + owner_list

                selected_owner = st.selectbox("", owner_options, index=0, label_visibility="collapsed" )
                if selected_owner != "Select Owner":
                    df_forecast_base = df_forecast_base[
                        df_forecast_base['owner_name'] == selected_owner ]

            elif forecast_level == "Outlet":
                outlet_list = sorted(df_order['outlet_name'].dropna().unique())
                outlet_options = ["Select Outlet"] + outlet_list

                selected_outlet = st.selectbox("", outlet_options, index=0, label_visibility="collapsed")
                if selected_outlet != "Select Outlet":
                    df_forecast_base = df_forecast_base[
                        df_forecast_base['outlet_name'] == selected_outlet]

        if metric_to_forecast == "gmv_order":
            df_forecast_base = df_forecast_base[
                df_forecast_base['status'].isin(FINANCIAL_STATUSES)]

        if df_forecast_base.empty:
            st.warning("No data available for forecasting.")
            st.stop()

        last_date = pd.to_datetime(
            df_forecast_base['order_date']).max().normalize()

        with col2:
            start_date, end_date = st.date_input(
                "Prediction Date Range:",
                value=(
                    last_date + pd.Timedelta(days=1),
                    last_date + pd.Timedelta(days=30)
                ),
                min_value=last_date + pd.Timedelta(days=1))

        forecast_days = (pd.to_datetime(end_date) - last_date).days + 1

        if forecast_days <= 0:
            st.error("Invalid forecast range.")
            st.stop()

        with col_button:
            run_prediction = st.button("Run Prediction")
                
        if run_prediction:  
            with st.spinner("Running forecasting model..."):
                # PREPARE DATA
                df_daily = prepare_forecast_data(
                    df_forecast_base,
                    metric_to_forecast)

                # PROPHET MODEL
                model, forecast = run_prophet_forecast(
                    df_daily,
                    periods=forecast_days)

                # FILTER FORECAST DATE
                filtered_forecast = forecast[
                    (forecast['ds'] >= pd.to_datetime(start_date)) &
                    (forecast['ds'] <= pd.to_datetime(end_date))]

                if filtered_forecast.empty:
                    st.error("Forecast result is empty.")
                    st.stop()

                total_forecast = filtered_forecast['yhat'].sum()
                total_lower = filtered_forecast['yhat_lower'].sum()
                total_upper = filtered_forecast['yhat_upper'].sum()

                value_display = (
                    f"Rp {total_forecast:,.0f}"
                    if metric_to_forecast == "gmv_order"
                    else f"{total_forecast:,.0f}")

                st.metric(
                    label=f"Prediction Result ({metric_label})",
                    value=value_display,
                    help=(
                        f"Period: {start_date} to {end_date}\n"
                        f"Lower Bound: {total_lower:,.0f}\n"
                        f"Upper Bound: {total_upper:,.0f}"))

                fig = plot_plotly(model, forecast)
                fig.update_layout(
                    title=f"Forecast {metric_label}",
                    xaxis_title="Date",
                    yaxis_title=metric_label,
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    margin=dict(t=80, l=40, r=60, b=60),
                    yaxis=dict(
                        tickprefix="Rp " if metric_to_forecast == "gmv_order" else "",
                        tickformat=",",
                        separatethousands=True))

                st.plotly_chart(fig, use_container_width=True)

                with st.expander("📄 Forecast Detail Table"):
                    df_table = filtered_forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].copy()

                    df_table.rename(columns={
                        'ds': 'Tanggal',
                        'yhat': 'Prediksi',
                        'yhat_lower': 'Batas Bawah',
                        'yhat_upper': 'Batas Atas'}, inplace=True)

                    if metric_to_forecast == "gmv_order":
                        df_table['Prediksi'] = df_table['Prediksi'].apply(lambda x: f"Rp {x:,.0f}")
                        df_table['Batas Bawah'] = df_table['Batas Bawah'].apply(lambda x: f"Rp {x:,.0f}")
                        df_table['Batas Atas'] = df_table['Batas Atas'].apply(lambda x: f"Rp {x:,.0f}")
                    else:
                        df_table['Prediksi'] = df_table['Prediksi'].map(lambda x: f"{x:,.0f}")
                        df_table['Batas Bawah'] = df_table['Batas Bawah'].map(lambda x: f"{x:,.0f}")
                        df_table['Batas Atas'] = df_table['Batas Atas'].map(lambda x: f"{x:,.0f}")

                    df_table['Tanggal'] = df_table['Tanggal'].dt.strftime("%d %b %Y")

                    st.dataframe(df_table, use_container_width=True)

# else:
#     st.warning("Tidak ada data yang cocok dengan filter yang Anda pilih.")
