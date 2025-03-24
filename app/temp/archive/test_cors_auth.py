import requests
import json
import sys
from app.database.users import add_user

# Configuration
BASE_URL = "http://localhost:8000/api"
TEST_USER = {"username": "testuser", "password": "password123"}

def create_test_user():
    """Create test user if not exists"""
    try:
        add_user(TEST_USER["username"], TEST_USER["password"], is_admin=True)
        print("Created test user")
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            print("Test user already exists")
        else:
            print(f"User creation error: {str(e)}")

def test_cors_preflight():
    """Test OPTIONS request works for CORS preflight"""
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type, Authorization"
    }
    response = requests.options(f"{BASE_URL}/token", headers=headers)
    print("\n=== CORS Preflight Test ===")
    print(f"Status Code: {response.status_code}")
    print("Response Headers:")
    for key, value in response.headers.items():
        if key.startswith("access-control"):
            print(f"  {key}: {value}")
    
    if response.status_code == 200:
        print("✅ CORS Preflight Passed!")
    else:
        print("❌ CORS Preflight Failed!")

def test_auth_flow():
    """Test full authentication flow with JWT token"""
    print("\n=== Authentication Flow Test ===")
    
    # 1. Get token
    auth_data = {
        "username": TEST_USER["username"],
        "password": TEST_USER["password"]
    }
    auth_response = requests.post(
        f"{BASE_URL}/token", 
        data=auth_data,
        headers={"Origin": "http://localhost:3000"}
    )
    
    print(f"Auth Status: {auth_response.status_code}")
    if auth_response.status_code != 200:
        print(f"Auth Error: {auth_response.text}")
        return
    
    token_data = auth_response.json()
    token = token_data["access_token"]
    print(f"Got token: {token[:20]}...")
    
    # 2. Use token to access protected endpoint
    headers = {
        "Authorization": f"Bearer {token}",
        "Origin": "http://localhost:3000"
    }
    
    stores_response = requests.get(f"{BASE_URL}/stores", headers=headers)
    print(f"Protected Endpoint Status: {stores_response.status_code}")
    
    if stores_response.status_code == 200:
        print("✅ JWT Authentication Passed!")
    else:
        print(f"❌ JWT Authentication Failed: {stores_response.text}")

if __name__ == "__main__":
    # Create test user
    create_test_user()
    
    # Test CORS preflight
    test_cors_preflight()
    
    # Test authentication flow
    test_auth_flow() 