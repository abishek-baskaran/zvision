import sqlite3
import os

# Adjust this path to match your project structure if needed
DB_PATH = "/home/abishek/zvision/app/zvision.db"

def print_db_schema(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print(f"--- Printing SQLite schema for {db_path} ---\n")

    # Fetch table/index/view/trigger info
    cursor.execute("""
        SELECT name, sql
        FROM sqlite_master
        WHERE type IN ('table', 'index', 'view', 'trigger')
        ORDER BY name
    """)
    rows = cursor.fetchall()

    for row in rows:
        name, sql = row
        print(f"Name: {name}\nSQL: {sql}\n")

        # If this is a table (identified by SQL starting with "CREATE TABLE"), 
        # print up to 5 sample rows if they exist.
        if sql and sql.strip().lower().startswith("create table"):
            print_sample_rows(conn, name)

    conn.close()

def print_sample_rows(conn, table_name):
    """
    Prints up to 5 rows from the given table.
    """
    print(f"Sample rows from table '{table_name}':")
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
        rows = cursor.fetchall()
        if not rows:
            print("  (No rows found)\n")
            return
        # Print the column names
        col_names = [desc[0] for desc in cursor.description]
        print("  Columns:", col_names)
        # Print each row
        for row in rows:
            print("  ", row)
        print()
    except sqlite3.Error as e:
        # Some objects in sqlite_master might not be actual tables or have unexpected structure
        print(f"  Could not fetch rows due to error: {e}\n")

if __name__ == "__main__":
    print_db_schema(DB_PATH)
