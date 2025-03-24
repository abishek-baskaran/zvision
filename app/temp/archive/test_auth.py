import requests
import sys
from app.database.users import add_user

# Configuration
BASE_URL = "http://localhost:8000/api"
TEST_USER = {"username": "testadmin", "password": "securepassword123"}

def create_test_user():
    """Create test user if not exists"""
    try:
        add_user(TEST_USER["username"], TEST_USER["password"], is_admin=True)
        print("Created test user")
    except Exception as e:
        print(f"User creation error: {str(e)}")

def test_authentication():
    """Test authentication flow with the API"""
    try:
        # Test successful authentication
        print("Testing valid credentials...")
        response = requests.post(
            f"{BASE_URL}/token",
            data={"username": TEST_USER["username"], "password": TEST_USER["password"]}
        )
        response.raise_for_status()
        token_data = response.json()
        print(f"Auth successful! Token: {token_data['access_token']}")

        # Test invalid credentials
        print("\nTesting invalid credentials...")
        bad_response = requests.post(
            f"{BASE_URL}/token",
            data={"username": "wronguser", "password": "wrongpass"}
        )
        print(f"Invalid auth response: {bad_response.status_code}")
        print(f"Response content: {bad_response.text}")

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    create_test_user()
    test_authentication() 