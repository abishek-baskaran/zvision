from .connection import get_connection
from typing import List, Dict, Optional

def initialize_events_table():
    """
    Creates the 'entry_exit_events' table if it doesn't exist.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if the table exists first
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='entry_exit_events'")
        table_exists = cursor.fetchone() is not None

        if not table_exists:
            # If table doesn't exist, create it with camera_id column
            cursor.execute('''
                CREATE TABLE entry_exit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    store_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    clip_path TEXT,
                    timestamp TEXT NOT NULL,
                    camera_id INTEGER,
                    FOREIGN KEY (store_id) REFERENCES stores(store_id),
                    FOREIGN KEY (camera_id) REFERENCES cameras(camera_id)
                )
            ''')
            conn.commit()
        else:
            # Check if camera_id column already exists
            cursor.execute("PRAGMA table_info(entry_exit_events)")
            columns = cursor.fetchall()
            column_names = [column[1] for column in columns]
            
            if 'camera_id' not in column_names:
                # Add the camera_id column if it doesn't exist
                cursor.execute('ALTER TABLE entry_exit_events ADD COLUMN camera_id INTEGER REFERENCES cameras(camera_id)')
                conn.commit()
                
            # Verify foreign key constraint for camera_id
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='entry_exit_events'")
            table_def = cursor.fetchone()[0]
            if "FOREIGN KEY (camera_id) REFERENCES cameras(camera_id)" not in table_def:
                # SQLite doesn't support ALTER TABLE to add constraints
                # We need to recreate the table with the constraint
                
                # 1. Enable foreign keys
                cursor.execute("PRAGMA foreign_keys = OFF")
                
                # 2. Rename the current table
                cursor.execute("ALTER TABLE entry_exit_events RENAME TO entry_exit_events_old")
                
                # 3. Create a new table with the proper constraint
                cursor.execute('''
                    CREATE TABLE entry_exit_events (
                        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        store_id INTEGER NOT NULL,
                        event_type TEXT NOT NULL,
                        clip_path TEXT,
                        timestamp TEXT NOT NULL,
                        camera_id INTEGER,
                        FOREIGN KEY (store_id) REFERENCES stores(store_id),
                        FOREIGN KEY (camera_id) REFERENCES cameras(camera_id)
                    )
                ''')
                
                # 4. Copy data from old table to new table
                cursor.execute('''
                    INSERT INTO entry_exit_events
                    (event_id, store_id, event_type, clip_path, timestamp, camera_id)
                    SELECT event_id, store_id, event_type, clip_path, timestamp, camera_id
                    FROM entry_exit_events_old
                ''')
                
                # 5. Drop the old table
                cursor.execute("DROP TABLE entry_exit_events_old")
                
                # 6. Re-enable foreign keys
                cursor.execute("PRAGMA foreign_keys = ON")
                
                conn.commit()
    finally:
        if conn:
            conn.close()

def add_event(store_id: int, event_type: str, clip_path: str, timestamp: str, camera_id: Optional[int] = None) -> int:
    """
    Inserts a new entry/exit event record into the 'entry_exit_events' table.
    Returns the auto-incremented event_id of the newly inserted row.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO entry_exit_events (store_id, event_type, clip_path, timestamp, camera_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (store_id, event_type, clip_path, timestamp, camera_id))
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
            SELECT event_id, store_id, event_type, clip_path, timestamp, camera_id
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
                "timestamp": r[4],
                "camera_id": r[5]
            })
        return results

    finally:
        if conn:
            conn.close()


