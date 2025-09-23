def load_dm_outlet():
    # Membaca seluruh tabel dm_outlet dari DATAMART. Ini satu-satunya fungsi yang akan dipanggil oleh app.py untuk data utama.
    print("--- [ETL] Membaca dari DATAMART: public.dm_outlet ---")
    try:
        # Menggunakan koneksi ke database DATAMART
        with get_connection() as conn:
            df_outlet = pd.read_sql("SELECT * FROM public.dm_outlet;", conn)
            
            if df_outlet.empty:
                st.error("Tabel Datamart (dm_order) kosong. Jalankan workflow n8n terlebih dahulu.")
                return pd.DataFrame()

            df_outlet['go_live'] = pd.to_datetime(df_outlet['order_date'])
            
            print(f"Berhasil mengambil {len(df_outlet)} baris dari dm_order.")
            return df_outlet
    except Exception as e:
        st.error(f"Gagal total memuat data dari DATAMART: {e}")
        return pd.DataFrame()