#!/usr/bin/env python3
import requests
import json
import sys
import os

# Configuration
API_URL = "http://localhost:8000/api"  # Update with your actual API URL
USERNAME = "admin"
PASSWORD = "password"

# Helper function to get an access token
def get_token():
    response = requests.post(
        f"{API_URL}/auth/login",
        json={"username": USERNAME, "password": PASSWORD}
    )
    if response.status_code != 200:
        print(f"Error logging in: {response.status_code}")
        print(response.text)
        sys.exit(1)
    
    return response.json()["access_token"]

# 1. Get token
token = get_token()
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# 2. Get list of stores
response = requests.get(f"{API_URL}/stores", headers=headers)
if response.status_code != 200:
    print(f"Error getting stores: {response.status_code}")
    print(response.text)
    sys.exit(1)

stores = response.json()
if not stores:
    print("No stores found. Please create a store first.")
    sys.exit(1)

store_id = stores[0]["store_id"]
print(f"Using store ID: {store_id}")

# 3. Get list of cameras for the store
response = requests.get(f"{API_URL}/stores/{store_id}/cameras", headers=headers)
if response.status_code != 200:
    print(f"Error getting cameras: {response.status_code}")
    print(response.text)
    sys.exit(1)

cameras = response.json()
if not cameras:
    print("No cameras found for this store. Creating one...")
    
    # Create a camera
    response = requests.post(
        f"{API_URL}/cameras",
        headers=headers,
        json={
            "store_id": store_id,
            "camera_name": "Test Camera",
            "source": "test_source"
        }
    )
    if response.status_code != 200:
        print(f"Error creating camera: {response.status_code}")
        print(response.text)
        sys.exit(1)
    
    camera = response.json()
    camera_id = camera["camera_id"]
else:
    camera_id = cameras[0]["camera_id"]

print(f"Using camera ID: {camera_id}")

# 4. Set calibration data
calibration_data = {
    "roi": {
        "x1": 100,
        "y1": 100,
        "x2": 500,
        "y2": 400
    },
    "line": {
        "startX": 200,
        "startY": 300,
        "endX": 400,
        "endY": 300
    }
}

print("\nSetting calibration data:")
print(json.dumps(calibration_data, indent=2))

response = requests.post(
    f"{API_URL}/cameras/{camera_id}/calibrate",
    headers=headers,
    json=calibration_data
)

print("\nPOST Response:")
print(f"Status code: {response.status_code}")
print(json.dumps(response.json(), indent=2))

# 5. Get calibration data
print("\nGetting calibration data:")
response = requests.get(
    f"{API_URL}/cameras/{camera_id}/calibrate",
    headers=headers
)

print("\nGET Response:")
print(f"Status code: {response.status_code}")
print(json.dumps(response.json(), indent=2))

print("\nCalibration test completed successfully!") 