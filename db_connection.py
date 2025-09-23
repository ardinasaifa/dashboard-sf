import os
from dotenv import load_dotenv
import psycopg2
from contextlib import contextmanager


load_dotenv()

@contextmanager
def get_connection():
    """
    Koneksi utama ke database DATAMART.
    Membaca konfigurasi dari file .env.
    """
    conn = None
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME"), 
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS")
        )
        
        yield conn
    except Exception as e:
        print(f"Gagal terhubung ke DATAMART: {e}")
        raise
    finally:
        if conn:
            conn.close()
            

@contextmanager
def get_dwh_connection():
    """
    Koneksi khusus ke database Data Warehouse (dwh-1).
    Digunakan untuk fungsi-fungsi yang butuh akses ke data mentah.
    """
    conn = None
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database="datawarehouse2", 
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS")
        )
        
        yield conn
    except Exception as e:
        print(f"Gagal terhubung ke dwh-1: {e}")
        raise
    finally:
        if conn:
            conn.close()
            