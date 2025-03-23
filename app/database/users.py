from .connection import get_connection
from typing import Optional, Dict
import bcrypt

def initialize_users_table():
    """
    Creates the 'users' table if it doesn't exist.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                hashed_password TEXT NOT NULL,
                is_admin BOOLEAN DEFAULT FALSE
            )
        ''')
        conn.commit()
    finally:
        if conn:
            conn.close()

def add_user(username: str, password: str, is_admin: bool = False) -> int:
    """
    Inserts a new user into the 'users' table with bcrypt hashed password.
    Returns the new user_id.
    """
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, hashed_password, is_admin)
            VALUES (?, ?, ?)
        ''', (username, hashed.decode('utf-8'), is_admin))
        conn.commit()
        return cursor.lastrowid
    finally:
        if conn:
            conn.close()

def verify_user(username: str, password: str) -> Optional[Dict]:
    """
    Verifies user credentials. Returns user dict if valid, None otherwise.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, username, hashed_password, is_admin 
            FROM users 
            WHERE username = ?
        ''', (username,))
        user = cursor.fetchone()
        
        if user and bcrypt.checkpw(password.encode('utf-8'), user[2].encode('utf-8')):
            return {
                "user_id": user[0],
                "username": user[1],
                "is_admin": bool(user[3])
            }
        return None
    finally:
        if conn:
            conn.close() 