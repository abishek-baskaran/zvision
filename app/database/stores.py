from app.database.connection import get_connection
from typing import List, Dict, Optional

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
                store_name TEXT NOT NULL UNIQUE,
                location TEXT NOT NULL
            )
        ''')
        conn.commit()
    finally:
        if conn:
            conn.close()

def add_store(store_name: str, location: str) -> int:
    """
    Inserts a new store into the 'stores' table.
    Returns the auto-incremented store_id of the newly inserted row.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('INSERT INTO stores (store_name, location) VALUES (?, ?)', (store_name, location))
        conn.commit()
        return cursor.lastrowid

    finally:
        if conn:
            conn.close()

def get_all_stores() -> List[Dict]:
    """
    Returns a list of all stores, each as a dict {store_id, store_name, location}.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT store_id, store_name, location FROM stores')
        rows = cursor.fetchall()

        results = []
        for r in rows:
            results.append({
                "store_id": r[0],
                "store_name": r[1],
                "location": r[2]
            })
        return results

    finally:
        if conn:
            conn.close()

def get_store_by_id(store_id: int) -> Optional[Dict]:
    """
    Fetch a single store by its store_id, returning None if not found.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT store_id, store_name, location FROM stores WHERE store_id=?', (store_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "store_id": row[0],
            "store_name": row[1],
            "location": row[2]
        }
    finally:
        if conn:
            conn.close()
