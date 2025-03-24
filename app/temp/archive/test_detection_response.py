import requests
import json
import sys
import time

# Configuration
BASE_URL = "http://localhost:8000/api"

def test_detection_response():
    """Test the enhanced detection API response format"""
    print("\n=== Testing Detection API Response Format ===")
    
    # First, list all cameras to select one for testing
    try:
        # Get all stores
        stores_response = requests.get(f"{BASE_URL}/stores")
        if stores_response.status_code != 200:
            print(f"Failed to retrieve stores: {stores_response.text}")
            return
            
        stores = stores_response.json()
        if not stores:
            print("No stores found, please create a store first")
            return
            
        # Get cameras for the first store
        store_id = stores[0]["store_id"]
        cameras_response = requests.get(f"{BASE_URL}/cameras?store_id={store_id}")
        
        if cameras_response.status_code != 200:
            print(f"Failed to retrieve cameras: {cameras_response.text}")
            return
            
        cameras_data = cameras_response.json()
        cameras = cameras_data.get("cameras", [])
        
        if not cameras:
            print(f"No cameras found for store_id={store_id}")
            return
            
        # Use the first camera for testing
        camera_id = cameras[0]["camera_id"]
        
        # Test both methods to trigger detection
        # 1. Query parameter method
        query_response = requests.post(f"{BASE_URL}/detect?camera_id={camera_id}")
        print("\nDetection API Response (query parameter):")
        print(f"Status Code: {query_response.status_code}")
        
        if query_response.status_code == 200:
            response_data = query_response.json()
            print(json.dumps(response_data, indent=2))
            
            # Validate response format
            required_fields = ["status", "bounding_boxes", "crossing_detected"]
            missing_fields = [field for field in required_fields if field not in response_data]
            
            if missing_fields:
                print(f"ERROR: Response missing required fields: {missing_fields}")
            else:
                print("✅ Response format valid")
                
            # If an event was created, test the logs endpoint
            if response_data.get("crossing_detected") and response_data.get("event_id"):
                # Wait for database to update
                time.sleep(1)
                
                event_id = response_data.get("event_id")
                logs_response = requests.get(f"{BASE_URL}/logs?store_id={store_id}")
                
                if logs_response.status_code == 200:
                    logs_data = logs_response.json()
                    events = logs_data.get("events", [])
                    found_event = False
                    
                    for event in events:
                        if event.get("event_id") == event_id:
                            found_event = True
                            print(f"\nEvent found in logs API with correct event_id: {event_id}")
                            print(json.dumps(event, indent=2))
                            break
                    
                    if not found_event:
                        print(f"ERROR: Event with event_id={event_id} not found in logs API")
        
        # 2. JSON body method
        print("\nTesting Detection API Response (JSON body):")
        json_response = requests.post(
            f"{BASE_URL}/detect", 
            json={"camera_id": str(camera_id)}
        )
        print(f"Status Code: {json_response.status_code}")
        
        if json_response.status_code == 200:
            response_data = json_response.json()
            print(json.dumps(response_data, indent=2))
            
            # Validate response format
            required_fields = ["status", "bounding_boxes", "crossing_detected"]
            missing_fields = [field for field in required_fields if field not in response_data]
            
            if missing_fields:
                print(f"ERROR: Response missing required fields: {missing_fields}")
            else:
                print("✅ Response format valid")
                
    except Exception as e:
        print(f"Error during test: {str(e)}")

if __name__ == "__main__":
    # Run the test
    test_detection_response() 