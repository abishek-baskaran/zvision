from app.database.connection import get_connection

def migrate_stores_table():
    """
    Migrates the stores table to include the location field.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Create a temporary table with the new schema
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stores_new (
                store_id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_name TEXT NOT NULL UNIQUE,
                location TEXT NOT NULL
            )
        ''')
        
        # Copy data from old table to new table
        cursor.execute('''
            INSERT INTO stores_new (store_id, store_name, location)
            SELECT store_id, store_name, 'Default Location' FROM stores
        ''')
        
        # Drop the old table
        cursor.execute('DROP TABLE stores')
        
        # Rename the new table to the original name
        cursor.execute('ALTER TABLE stores_new RENAME TO stores')
        
        conn.commit()
        print("Successfully migrated stores table")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    migrate_stores_table() 