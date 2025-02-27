# app/database/reset_db.py
from .connection import get_connection
from . import initialize_db

def reset_db():
    """
    Drops known tables, then reinitializes them via initialize_db().
    ALL DATA WILL BE LOST.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Adjust table list if you add cameras or other new tables
    known_tables = [
        "calibrations",
        "entry_exit_events",
        "stores",
        "cameras"
    ]

    for table in known_tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table};")
    conn.commit()
    conn.close()

    # Recreate fresh tables
    initialize_db()
    print("Database has been reset and reinitialized.")

if __name__ == "__main__":
    ans = input("This will DROP all known tables! Continue? [y/N] ").strip().lower()
    if ans == 'y':
        reset_db()
    else:
        print("Operation cancelled.")
