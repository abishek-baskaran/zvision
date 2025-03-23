import sqlite3
import os
from app.config import DATABASE_PATH

# Use the configured database path
DB_PATH = DATABASE_PATH

def get_connection():
    """
    Returns a connection to the SQLite database,
    creating the database if it doesn't exist.
    """
    # Ensure directory exists
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
        
    return sqlite3.connect(DB_PATH)
