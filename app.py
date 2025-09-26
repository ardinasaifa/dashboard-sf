import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re

from datetime import date, timedelta
from etl_process import load_dm_order, load_dm_outlet, get_outlet_performance_metrics_v2, get_open_closed_ratio_working, get_outlet_metrics_trend, get_open_closed_daily_trend


# ========================================== LOAD DATA ======================================================
df_order = load_dm_order()
df_outlet = load_dm_outlet()
# df_virtualbrand = 

# -------------------- Konfigurasi Halaman & CSS --------------------
st.set_page_config(layout="wide", page_title="Superfood Dashboard", initial_sidebar_state="expanded")
st.markdown("""
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        /* --- Global Styles --- */
        html, body, .stApp { font-family: 'Poppins', sans-serif; background-color: #F0F2F6; color: #333; }
        h1, h2, h3 { font-weight: 600; color: #111; }
        
        /* --- Sidebar Styling --- */
        section[data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 0.5px solid #E0E0E0; padding: 20px 0.5px; }
        .sidebar-title { font-size: 1.8em; font-weight: 700; color: #FF4B4B; text-align: center; margin-bottom: 20px; }
        .sidebar-nav { list-style-type: none; padding: 0; margin: 0; }
        .sidebar-nav a { display: flex; align-items: center; padding: 8px 20px; margin: 5px 0; border-radius: 8px; color: #555; text-decoration: none; font-weight: 400; transition: background-color 0.3s, color 0.3s; }
        .sidebar-nav a:hover { background-color: #F0F2F6; color: #555; }
        .sidebar-nav a.active { background-color: #FFEBEB; color: #FF4B4B; font-weight: 500; }
        .sidebar-nav a i { margin-right: 15px; font-size: 1em; width: 20px; text-align: center; }
        
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
            flex: 1;                        /* <= biar proporsional */
            max-width: 100%;                /* <= biar ga melebar */
            background-color: white; 
            border: none; 
            padding: 25px 82px; 
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
            
        .stMultiSelect > div > div {
            background-color: #FFFFFF !important;
            border: 1px solid #E0E0E0 !important;
            border-radius: 8px !important; }
        
        .stSelectbox > div > div {
            background-color: #FFFFFF !important;
            border: 1px solid #E0E0E0 !important;
            border-radius: 8px !important;} 
        .stDateInput > div > div { background-color: #FFFFFF; }
        .main > div { padding-left: 2rem; padding-right: 2rem; }
    </style>
""", unsafe_allow_html=True)

# FUNGSI UNTUK AMBIL OPSI FILTER DARI DATABASE
@st.cache_data
def get_filter_options(_df_order, _df_outlet):
    if _df_order.empty and _df_outlet.empty:
        return {"brands": [], "outlets": [], "owners": [], "sources": [], "statuses": []}
    
    def format_status(s): 
        return s.replace('wc-', '').replace('-', ' ').title() if isinstance(s, str) else s
        
    return {
        "brands": sorted([b for b in _df_order['brand_name'].dropna().unique() if b]),
        "outlets": sorted([o for o in _df_outlet['outlet_name'].dropna().unique() if o]),
        "owners": sorted([o for o in _df_outlet['owner_name'].dropna().unique() if o]),
        "sources": sorted([s for s in _df_order['order_source'].dropna().unique() if s]),
        "statuses": sorted(list(set(format_status(s) for s in _df_order['status'].dropna().unique() if s)))
    }
    
filter_options = get_filter_options(df_order, df_outlet)

# FUNGSI UNTUK AMBIL OUTLET METRIC TREND BUAT CHART
@st.cache_data
def get_outlet_trend_metrics(df_outlet, df_order, start_date, end_date, granularity):
    df_outlet['go_live'] = pd.to_datetime(df_outlet['go_live'], errors='coerce')
    df_order['order_date'] = pd.to_datetime(df_order['order_date'], errors='coerce')
    trend_data = []
    
    if granularity == 'daily':
        period_range = pd.date_range(start=start_date, end=end_date, freq='D')
    else: 
        period_range = pd.period_range(start=start_date, end=end_date, freq='M').to_timestamp('s').to_list()

    for p_timestamp in period_range:
        if granularity == 'daily':
            current_start = p_timestamp.date()
            current_end = p_timestamp.date()
            period_str = p_timestamp.strftime('%Y-%m-%d')
        else:
            current_start = p_timestamp.date().replace(day=1)
            current_end = (p_timestamp.date().replace(day=28) + pd.Timedelta(days=4)).replace(day=1) - pd.Timedelta(days=1)
            period_str = p_timestamp.strftime('%Y-%m')
        
        # 1. Hitung total outlet yang go_live sampai akhir periode ini (TOTAL AKTIF)
        all_active_outlets = df_outlet[
            (df_outlet['go_live'].dt.date <= current_end)]['outlet_id'].unique()
        
        orders_in_period = df_order[
            (df_order['order_date'].dt.date >= current_start) & 
            (df_order['order_date'].dt.date <= current_end)
        ]
        
        avg_activation_days = df_outlet[
            (df_outlet['go_live'].dt.date <= current_end)]['outlet_activation_time_days'].mean()
        if pd.isna(avg_activation_days): 
            avg_activation_days = 0

        # 2. Hitung outlet yang memiliki pesanan di periode ini (PRODUKTIF)
        productive_outlets_in_period = orders_in_period['outlet_id'].unique()
        num_productive = len(productive_outlets_in_period)
        
        # 3. Hitung outlet yang go_live TAPI tidak produktif
        unproductive_but_active = len(set(all_active_outlets) - set(productive_outlets_in_period))
        
        # 4. Total aktif adalah jumlah produktif dan tidak produktif
        num_total_active = num_productive + unproductive_but_active
        
        total_orders = orders_in_period['order_id'].count()
        total_gmv = orders_in_period['gmv_order'].sum()
        avg_order_per_productive = total_orders / num_productive if num_productive > 0 else 0
        avg_gmv_per_productive = total_gmv / num_productive if num_productive > 0 else 0

        trend_data.append({
            'period_str': period_str,
            'Productive': num_productive,
            'Active real': num_total_active,
            'Active': unproductive_but_active,
            'avg_order_per_productive_outlet': avg_order_per_productive,
            'avg_gmv_per_productive_outlet': avg_gmv_per_productive,
            'avg_activation_days': avg_activation_days
        })

    df_outlet_trend_metrics = pd.DataFrame(trend_data)
    df_outlet_trend_metrics = df_outlet_trend_metrics.set_index('period_str').reindex(
        [p.strftime('%Y-%m-%d') if granularity=='daily' else p.strftime('%Y-%m') for p in period_range]
    ).reset_index().rename(columns={'index': 'period_str'})
    df_outlet_trend_metrics = df_outlet_trend_metrics.fillna(0)
    
    return df_outlet_trend_metrics

