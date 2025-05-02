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
    
def insert_only_new_polizei_data(data):
 
    existing_result = supabase.table("polizei").select("time").execute()
    existing_times = set(record.get('time') for record in existing_result.data)
    
    new_data = [item for item in data if item.get('time') not in existing_times]
    
    #print(f"total: {len(data)}")
    print(f"new: {len(new_data)}")
    
    if new_data:
        success_count = 0
        for item in new_data:
            try:
                supabase.table("polizei").insert(item).execute()
                success_count += 1
            except Exception as e:
                print(f"error: {str(e)}")
        
        print(f"total inserted {success_count} new records")
        return success_count
    else:
        print("no new records")
        return 0
    
def insert_only_new_meeting_data(data):
    # Fetch existing records from the database
    existing_result = supabase.table("meeting").select("von", "datum", "thema").execute()
    
    # Create a set of existing keys
    existing_keys = set()
    for record in existing_result.data:
        key = f"{record.get('von').strip()}|{record.get('datum').strip()}|{record.get('thema').strip()}"
        existing_keys.add(key)
        print(f"Existing key: {key}")  # Debugging output

    # Filter new data
    new_data = []
    for item in data:
        key = f"{item.get('Von').strip()}|{item.get('Datum').strip()}|{item.get('Thema').strip()}"
        print(f"Checking key: {key}")  # Debugging output
        if key not in existing_keys:
            print(f"New key found: {key}")  # Debugging output
            new_data.append(item)
        else:
            print(f"Key already exists: {key}")

    # Print the number of new records
    print(f"New records: {len(new_data)}")
    def convert_keys_to_lowercase(item):
        return {key.lower(): value for key, value in item.items()}

    new_data_lowercase = [convert_keys_to_lowercase(item) for item in new_data]
    # Insert new records into the database in batches
    if new_data_lowercase:
        batch_size = 100  # Adjust the batch size as needed
        success_count = 0

        for i in range(0, len(new_data_lowercase), batch_size):
            batch = new_data_lowercase[i:i + batch_size]
            try:
                supabase.table("meeting").insert(batch).execute()
                success_count += len(batch)
            except Exception as e:
                print(f"Error inserting batch starting at index {i}: {str(e)}")

        print(f"Total inserted {success_count} new records")
        return success_count
    else:
        print("No new records to insert")
        return 0



def upsert_into_supabase_meeting(data):
    for item in data:
        supabase.table("meeting").upsert(item).execute()
    print("Data upserted into Supabase 'meeting' table successfully.")


def find_meeting_by_keyword_supabase(keyword):
    data = supabase.table("meeting").select("*").ilike("thema", f"%{keyword}%").execute()
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
    data = supabase.table("meeting").select("*").ilike("thema", f"%{keyword}%").eq("datum", datum).execute()
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
