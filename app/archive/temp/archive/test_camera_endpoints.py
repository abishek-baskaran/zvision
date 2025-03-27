import requests
import json
import sys
from pathlib import Path

# Add parent directory to path so we can import from app
sys.path.append(str(Path(__file__).parent.parent.parent))

# Base URL for API
BASE_URL = "http://localhost:8000/api"

def test_camera_endpoints():
    """Test the camera endpoints we've implemented"""
    print("Testing Camera API Endpoints")
    
    # Step 1: Get auth token
    print("\n1. Getting authentication token...")
    login_data = {
        "username": "admin",  # Default username from documentation
        "password": "password"  # Default password from documentation
    }
    
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    if response.status_code != 200:
        print(f"❌ Authentication failed: {response.status_code}")
        print(response.text)
        return

    token = response.json().get("access_token")
    print(f"✅ Authentication successful, got token")
    
    # Headers for authenticated requests
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Step 2: Create a camera (POST /api/cameras)
    print("\n2. Creating a camera...")
    camera_data = {
        "store_id": 1,  # Assuming store with ID 1 exists
        "camera_name": "Test Camera",
        "source": "rtsp://example.com/stream1"
    }
    
    response = requests.post(f"{BASE_URL}/cameras", headers=headers, json=camera_data)
    if response.status_code != 200:
        print(f"❌ Create camera failed: {response.status_code}")
        print(response.text)
    else:
        print(f"✅ Camera created successfully")
        camera = response.json()
        print(json.dumps(camera, indent=2))
        
        # Save camera_id for later tests
        camera_id = camera.get("camera_id")
        
        # Step 3: Get cameras for store (GET /api/stores/{store_id}/cameras)
        print(f"\n3. Getting cameras for store {camera_data['store_id']}...")
        response = requests.get(f"{BASE_URL}/stores/{camera_data['store_id']}/cameras", headers=headers)
        if response.status_code != 200:
            print(f"❌ Get cameras for store failed: {response.status_code}")
            print(response.text)
        else:
            print(f"✅ Got cameras for store")
            cameras = response.json()
            print(json.dumps(cameras, indent=2))
        
        # Step 4: Get single camera (GET /api/cameras/{camera_id})
        print(f"\n4. Getting camera {camera_id}...")
        response = requests.get(f"{BASE_URL}/cameras/{camera_id}", headers=headers)
        if response.status_code != 200:
            print(f"❌ Get camera failed: {response.status_code}")
            print(response.text)
        else:
            print(f"✅ Got camera")
            camera = response.json()
            print(json.dumps(camera, indent=2))
            
        # Alternative: Get cameras using query parameter
        print(f"\n5. Getting cameras with store_id query parameter...")
        response = requests.get(f"{BASE_URL}/cameras?store_id={camera_data['store_id']}", headers=headers)
        if response.status_code != 200:
            print(f"❌ Get cameras with query parameter failed: {response.status_code}")
            print(response.text)
        else:
            print(f"✅ Got cameras with query parameter")
            cameras = response.json()
            print(json.dumps(cameras, indent=2))

if __name__ == "__main__":
    test_camera_endpoints() 