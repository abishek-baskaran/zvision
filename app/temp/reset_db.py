import sys
from .connection import get_connection
from . import initialize_db

def reset_db():
    """
    Drops the known tables (calibrations, cameras, events, stores), then recreates them
    by calling `initialize_db()`.
    ALL DATA WILL BE LOST!
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Drop tables in reverse order of foreign-key dependencies (if any)
    known_tables = [
        "calibrations",        # references cameras(camera_id)
        "cameras",             # references stores(store_id)
        "entry_exit_events",   # references stores(store_id)
        "stores"
    ]

    for table in known_tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table};")

    conn.commit()
    conn.close()

    # Re-initialize all tables
    initialize_db()
    print("Database has been fully reset and reinitialized.")

if __name__ == "__main__":
    # Optional: confirm with user before wiping the DB
    ans = input("This will DROP all known tables! Continue? [y/N] ").strip().lower()
    if ans == 'y':
        reset_db()
    else:
        print("Operation cancelled.")
