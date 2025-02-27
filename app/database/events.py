from .connection import get_connection
from typing import List, Dict

def initialize_events_table():
    """
    Creates the 'entry_exit_events' table if it doesn't exist.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

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

        return cursor.lastrowid

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

    finally:
        if conn:
            conn.close()


