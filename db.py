import sqlite3
import psycopg2
import dotenv

import os
from supabase import create_client, Client


dotenv.load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def create_table_polizei(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS polizei (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            time TEXT,
            district TEXT,
            url TEXT,
            details TEXT
        )
    """
    )
    conn.commit()
    cursor.close()
    print("Table 'polizei' created successfully.")
    return cursor


def create_table_meeting(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS meeting (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            time TEXT,
            district TEXT
        )
    """
    )
    conn.commit()
    cursor.close()
    print("Table 'meeting' created successfully.")
    return cursor


def insert_polizei_data(conn, data):
    cursor = conn.cursor()
    for item in data:
        cursor.execute(
            """
            INSERT INTO polizei (title, time, district, url, details)
            VALUES (?, ?, ?, ?, ?)
        """,
            (item["title"], item["time"], item["district"], item["url"], item["details"]),
        )
    conn.commit()
    cursor.close()
    print("Data inserted into 'polizei' table successfully.")


def insert_meeting_data(conn, data):
    cursor = conn.cursor()
    for item in data:
        cursor.execute(
            """
            INSERT INTO meeting (title, time, district)
            VALUES (?, ?, ?)
        """,
            (item["title"], item["time"], item["district"]),
        )
    conn.commit()
    cursor.close()
    print("Data inserted into 'meeting' table successfully.")


def fetch_polizei_data(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM polizei")
    rows = cursor.fetchall()
    cursor.close()
    return rows


def fetch_meeting_data(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM meeting")
    rows = cursor.fetchall()
    cursor.close()
    return rows


def delete_polizei_data(conn):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM polizei")
    conn.commit()
    cursor.close()
    print("Data deleted from 'polizei' table successfully.")


def delete_meeting_data(conn):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM meeting")
    conn.commit()
    cursor.close()
    print("Data deleted from 'meeting' table successfully.")


def delete_all_data(conn):
    delete_polizei_data(conn)
    delete_meeting_data(conn)
    print("All data deleted from both tables successfully.")


def create_tables(conn):
    create_table_polizei(conn)
    create_table_meeting(conn)
    print("All tables created successfully.")


def drop_tables(conn):
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS polizei")
    cursor.execute("DROP TABLE IF EXISTS meeting")
    conn.commit()
    cursor.close()
    print("All tables dropped successfully.")


def connect_db(db_name):

    conn = sqlite3.connect(db_name)
    print(f"Connected to database '{db_name}' successfully.")
    return conn


def connect_postgres_db():

    conn = psycopg2.connect(
        dbname="your_db_name",
        user="your_username",
        password="your_password",
        host="localhost",
        port="5432",
    )
    print("Connected to PostgreSQL database successfully.")
    return conn


def insert_into_supabase_polizei(data):
    for item in data:
        supabase.table("polizei").insert(item).execute()
    print("Data inserted into Supabase 'polizei' table successfully.")


def upsert_into_supabase_polizei(data):
    for item in data:
        supabase.table("polizei").upsert(item).execute()
    print("Data upserted into Supabase 'polizei' table successfully.")


def upsert_into_supabase_meeting(data):
    for item in data:
        supabase.table("meeting").upsert(item).execute()
    print("Data upserted into Supabase 'meeting' table successfully.")


def find_meeting_by_keyword_supabase(keyword):
    data = supabase.table("meeting").select("*").ilike("Thema", f"%{keyword}%").execute()
    if data.data:
        print(f"Meeting found with keyword '{keyword}': {data.data}")
        return data.data
    else:
        print(f"No meeting found with keyword '{keyword}'.")
        
        
def find_polizei_by_keyword_supabase(keyword):
    data = supabase.table("polizei").select("*").ilike("details", f"%{keyword}%").execute()
    if data.data:
        print(f"Polizei record found with keyword '{keyword}': {data.data}")
        return data.data
    else:
        print(f"No polizei record found with keyword '{keyword}'.")


def find_meeting_by_datum_and_keyword_supabase(datum, keyword):
    data = supabase.table("meeting").select("*").ilike("Thema", f"%{keyword}%").eq("Datum", datum).execute()
    if data.data:
        print(f"Meeting found with keyword '{keyword}' and datum '{datum}': {data.data}")
        return data.data
    else:
        print(f"No meeting found with keyword '{keyword}' and datum '{datum}'.")
        
        


def close_db(conn):
    conn.close()
    print("Database connection closed successfully.")


def main():
    db_name = "polizei.db"
    conn = connect_db(db_name)

    # Create tables
    create_tables(conn)

    # Drop tables (for testing purposes)
    drop_tables(conn)

    # Close the database connection
    close_db(conn)
