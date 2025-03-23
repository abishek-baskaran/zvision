from app.database.connection import get_connection
from typing import Optional, Dict, Any

def initialize_calibration_table():
    """
    Creates the 'calibrations' table if it doesn't exist, referencing camera_id from cameras.
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
            crop_x1 REAL,
            crop_y1 REAL,
            crop_x2 REAL,
            crop_y2 REAL,
            orientation TEXT DEFAULT 'leftToRight',
            frame_rate INTEGER DEFAULT 5,
            FOREIGN KEY (camera_id) REFERENCES cameras(camera_id)
        )
    ''')
    conn.commit()
    conn.close()

def store_calibration(camera_id: int, x1: float, y1: float, x2: float, y2: float, 
                      crop_x1: float, crop_y1: float, crop_x2: float, crop_y2: float,
                      orientation: str = 'leftToRight', frame_rate: int = 5) -> None:
    """
    Inserts or updates calibration data for a camera_id.
    If you only want one line per camera, consider using ON CONFLICT(camera_id) DO UPDATE, 
    but that requires a UNIQUE constraint on camera_id. 
    For multiple lines, just do a plain insert.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO calibrations (camera_id, line_start_x, line_start_y, line_end_x, line_end_y, 
                                crop_x1, crop_y1, crop_x2, crop_y2, orientation, frame_rate)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(camera_id) DO UPDATE SET
            line_start_x=excluded.line_start_x,
            line_start_y=excluded.line_start_y,
            line_end_x=excluded.line_end_x,
            line_end_y=excluded.line_end_y,
            crop_x1=excluded.crop_x1,
            crop_y1=excluded.crop_y1,
            crop_x2=excluded.crop_x2,
            crop_y2=excluded.crop_y2,
            orientation=excluded.orientation,
            frame_rate=excluded.frame_rate
    ''', (camera_id, x1, y1, x2, y2, crop_x1, crop_y1, crop_x2, crop_y2, orientation, frame_rate))

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
        SELECT calibration_id, camera_id, line_start_x, line_start_y, line_end_x, line_end_y, 
               crop_x1, crop_y1, crop_x2, crop_y2, orientation, frame_rate
        FROM calibrations
        WHERE camera_id = ?
    ''', (camera_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "calibration_id": row[0],
            "camera_id": row[1],
            "line": {
                "line_start_x": row[2],
                "line_start_y": row[3],
                "line_end_x":   row[4],
                "line_end_y":   row[5]
            },
            "square": {
                "crop_x1": row[6],
                "crop_y1": row[7],
                "crop_x2": row[8],
                "crop_y2": row[9]
            },
            "orientation": row[10],
            "frame_rate": row[11]
        }

    return None
