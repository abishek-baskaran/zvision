import sqlite3
import os

# Construct the path to zvision.db (one level up from database folder)
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "zvision.db")

def get_connection():
    """
    Returns a connection to the SQLite database,
    creating 'zvision.db' if it doesn't exist.
    """
    return sqlite3.connect(DB_PATH)
