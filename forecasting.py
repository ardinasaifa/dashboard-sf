import pandas as pd
from prophet import Prophet
import streamlit as st

@st.cache_data
def prepare_forecast_data(df, metric_column):
    df_clean = df.copy()
    df_clean['order_date'] = pd.to_datetime(df_clean['order_date']).dt.floor('D')

    if metric_column == 'Total Orders':
        df_daily = df_clean.groupby('order_date').size().reset_index(name='y')
    else:
        df_daily = df_clean.groupby('order_date')[metric_column].sum().reset_index(name='y')

    df_daily.columns = ['ds', 'y']
    df_daily['ds'] = pd.to_datetime(df_daily['ds']).dt.tz_localize(None)

    # isi tanggal kosong
    df_daily = (
        df_daily
        .set_index('ds')
        .asfreq('D', fill_value=0)
        .reset_index()
        .sort_values('ds')
    )

    return df_daily


def run_prophet_forecast(df_daily, periods=30):
    
    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
        interval_width=0.95  # Rentang ketidakpastian 95%
    )
    
    # Tambahkan kalender libur Indonesia agar prediksi lebih akurat (misal: Lebaran/Natal)
    model.add_country_holidays(country_name='ID')
    
    # Proses belajar dari data historis
    model.fit(df_daily)
    
    future = model.make_future_dataframe(periods=periods)
    
    forecast = model.predict(future)
    
    return model, forecast