from .connection import get_connection
from typing import List, Dict

def initialize_stores_table():
    """
    Creates the 'stores' table if it doesn't exist.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stores (
                store_id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_name TEXT NOT NULL UNIQUE
            )
        ''')
        conn.commit()
    finally:
        if conn:
            conn.close()

def add_store(store_name: str) -> int:
    """
    Inserts a new store into the 'stores' table.
    Returns the auto-incremented store_id of the newly inserted row.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('INSERT INTO stores (store_name) VALUES (?)', (store_name,))
        conn.commit()
        return cursor.lastrowid

    finally:
        if conn:
            conn.close()

def get_all_stores() -> List[Dict]:
    """
    Returns a list of all stores, each as a dict {store_id, store_name}.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT store_id, store_name FROM stores')
        rows = cursor.fetchall()

        results = []
        for r in rows:
            results.append({
                "store_id": r[0],
                "store_name": r[1]
            })
        return results

    finally:
        if conn:
            conn.close()
