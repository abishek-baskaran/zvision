import sqlite3
import os
from typing import List, Dict

DB_PATH = os.path.join(os.path.dirname(__file__), "zvision.db")

def get_connection():
    """
    Returns a connection to the SQLite database.
    Creates 'zvision.db' in the current folder if it doesn't exist.
    """
    return sqlite3.connect(DB_PATH)

def initialize_db():
    """
    Creates the 'stores' and 'entry_exit_events' tables if they don't exist.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Create 'stores' table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stores (
                store_id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_name TEXT NOT NULL UNIQUE
            )
        ''')
        
        # Create 'entry_exit_events' table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS entry_exit_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                clip_path TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (store_id) REFERENCES stores(store_id)
            )
        ''')
        conn.commit()
    except sqlite3.Error as e:
        raise RuntimeError(f"Database initialization error: {e}")
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

        # Retrieve the auto-generated store_id
        store_id = cursor.lastrowid
        return store_id

    except sqlite3.Error as e:
        raise RuntimeError(f"Error adding store '{store_name}': {e}")
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

    except sqlite3.Error as e:
        raise RuntimeError(f"Error retrieving all stores: {e}")
    finally:
        if conn:
            conn.close()

def add_event(store_id: int, event_type: str, clip_path: str, timestamp: str) -> int:
    """
    Inserts a new entry/exit event record into the 'entry_exit_events' table.
    Returns the auto-incremented event_id of the newly inserted row.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO entry_exit_events (store_id, event_type, clip_path, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (store_id, event_type, clip_path, timestamp))
        conn.commit()

        event_id = cursor.lastrowid
        return event_id

    except sqlite3.Error as e:
        raise RuntimeError(f"Error adding event (store_id={store_id}): {e}")
    finally:
        if conn:
            conn.close()

def get_events_for_store(store_id: int) -> List[Dict]:
    """
    Fetch all events for a particular store_id, sorted by event_id asc (or timestamp asc).
    Returns each row as a dict with event details.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT event_id, store_id, event_type, clip_path, timestamp
            FROM entry_exit_events
            WHERE store_id = ?
            ORDER BY event_id
        ''', (store_id,))
        rows = cursor.fetchall()

        results = []
        for r in rows:
            results.append({
                "event_id": r[0],
                "store_id": r[1],
                "event_type": r[2],
                "clip_path": r[3],
                "timestamp": r[4]
            })
        return results

    except sqlite3.Error as e:
        raise RuntimeError(f"Error retrieving events for store_id={store_id}: {e}")
    finally:
        if conn:
            conn.close()

# For testing the module directly:
if __name__ == "__main__":
    # Initialize the database
    initialize_db()

    # If no stores exist yet, add one
    stores = get_all_stores()
    if not stores:
        print("No stores found. Adding default store 'My First Store'...")
        new_store_id = add_store("My First Store")
        print(f"Added store: ID={new_store_id}")
    else:
        print("Existing stores:")
        for s in stores:
            print(s)

    # Get or create a store_id for testing
    if not stores:
        store_id = new_store_id
    else:
        store_id = stores[0]["store_id"]

    # Add a test event
    test_event_id = add_event(
        store_id=store_id,
        event_type="entry",
        clip_path="clips/sample_clip.mp4",
        timestamp="2025-02-20 10:00:00"
    )
    print(f"Test event added with event_id={test_event_id}")

    # Fetch and print all events for the chosen store
    events = get_events_for_store(store_id)
    print("Events for store_id=", store_id)
    for e in events:
        print(e)
