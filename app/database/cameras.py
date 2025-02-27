# app/database/cameras.py
from .connection import get_connection
from typing import List, Dict

def initialize_cameras_table():
    """
    Creates the 'cameras' table if it doesn't exist.
    Each camera belongs to a store_id. One store -> many cameras.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cameras (
            camera_id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_id INTEGER NOT NULL,
            camera_name TEXT,
            FOREIGN KEY (store_id) REFERENCES stores(store_id)
        )
    ''')
    conn.commit()
    conn.close()

def add_camera(store_id: int, camera_name: str) -> int:
    """
    Inserts a new camera for a given store_id, returns the new camera_id.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO cameras (store_id, camera_name)
        VALUES (?, ?)
    ''', (store_id, camera_name))
    conn.commit()

    new_id = cursor.lastrowid
    conn.close()
    return new_id

def get_cameras_for_store(store_id: int) -> List[Dict]:
    """
    Retrieves all cameras for a given store.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT camera_id, camera_name
        FROM cameras
        WHERE store_id = ?
    ''', (store_id,))
    rows = cursor.fetchall()
    conn.close()

    results = []
    for r in rows:
        results.append({
            "camera_id": r[0],
            "camera_name": r[1]
        })
    return results

def get_store_for_camera(camera_id: int) -> int:
    """
    Fetches the store_id associated with a given camera_id.
    Returns the store_id if found.
    Raises ValueError if the camera_id doesn't exist.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT store_id FROM cameras WHERE camera_id=?', (camera_id,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        raise ValueError(f"No camera found for camera_id={camera_id}")
    return row[0]
