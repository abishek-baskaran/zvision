# app/database/calibration.py
from .connection import get_connection
from typing import Optional, Dict, Any

def initialize_calibration_table():
    """
    Creates the 'calibrations' table if it doesn't exist, referencing camera_id from cameras.
    NOTE: If you already had a calibrations table with TEXT camera_id, you can drop it first:
      DROP TABLE IF EXISTS calibrations;
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS calibrations (
            calibration_id INTEGER PRIMARY KEY AUTOINCREMENT,
            camera_id INTEGER NOT NULL UNIQUE,
            line_start_x REAL,
            line_start_y REAL,
            line_end_x REAL,
            line_end_y REAL,
            FOREIGN KEY (camera_id) REFERENCES cameras(camera_id)
        )
    ''')
    conn.commit()
    conn.close()

def store_calibration(camera_id: int, x1: float, y1: float, x2: float, y2: float) -> None:
    """
    Inserts or updates calibration data for a camera_id.
    If you only want one line per camera, consider using ON CONFLICT(camera_id) DO UPDATE, 
    but that requires a UNIQUE constraint on camera_id. 
    For multiple lines, just do a plain insert.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Option A: multiple lines => just insert
    # cursor.execute('''
    #     INSERT INTO calibrations (camera_id, line_start_x, line_start_y, line_end_x, line_end_y)
    #     VALUES (?, ?, ?, ?, ?)
    # ''', (camera_id, x1, y1, x2, y2))

    # Option B: single line => create a UNIQUE index on camera_id, then do upsert
    # e.g.:
    cursor.execute('''
        INSERT INTO calibrations (camera_id, line_start_x, line_start_y, line_end_x, line_end_y)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(camera_id) DO UPDATE SET
            line_start_x=excluded.line_start_x,
            line_start_y=excluded.line_start_y,
            line_end_x=excluded.line_end_x,
            line_end_y=excluded.line_end_y
    ''', (camera_id, x1, y1, x2, y2))

    conn.commit()
    conn.close()

def fetch_calibration_for_camera(camera_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieves calibration lines for a given camera_id.
    If you only want the latest line, you can LIMIT 1 by calibration_id desc.
    Otherwise, you might return a list if multiple lines are allowed.
    """
    conn = get_connection()
    cursor = conn.cursor()
    # If you want the newest line only, do: ORDER BY calibration_id DESC LIMIT 1
    cursor.execute('''
        SELECT calibration_id, camera_id, line_start_x, line_start_y, line_end_x, line_end_y
        FROM calibrations
        WHERE camera_id = ?
        ORDER BY calibration_id DESC
        LIMIT 1
    ''', (camera_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "calibration_id": row[0],
            "camera_id": row[1],
            "line_start_x": row[2],
            "line_start_y": row[3],
            "line_end_x": row[4],
            "line_end_y": row[5]
        }
    return None