# ================================================================= SIDEBAR NAVIGASI =================================================================
with st.sidebar:
    st.image("https://superfood-ic.com/wp-content/uploads/2022/10/logo-sf-web.png", width=150)
    st.markdown("<div class='sidebar-title'>SuperFood</div>", unsafe_allow_html=True)
    query_params = st.query_params.to_dict()
    page = query_params.get("page", "Merchant Analysis")
    st.markdown(f"""
        <div class="sidebar-nav">
            <a href="?page=Merchant Analysis" class="{'active' if page == 'Merchant Analysis' else ''}"><i class="fas fa-users"></i> Merchant Analysis</a>
            <a href="?page=Competitor Analysis" class="{'active' if page == 'Competitor Analysis' else ''}"><i class="fas fa-tag"></i> Competitor Analysis</a>
            <a href="?page=Customer Analysis" class="{'active' if page == 'Customer Analysis' else ''}"><i class="fas fa-chart-line"></i> Customer Analysis</a>
        </div>
    """, unsafe_allow_html=True)


# ============================================================= PAGE MERCHANT ANALYSIS ==========================================================================
if page == "Merchant Analysis":
    st.title("Merchant Analysis")
    
    # filter 
    st.header("Filters")
    with st.container(border=True):
        filter_cols_1 = st.columns(3)
        with filter_cols_1[0]:
            if not df_order.empty:
                min_date, max_date = df_order['order_date'].min().date(), df_order['order_date'].max().date()
                date_range_val = st.date_input("Date Range", value=(max_date - timedelta(days=7), max_date), min_value=min_date, max_value=max_date, key="overview_date")
            else:
                date_range_val = st.date_input("Date Range", value=(date.today() - timedelta(days=7), date.today()), key="overview_date_empty")
        with filter_cols_1[1]: selected_brands = st.multiselect("Virtual Brand", options=['All'] + filter_options.get('brands', []), default=['All'], key="overview_brands")
        with filter_cols_1[2]: selected_order_sources = st.multiselect("Channel (OFD)", options=['All'] + filter_options.get('sources', []), default=['All'], key="overview_sources")
        
        filter_cols_2 = st.columns(3)
        with filter_cols_2[0]: selected_outlets = st.multiselect("Outlet", options=['All'] + filter_options.get('outlets', []), default=['All'], key="overview_outlets",)
        with filter_cols_2[1]: selected_owners = st.multiselect("Nama Owner", options=['All'] + filter_options.get('owners', []), default=['All'], key="overview_owners")
        with filter_cols_2[2]: selected_statuses = st.multiselect("Order Status", options=filter_options.get('statuses', []), default=[], key="overview_statuses")

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
                df_outlet['go_live'].dt.date <= end_date_filter
            ]['outlet_id'].nunique()
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
            
            # hitung Active Outlets saat ini dan sebelumnya
            active_outlets = df_outlet[df_outlet['go_live'].dt.date <= end_date_filter]['outlet_id'].nunique()
            active_outlets_prev = df_outlet[df_outlet['go_live'].dt.date <= end_date_prev]['outlet_id'].nunique()
            active_outlets_growth = ((active_outlets - active_outlets_prev) / active_outlets_prev * 100) if active_outlets_prev > 0 else 0
            productive_outlets = df_filtered_order['outlet_id'].nunique()
            productive_outlets_prev = df_filtered_order_prev['outlet_id'].nunique()
        
        # apply filter status
        if selected_statuses:
            db_statuses = [f"wc-{s.lower().replace(' ', '-')}" for s in selected_statuses]
            df_filtered_order = df_filtered_order[df_filtered_order['status'].isin(db_statuses)]
            df_filtered_order_prev = df_filtered_order_prev[df_filtered_order_prev['status'].isin(db_statuses)]

    df_orders_filtered = df_filtered_order.drop_duplicates(subset=['order_id'])
    df_orders_filtered_prev = df_filtered_order_prev.drop_duplicates(subset=['order_id'])
        
    # calculation all metric in growth tab
    if not df_orders_filtered.empty:
        FINANCIAL_STATUSES = ('wc-disbursement-completed', 'wc-completed', 'wc-disbursement-progress')
        TOTAL_ORDER_COUNT_STATUSES = ('wc-disbursement-completed', 'wc-disbursement-progress', 'wc-completed', 'wc-processing', 'wc-cancelled')

        df_financial_base = df_orders_filtered[df_orders_filtered['status'].isin(FINANCIAL_STATUSES)] if not selected_statuses else df_orders_filtered
        df_order_count_base = df_orders_filtered[df_orders_filtered['status'].isin(TOTAL_ORDER_COUNT_STATUSES)] if not selected_statuses else df_orders_filtered
    
        total_gmv = df_financial_base['gmv_order'].sum()
        total_cogs = df_financial_base['cogs_order'].sum()
        total_gross_revenue = df_financial_base['gross_revenue_order'].sum()
        total_orders = df_order_count_base['order_id'].nunique()
        total_orders_clean = df_financial_base['order_id'].nunique() #total order bersih ('wc-disbursement-completed', 'wc-completed', 'wc-disbursement-progress')
        productive_outlets = df_financial_base['outlet_id'].nunique()
        # avg_order_value = total_gross_revenue / total_orders if total_orders > 0 else 0 #avg_order_value kotor
        success_order_count = df_orders_filtered[df_orders_filtered['status'].isin(['wc-completed', 'wc-disbursement-completed', 'wc-disbursement-progress'])]['order_id'].nunique()
        success_ratio = (success_order_count / total_orders * 100) if total_orders > 0 else 0.0

    if not df_orders_filtered_prev.empty:
        df_financial_base_prev = df_orders_filtered_prev[df_orders_filtered_prev['status'].isin(FINANCIAL_STATUSES)] if not selected_statuses else df_orders_filtered_prev
        df_order_count_base_prev = df_orders_filtered_prev[df_orders_filtered_prev['status'].isin(TOTAL_ORDER_COUNT_STATUSES)] if not selected_statuses else df_orders_filtered_prev

        total_gmv_prev = df_financial_base_prev['gmv_order'].sum()
        total_gross_revenue_prev = df_financial_base_prev['gross_revenue_order'].sum()
        total_orders_prev = df_order_count_base_prev['order_id'].nunique()
        success_order_count_prev = df_financial_base_prev['order_id'].nunique()
        
    # calculation growth
    gmv_growth = ((total_gmv - total_gmv_prev) / total_gmv_prev * 100) if total_gmv_prev > 0 else 0
    gross_revenue_growth = ((total_gross_revenue - total_gross_revenue_prev) / total_gross_revenue_prev * 100) if total_gross_revenue_prev > 0 else 0
    orders_growth = ((total_orders - total_orders_prev) / total_orders_prev * 100) if total_orders_prev > 0 else 0
    
    # tab
    growth_tab, outlet_tab, order_tab, breakdown_tab = st.tabs(["📈 Growth", "🏪 Outlet Details", "🛒 Order Details", "📊 Detailed Breakdowns"])
        
    # growth_tab
    with growth_tab:
        if not df_orders_filtered.empty:
            st.subheader("Overview")
            kpi_cols = st.columns(4)
            
            status_breakdown = df_order_count_base['status'].value_counts()
            completed_count = status_breakdown.get('wc-completed', 0)
            disbursement_completed_count = status_breakdown.get('wc-disbursement-completed', 0)
            disbursement_progress_count = status_breakdown.get('wc-disbursement-progress', 0)
            processing_count = status_breakdown.get('wc-processing', 0)
            cancelled_count = status_breakdown.get('cancelled', 0)
            
            help_text = f"""Order Status Breakdown:
- Completed: {completed_count:,}
- Disbursement Completed: {disbursement_completed_count:,}
- Disbursement Progress: {disbursement_progress_count:,}
- Processing: {processing_count:,}
- Cancelled: {cancelled_count:,}

Total Success Orders: {success_order_count:,}"""
            
            # metric di growth
            with kpi_cols[0]:
                st.metric("Total GMV", f"Rp {total_gmv:,.0f}", delta=f"{gmv_growth:,.1f}% From last month", help="Gross Merchandise Value")
            with kpi_cols[1]:
                st.metric("Total Gross Revenue", f"Rp {total_gross_revenue:,.0f}", delta=f"{gross_revenue_growth:,.1f}% From last month", help="GMV-COGS")
            with kpi_cols[2]:
                st.metric("Total Orders", f"{total_orders:,.0f}", delta=f"{orders_growth:,.1f}% From last month", help=help_text)
            with kpi_cols[3]:
                st.metric("Active Outlets", f"{active_outlets:,.0f}", delta=f"{active_outlets_growth:,.1f}% From last month", help="Cumulative Outlets")
            
            
            st.write("---")
            
            col1, col2 = st.columns([2, 1])
            with col2:
                granularity_selection = st.selectbox("View Trend By:", ("Monthly", "Daily"))
                granularity_for_query = granularity_selection.lower()
            
            with col1:
                selected_metric_to_plot = st.segmented_control("Show Trend For:", options=["GMV","Gross Revenue", "Orders", "Active Outlets"], default= "GMV", key="growth_trend_control")
            
        # df_trend this is data trend for chart (order)
        df_trend_source = df_financial_base.copy()
        if granularity_for_query == 'daily':
            df_trend_source['period_str'] = df_trend_source['order_date'].dt.strftime('%Y-%m-%d')
        else:
            df_trend_source['period_str'] = df_trend_source['order_date'].dt.to_period('M').astype(str)

        df_trend = df_trend_source.groupby('period_str').agg(
            gmv=('gmv_order', 'sum'),
            gross_revenue=('gross_revenue_order', 'sum'),
            orders=('order_id', 'nunique'),
            outlets=('outlet_id', 'nunique')
        ).reset_index()

        # df_outlet_trend this is data trend for chart (outlet)
        df_outlet_trend = pd.DataFrame()
        if not df_outlet.empty:
            df_outlet_trend = df_outlet.copy()
            df_outlet_trend['go_live'] = pd.to_datetime(df_outlet_trend['go_live'], errors='coerce')
            df_outlet_trend = df_outlet_trend[df_outlet_trend['go_live'].dt.date <= end_date_filter]

            if granularity_for_query == 'daily':
                df_outlet_trend['period_str'] = df_outlet_trend['go_live'].dt.strftime('%Y-%m-%d')
            else:
                df_outlet_trend['period_str'] = df_outlet_trend['go_live'].dt.to_period('M').astype(str)
            
            df_outlet_trend = df_outlet_trend.groupby('period_str').size().reset_index(name='activated_outlets')
            df_outlet_trend = df_outlet_trend.sort_values('period_str')
            df_outlet_trend['cumulative_active_outlets'] = df_outlet_trend['activated_outlets'].cumsum()

        fig = None
        if selected_metric_to_plot == "Active Outlets":
            color = "green" if active_outlets_growth >= 0 else "red"
            arrow = "↑" if active_outlets_growth >= 0 else "↓"
            st.markdown(f"""
                        <div style="font-size:24px; font-weight:600;">Active Outlets</div>
                        <div style="display:flex; align-items:center; gap:16px;">
                            <div style="font-size:32px; font-weight:700;">{active_outlets:,.0f}</div>
                            <div style="font-size:16px; color:{color};">
                                {arrow} {active_outlets_growth:,.1f}% From last month
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
            if not df_outlet_trend.empty:
                fig = px.line(
                    df_outlet_trend,
                    x='period_str',
                    y='cumulative_active_outlets',
                    title='Cumulative Active Outlet Growth',
                    labels={'period_str': granularity_selection, 'cumulative_active_outlets': 'Total Active Outlets'},
                    markers=True
                )
                fig.update_yaxes(tickformat=",.0f")
            else:
                st.info("No active outlet trend data available.")
                
        else:
            plot_mapping = {
                "GMV": ("gmv", "GMV Growth", total_gmv, gmv_growth),
                "Gross Revenue": ("gross_revenue", "Gross Revenue Growth", total_gross_revenue, gross_revenue_growth),
                "Order": ("orders", "Order Growth", total_orders, orders_growth)
            }
            
            y_axis, title, display_value, growth_value = plot_mapping.get(
                selected_metric_to_plot, 
                ("gmv", "GMV Growth", total_gmv, gmv_growth)
            )

            color = "green" if growth_value >= 0 else "red"
            arrow = "↑" if growth_value >= 0 else "↓"

            # Markdown khusus untuk metrik penjualan
            st.markdown(f"""
                <div style="font-size:24px; font-weight:600;">Total {selected_metric_to_plot}</div>
                <div style="display:flex; align-items:center; gap:16px;">
                    <div style="font-size:32px; font-weight:700;">{display_value:,.0f}</div>
                    <div style="font-size:16px; color:{color};">
                        {arrow} {growth_value:,.1f}% From last month
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            if not df_trend.empty:
                fig = px.line(
                    df_trend,
                    x='period_str',
                    y=y_axis,
                    title=title,
                    labels={'period_str': granularity_selection, y_axis: selected_metric_to_plot},
                    markers=True
                )
                if 'Revenue' in selected_metric_to_plot or 'GMV' in selected_metric_to_plot:
                    fig.update_yaxes(tickprefix="Rp ", tickformat=",.0f")
            else:
                st.info("No trend data available for the selected filters.")


        if fig is not None:
            fig.update_layout(
                margin=dict(t=60, l=40, r=40, b=25),
                autosize=True, 
                width=None, 
                xaxis_title=None, 
                yaxis_title=None, 
                hovermode="x unified", 
                plot_bgcolor='rgba(0,0,0,0)', 
                paper_bgcolor='rgba(0,0,0,0)'
            )
            fig.update_traces(line_color='#FF4B4B')
            st.plotly_chart(fig, use_container_width=True)
                
    
        # outlet tab
        with outlet_tab:
            st.subheader("Overview")
            outlet_performance_data = get_outlet_performance_metrics_v2(start_date_filter, end_date_filter)
            outlet_performance_data_prev = get_outlet_performance_metrics_v2(start_date_prev, end_date_prev)
            
            df_outlet_current = df_outlet[
                (df_outlet['go_live'].dt.date >= start_date_filter) &
                (df_outlet['go_live'].dt.date <= end_date_filter)
            ]
            df_outlet_prev = df_outlet[
                (df_outlet['go_live'].dt.date >= start_date_prev) &
                (df_outlet['go_live'].dt.date <= end_date_prev)
            ]
            
            act_rate = outlet_performance_data.get('activation_rate')
            ret_rate = outlet_performance_data.get('retention_rate')
            avg_act_time = outlet_performance_data.get('avg_activation_time_days')
            avg_act_time = df_outlet_current['outlet_activation_time_days'].mean()
            
            act_rate_prev = outlet_performance_data_prev.get('activation_rate')
            ret_rate_prev = outlet_performance_data_prev.get('retention_rate')
            avg_act_time_prev = df_outlet_prev['outlet_activation_time_days'].mean()
            
            # ini pakai cumulative active outlet
            avg_gmv_per_outlet = total_gmv / active_outlets if active_outlets > 0 else 0
            avg_gmv_per_outlet_productive = total_gmv / productive_outlets if productive_outlets > 0 else 0
            avg_order_per_outlet = total_orders / active_outlets if active_outlets > 0 else 0
            avg_order_per_outlet_productive = total_orders / productive_outlets if productive_outlets > 0 else 0
            
            avg_gmv_per_outlet_prev = total_gmv_prev / active_outlets_prev if active_outlets_prev > 0 else 0
            avg_gmv_per_outlet_productive_prev = total_gmv_prev / productive_outlets_prev if productive_outlets_prev > 0 else 0
            avg_order_per_outlet_prev = total_orders_prev / active_outlets_prev if active_outlets_prev > 0 else 0
            avg_order_per_outlet_productive_prev = total_orders_prev / productive_outlets_prev if productive_outlets_prev > 0 else 0

            df_ratio = get_open_closed_ratio_working(start_date_filter, end_date_filter)
            open_close_ratio = df_ratio["open_closed_ratio"].mean()
            df_ratio_prev = get_open_closed_ratio_working(start_date_prev, end_date_prev)
            open_close_ratio_prev = df_ratio_prev["open_closed_ratio"].mean()

            # growth percentage
            def calculate_growth(current, prev):
                if prev is not None and prev > 0:
                    return (current - prev) / prev * 100
                return 0

            # calculate growth
            gmv_per_outlet_growth = calculate_growth(avg_gmv_per_outlet, avg_gmv_per_outlet_prev)
            gmv_per_outlet_productive_growth = calculate_growth(avg_gmv_per_outlet_productive, avg_gmv_per_outlet_productive_prev)
            order_per_outlet_growth = calculate_growth(avg_order_per_outlet, avg_order_per_outlet_prev)
            order_per_outlet_productive_growth = calculate_growth(avg_order_per_outlet_productive, avg_order_per_outlet_productive_prev)

            act_rate_growth = calculate_growth(act_rate, act_rate_prev)
            ret_rate_growth = calculate_growth(ret_rate, ret_rate_prev)
            avg_act_time_growth = calculate_growth(avg_act_time, avg_act_time_prev)
            open_close_ratio_growth = calculate_growth(open_close_ratio, open_close_ratio_prev)
            
            # calculate outlet performance metric
            avg_gmv_per_outlet = total_gmv / active_outlets if active_outlets > 0 else 0
            avg_gmv_per_outlet_productive = total_gmv / productive_outlets if productive_outlets > 0 else 0
            avg_order_per_outlet = total_orders / active_outlets if active_outlets > 0 else 0
            avg_order_per_outlet_productive = total_orders / productive_outlets if productive_outlets > 0 else 0
            
            act_rate_display = f"{act_rate:.1%}" if act_rate is not None else "N/A"
            ret_rate_display = f"{ret_rate:.1%}" if ret_rate is not None else "N/A"
            avg_act_time_display = f"{avg_act_time:.1f} Hari" if avg_act_time is not None else "N/A"
            open_close_ratio_display = f"{open_close_ratio:.2f}%" if open_close_ratio > 0 else "0.00%"

            productivity_outlets = st.columns(4)
            productivity_outlets[0].metric("Activation Rate", act_rate_display, 
                delta=f"{act_rate_growth:.1f}% From last month",
                help="Persentase outlet terverifikasi yang berhasil aktif.")
            productivity_outlets[1].metric("Retention Rate", ret_rate_display, 
                delta=f"{ret_rate_growth:.1f}% From last month",
                help="Persentase outlet yang tetap aktif per periode.")
            productivity_outlets[2].metric("Open vs Closed Ratio", open_close_ratio_display, 
                delta=f"{open_close_ratio_growth:.1f}% From last month",
                help="Persentase waktu outlet benar-benar beroperasi (uptime).")
            productivity_outlets[3].metric("Avg Activation Time", avg_act_time_display, 
                delta=f"{avg_act_time_growth:.1f}% From last month",
                help="Jumlah hari sejak outlet mendaftar hingga outlet go-live")

            performance_outlets = st.columns(4)
            performance_outlets[0].metric("Avg GMV/Active Outlet", f"Rp. {avg_gmv_per_outlet:,.0f}", 
                delta=f"{gmv_per_outlet_growth:.1f}% From last month", 
                help="Rata-rata GMV per outlet aktif.")
            performance_outlets[1].metric("Avg GMV/Productive Outlet", f"Rp. {avg_gmv_per_outlet_productive:,.0f}", 
                delta=f"{gmv_per_outlet_productive_growth:.1f}% From last month", 
                help="Rata-rata GMV per outlet produktif.")
            performance_outlets[2].metric("Avg Order/Active Outlet", f"{avg_order_per_outlet:,.1f}", 
                delta=f"{order_per_outlet_growth:.1f}% From last month", 
                help="Rata-rata GMV per outlet aktif.")
            performance_outlets[3].metric("Avg Order/Procductive Outlet", f"{avg_order_per_outlet_productive:,.1f}", 
                delta=f"{order_per_outlet_productive_growth:.1f}% From last month", 
                help="Rata-rata jumlah pesanan per outlet produktif.")

            st.write("---")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                selected_metric_to_plot_outlet = st.segmented_control("Show Trend For:", 
                    options=["Activation Rate", "Retention Rate", "Open vs Closed Ratio"], 
                    default="Activation Rate",
                    key="outlet_trend_control")
            with col2:
                outlet_granularity_selection = st.selectbox(
                    "View Trend By:", ("Monthly", "Daily"),
                    key="outlet_granularity")
                
            df_outlet_trend_metrics = get_outlet_trend_metrics(df_outlet, df_order, start_date_filter, end_date_filter, outlet_granularity_selection.lower())

            # displayed chart
            if selected_metric_to_plot_outlet == "Activation Rate":
                color = "green" if act_rate_growth >= 0 else "red"
                arrow = "↑" if act_rate_growth >= 0 else "↓"

                st.markdown(f"""
                    <div style="font-size:24px; font-weight:600;">Activation Rate</div>
                    <div style="display:flex; align-items:center; gap:16px;">
                        <div style="font-size:32px; font-weight:700;">{act_rate_display}</div>
                        <div style="font-size:16px; color:{color};">
                            {arrow} {act_rate_growth:.1f}% From last month
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                
                try:
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        df_plot = df_outlet_trend_metrics.melt(
                            id_vars=['period_str'], 
                            value_vars=['Productive', 'Active'],
                            var_name='Category',
                            value_name='Count'
                        )
                        
                        fig = px.bar(
                            df_plot, 
                            x='period_str', 
                            y='Count', 
                            color='Category',
                            title="Productive & Active Outlets Status",
                            labels={'period_str': 'Period', 'Count': 'Number of Outlets'},
                            text='Count',
                            color_discrete_map={'Productive': '#fa7878', 'Active': '#fcd4d4'}
                        )
                        fig.update_layout(barmode='stack', legend_title_text='Outlet Status', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(t=60, l=80, r=160, b=25))
                        st.plotly_chart(fig, use_container_width=True)

                    # Grafik Pie Chart di kolom kedua
                    with col2:
                        latest_data = df_outlet_trend_metrics.iloc[-1]
                        pie_data = pd.DataFrame({
                            'Category': ['Productive', 'Active'],
                            'Count': [latest_data['Productive'], latest_data['Active']]
                        })

                        pie_fig = px.pie(
                            pie_data,
                            values='Count',
                            names='Category',
                            color='Category',
                            color_discrete_map={'Productive': '#fa7878', 'Active': '#fcd4d4'},
                            labels={'Count': 'Outlet Count', 'Category': 'Status'}
                        )
                        pie_fig.update_traces(textinfo='percent+value', textposition='inside')
                        pie_fig.update_layout(showlegend=True, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(r=140, l=20, t=60, b=0))
                        st.plotly_chart(pie_fig, use_container_width=True)
                except Exception as e:
                    st.warning(f"Error: Data tidak mencukupi untuk membuat grafik. {e}")
                    
                # try:
                #     df_plot = df_outlet_trend_metrics.melt(
                #         id_vars=['period_str'], 
                #         value_vars=['Productive', 'Active'],
                #         var_name='Category',
                #         value_name='Count'
                #     )
                    
                #     fig = px.bar(df_plot, 
                #                 x='period_str', 
                #                 y='Count', 
                #                 color='Category',
                #                 title="Productive & Active Outlets Status",
                #                 labels={'period_str': 'Period', 'Count': 'Number of Outlets'},
                #                 text='Count',
                #                 color_discrete_map={'Productive': '#fa7878', 'Active': '#fcd4d4'}
                #     )
                #     fig.update_layout(barmode='stack', legend_title_text='Outlet Status', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(t=60, l=80, r=180, b=25))
                #     st.plotly_chart(fig, use_container_width=True)

                # except Exception as e:
                #     st.warning(f"Error: Data aktivasi tidak tersedia. Pastikan fungsi ETL mengembalikan data yang benar. Pesan: {e}")
            
            elif selected_metric_to_plot_outlet == "Retention Rate":
                color = "green" if ret_rate_growth >= 0 else "red"
                arrow = "↑" if ret_rate_growth >= 0 else "↓"

                st.markdown(f"""
                    <div style="font-size:24px; font-weight:600;">Retention Rate</div>
                    <div style="display:flex; align-items:center; gap:16px;">
                        <div style="font-size:32px; font-weight:700;">{ret_rate_display}</div>
                        <div style="font-size:16px; color:{color};">
                            {arrow} {ret_rate_growth:.1f}% From last month
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                
                try:
                    df_retention_data = get_outlet_metrics_trend(start_date_filter, end_date_filter, granularity=outlet_granularity_selection.lower())
                
                    df_retention_data["date"] = pd.to_datetime(df_retention_data["date"]).dt.strftime(
                        "%Y-%m" if outlet_granularity_selection=="Monthly" else "%Y-%m-%d")
                    
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
                                text='Count',
                                color_discrete_map={'Churn': '#fa7878','Retained': '#fcd4d4'}
                    )
                    fig.update_layout(barmode='stack', legend_title_text='Retention Status', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(t=60, l=80, r=220, b=25))
                    st.plotly_chart(fig, use_container_width=True)

                except Exception as e:
                    st.warning(f"Error: Data retensi tidak tersedia. Pastikan fungsi ETL mengembalikan data yang benar. Pesan: {e}")
                    
            elif selected_metric_to_plot_outlet == "Open vs Closed Ratio":
                color = "green" if open_close_ratio_growth >= 0 else "red"
                arrow = "↑" if open_close_ratio_growth >= 0 else "↓"

                st.markdown(f"""
                    <div style="font-size:24px; font-weight:600;">Open vs Closed Ratio</div>
                    <div style="display:flex; align-items:center; gap:16px;">
                        <div style="font-size:32px; font-weight:700;">{open_close_ratio_display}</div>
                        <div style="font-size:16px; color:{color};">
                            {arrow} {open_close_ratio_growth:.1f}% From last month
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                
                try:
                    df_open_closed = get_open_closed_daily_trend(start_date_filter, end_date_filter, outlet_granularity_selection)

                    df_plot = df_open_closed.melt(
                        id_vars=['period'],
                        value_vars=['Close', 'Open'],
                        var_name='Status Outlet',
                        value_name='Count')
                    
                    fig = px.bar(df_plot,
                                x='period',
                                y='Count',
                                color='Status Outlet',
                                title="Open vs Closed Time by Outlet",
                                labels={'period': 'Periode', 'Count': 'Total Outlet',  'Status': 'Status'},
                                color_discrete_map={'Open': '#fcd4d4', 'Close': '#fa7878'},
                                hover_data={'Count': ':.2f'})
                    fig.update_layout(barmode='stack', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(t=60, l=80, r=200, b=25))
                    st.plotly_chart(fig, use_container_width=True)

                except Exception as e:
                    st.warning(f"Error: Data rasio open vs closed tidak tersedia. Pastikan fungsi ETL mengembalikan data yang benar. Pesan: {e}")

            st.write("---")
            col1, col2 = st.columns([2, 1])
            with col1:
                selected_metric_to_plot_outlet2 = st.segmented_control("Show Trend For:", 
                    options=["Activation Time", "Average GMV", "Average Order"], 
                    default="Activation Time",
                    key="outlet_trend_control2")
            with col2:
                outlet_granularity_selection2 = st.selectbox(
                    "View Trend By:", ("Monthly", "Daily"),
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
                    selected_column = 'avg_activation_days'
                    chart_title = "Average Outlet Activation Time"
                    y_axis_label = "Average days"
                    
                elif selected_metric_to_plot_outlet2 == "Average GMV":
                    color = "green" if gmv_per_outlet_productive_growth >= 0 else "red"
                    arrow = "↑" if gmv_per_outlet_productive_growth >= 0 else "↓"

                    st.markdown(f"""
                        <div style="font-size:24px; font-weight:600;">Average GMV/Outlet</div>
                        <div style="display:flex; align-items:center; gap:16px;">
                            <div style="font-size:32px; font-weight:700;">Rp {avg_gmv_per_outlet_productive:,.0f}</div>
                            <div style="font-size:16px; color:{color};">
                                {arrow} {gmv_per_outlet_productive_growth:.1f}% From last month
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    selected_column = 'avg_gmv_per_productive_outlet'
                    chart_title = "Average GMV/Outlet"
                    y_axis_label = "Average GMV"
                    
                elif selected_metric_to_plot_outlet2 == "Average Order":
                    color = "green" if order_per_outlet_productive_growth >= 0 else "red"
                    arrow = "↑" if order_per_outlet_productive_growth >= 0 else "↓"
                    st.markdown(f"""
                        <div style="font-size:24px; font-weight:600;">Average Order/Outlet</div>
                        <div style="display:flex; align-items:center; gap:16px;">
                            <div style="font-size:32px; font-weight:700;">{avg_order_per_outlet_productive:,.1f}</div>
                            <div style="font-size:16px; color:{color};">
                                {arrow} {order_per_outlet_productive_growth:.1f}% From last month
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    selected_column = 'avg_order_per_productive_outlet'
                    chart_title = "Rata-rata Jumlah Pesanan per Outlet Produktif"
                    y_axis_label = "Total orders"
                
                fig = px.line(
                    df_outlet_trend_metrics2, 
                    x='period_str', 
                    y=selected_column, 
                    title=chart_title,
                    labels={'periode_str': 'Periode', selected_column: y_axis_label},
                    markers=True
                )
                
                fig.update_traces(line_color='#FF4B4B')
                fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(t=60, l=80, r=80, b=25))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Tidak ada data untuk periode yang dipilih.")
                        
                
        with order_tab:
            st.subheader("Overview")
            avg_order_value = total_gross_revenue / success_order_count if total_orders > 0 else 0
            success_ratio = (success_order_count / total_orders * 100) if total_orders > 0 else 0.0

            avg_order_value_prev = total_gross_revenue_prev / total_orders_prev if total_orders_prev > 0 else 0
            success_ratio_prev = (success_order_count_prev / total_orders_prev * 100) if total_orders_prev > 0 else 0.0

            # growth
            aov_growth = ((avg_order_value - avg_order_value_prev) / avg_order_value_prev * 100) if avg_order_value_prev != 0 else 0
            success_ratio_growth = ((success_ratio - success_ratio_prev) / success_ratio_prev * 100) if success_ratio_prev != 0 else 0

            kpi_order_cols = st.columns(2)
            kpi_order_cols[0].metric("Average Order Value (AOV)", f"Rp {avg_order_value:,.0f}", delta=f"{aov_growth:.1f}% From last month", help="Nilai rata-rata transaksi per order.")
            kpi_order_cols[1].metric("Success Order Ratio", f"{success_ratio:.1f}%", delta=f"{success_ratio_growth:.1f}% From last month",help="Total order success (completed, disbursement completed, and disbursement progress) divide total orders.")
            
            st.write("---")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown(f"""
                <div style="font-size:24px; font-weight:600;">Average Order Value</div>
                <div style="display:flex; align-items:center; gap:16px;">
                    <div style="font-size:32px; font-weight:700;">{avg_order_value:,.0f}</div>
                    <div style="font-size:16px; color:{color};">
                        {arrow} {aov_growth:.1f}% From last month
                    </div>
                </div>
            """, unsafe_allow_html=True)
            # with col1:
            #     selected_metric_to_plot_outlet = st.segmented_control("Show Trend For:", 
            #         options=["Activation Rate", "Retention Rate", "Open vs Closed Ratio"], 
            #         default="Activation Rate",
            #         key="outlet_trend_control")
            with col2:
                order_granularity_selection = st.selectbox(
                    "View Trend By:", ("Monthly", "Daily"),
                    key="order_granularity")
            
            if order_granularity_selection == 'Monthly':
                period_range = pd.period_range(start=start_date_filter, end=end_date_filter, freq='M')
                all_periods = pd.DataFrame({'period_str': period_range.astype(str)})
            else: # Daily
                period_range = pd.date_range(start=start_date_filter, end=end_date_filter, freq='D')
                all_periods = pd.DataFrame({'period_str': period_range.strftime('%Y-%m-%d')})

            df_trend_source2 = df_financial_base.copy()
            if order_granularity_selection == 'Daily':
                df_trend_source2['period_str'] = df_trend_source2['order_date'].dt.strftime('%Y-%m-%d')
            else:
                df_trend_source2['period_str'] = df_trend_source2['order_date'].dt.to_period('M').astype(str)

            df_aov_data = df_trend_source2.groupby('period_str').agg(
                gross_revenue=('gross_revenue_order', 'sum'),
                orders=('order_id', 'nunique')
            ).reset_index()

            df_aov_data['aov'] = df_aov_data['gross_revenue'] / df_aov_data['orders'].replace(0, 1)

            df_trend2 = pd.merge(all_periods, df_aov_data, on='period_str', how='left').fillna(0)
            df_trend2 = df_trend2.sort_values('period_str').reset_index(drop=True)
            
            if not df_trend2.empty and 'aov' in df_trend2.columns:
                fig_aov_trend = px.line(df_trend2, x='period_str', y='aov', title=f"Average Order Value", labels={'Periode': order_granularity_selection, 'avg_order_value': 'Average Order Value'}, markers=True)
                fig_aov_trend.update_yaxes(tickprefix="Rp ", tickformat=",.0f")
                fig_aov_trend.update_layout(margin = dict(t=60, l=40, r=40, b=25), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                fig_aov_trend.update_traces(line_color='#F59E0B')
                st.plotly_chart(fig_aov_trend, use_container_width=True)
            else: st.info("No data for AOV trend.")
            
            st.write("---")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown(f"""
                <div style="font-size:24px; font-weight:600;">Success Order Ratio</div>
                <div style="display:flex; align-items:center; gap:16px;">
                    <div style="font-size:32px; font-weight:700;">{success_ratio:.1f}</div>
                    <div style="font-size:16px; color:{color};">
                        {arrow} {success_ratio_growth:.1f}% From last month
                    </div>
                </div>
            """, unsafe_allow_html=True)

            with col2:
                order_granularity_selection2 = st.selectbox(
                    "View Trend By:", ("Monthly", "Daily"),
                    key="order_granularity2")
            
            if order_granularity_selection2 == 'Daily':
                period_format = '%Y-%m-%d'
            else:
                period_format = '%Y-%m'

            df_trend_ratio = df_orders_filtered.copy()
            success_statuses = ['wc-completed', 'wc-disbursement-completed', 'wc-disbursement-progress']
            cancelled_status = 'wc-cancelled'
            
            df_trend_ratio['status_group'] = df_trend_ratio['status'].apply(
                lambda x: 'Success' if x in success_statuses else ('Cancelled' if x == cancelled_status else None)
            )
            df_trend_ratio.dropna(subset=['status_group'], inplace=True)
            if order_granularity_selection2 == 'Daily':
                df_trend_ratio['period_str'] = df_trend_ratio['order_date'].dt.strftime('%Y-%m-%d')
            else:
                df_trend_ratio['period_str'] = df_trend_ratio['order_date'].dt.to_period('M').astype(str)

            # 3. Agregasi data untuk setiap periode dan kategori
            df_trend_data = df_trend_ratio.groupby(['period_str', 'status_group']).agg(
                order_count=('order_id', 'nunique')
            ).reset_index()

            if not df_trend_data.empty:
                col1, col2 = st.columns([2, 1])
                with col1:
                    fig_bar = px.bar(
                        df_trend_data,
                        x='period_str',
                        y='order_count',
                        color='status_group',
                        title='Success vs Cancelled Orders Ratio',
                        labels={'order_count': 'Total Orders', 'period_str': 'Period'},
                        color_discrete_map={'Success': '#87d499', 'Cancelled': '#fa7878'},
                        text='order_count'
                    )
                    fig_bar.update_layout(barmode='stack', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(t=60, l=80, r=160, b=25))
                    fig_bar.update_traces(textposition='inside', insidetextfont_color='white')
                    st.plotly_chart(fig_bar, use_container_width=True)

                with col2:
                    latest_data = df_trend_data.groupby('status_group')['order_count'].sum().reset_index()
                    
                    fig_pie = px.pie(
                        latest_data,
                        values='order_count',
                        names='status_group',
                        title='Success vs cancel ratio',
                        color= 'status_group',
                        color_discrete_map={'Success': '#87d499', 'Cancelled': '#fa7878'},
                        labels={'order_count': 'Jumlah Pesanan', 'status_group': 'Status'}
                    )
                    fig_pie.update_traces(textinfo='percent+value', textposition='inside')
                    fig_pie.update_layout(showlegend=True, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(t=60, l=20, r=140,  b=0))
                    st.plotly_chart(fig_pie, use_container_width=True)

            else:
                st.info("Tidak ada data pesanan yang tersedia untuk rentang waktu ini.")
            
            # st.subheader("Sales Analytics by OFD")
            # ofd_metric = st.selectbox("Analyze OFD by:", options=["Gross Revenue", "Total Orders", "Average Order Value"])
            # if ofd_metric == "Gross Revenue":
            #     analysis_df = df_orders_filtered.groupby('order_source')['gross_revenue_order'].sum().reset_index()
            #     y_axis_label, title = 'gross_revenue_order', 'Gross Revenue by OFD'
            # elif ofd_metric == "Total Orders":
            #     analysis_df = df_orders_filtered.groupby('order_source')['order_id'].nunique().reset_index()
            #     analysis_df.rename(columns={'order_id': 'Total Orders'}, inplace=True)
            #     y_axis_label, title = 'Total Orders', 'Total Orders by OFD'
            # else: # AOV
            #     analysis_df = df_orders_filtered.groupby('order_source').agg(GrossRevenue=('gross_revenue_order', 'sum'), Orders=('order_id', 'nunique')).reset_index()
            #     analysis_df['AOV'] = analysis_df['GrossRevenue'] / analysis_df['Orders']
            #     y_axis_label, title = 'AOV', 'Average Order Value by OFD'
            
            # fig_ofd = px.bar(analysis_df.sort_values(by=y_axis_label, ascending=False), x='order_source', y=y_axis_label, title=title, color_discrete_sequence=['#FF4B4B'])
            # fig_ofd.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin = dict(t=80, l=40, r=40, b=25))
            # st.plotly_chart(fig_ofd, use_container_width=True)

        # with breakdown_tab:
        #     st.header("Detailed Revenue Breakdowns")
        #     st.info("Tabel di bawah ini akan ter-update secara otomatis berdasarkan semua filter yang aktif.")
        #     st.subheader("Revenue by Brand")
        #     revenue_by_brand = df_orders_filtered.groupby('brand_name')['gross_revenue_order'].sum().sort_values(ascending=False).reset_index()
        #     st.dataframe(revenue_by_brand.style.format({'gross_revenue_order': 'Rp {:,.0f}'}), use_container_width=True)
        #     st.write("---")
        #     st.subheader("Revenue by Outlet")
        #     revenue_by_outlet = df_orders_filtered.groupby(['brand_name', 'outlet_name'])['gross_revenue_order'].sum().sort_values(ascending=False).reset_index()
        #     st.dataframe(revenue_by_outlet.style.format({'gross_revenue_order': 'Rp {:,.0f}'}), use_container_width=True)
        #     st.write("---")
        #     st.subheader("Revenue by Order Source (OFD)")
        #     revenue_by_source = df_orders_filtered.groupby('order_source')['gross_revenue_order'].sum().sort_values(ascending=False).reset_index()
        #     st.dataframe(revenue_by_source.style.format({'gross_revenue_order': 'Rp {:,.0f}'}), use_container_width=True)
        #     st.write("---")
        #     st.subheader("Revenue by Owner")
        #     revenue_by_owner = df_orders_filtered.groupby('owner_name')['gross_revenue_order'].sum().sort_values(ascending=False).reset_index()
        #     st.dataframe(revenue_by_owner.style.format({'gross_revenue_order': 'Rp {:,.0f}'}), use_container_width=True)
    
else:
    st.warning("Tidak ada data yang cocok dengan filter yang Anda pilih.")
