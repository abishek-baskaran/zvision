import sys
from pathlib import Path
import bcrypt

# Add parent directory to path so we can import from app
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.database.connection import get_connection

def create_test_user():
    """Create a test user in the database for testing"""
    print("Creating test user...")
    
    # Create admin user with password 'password'
    username = "admin"
    password = "password"
    
    # Hash the password using bcrypt
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if the user already exists
    cursor.execute('SELECT username FROM users WHERE username = ?', (username,))
    if cursor.fetchone():
        print(f"User '{username}' already exists.")
        conn.close()
        return
    
    # Create the users table if it doesn't exist (just in case)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            hashed_password TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT FALSE
        )
    ''')
    
    # Insert the user
    cursor.execute('''
        INSERT INTO users (username, hashed_password, is_admin)
        VALUES (?, ?, ?)
    ''', (username, hashed.decode('utf-8'), True))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Created test user '{username}' with password '{password}'")

if __name__ == "__main__":
    create_test_user() 