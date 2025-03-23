from app.database.connection import get_connection
from app.database import initialize_db

def reset_db():
    """
    Drops all tables in the database, then reinitializes them via initialize_db().
    ALL DATA WILL BE LOST.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = cursor.fetchall()
    
    # Drop all tables
    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table[0]};")
    
    conn.commit()
    conn.close()

    # Recreate fresh tables
    initialize_db()
    print("Database has been reset and reinitialized.")

if __name__ == "__main__":
    ans = input("This will DROP all tables in the database! Continue? [y/N] ").strip().lower()
    if ans == 'y':
        reset_db()
    else:
        print("Operation cancelled.")
