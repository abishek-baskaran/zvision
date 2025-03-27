import asyncio
import json
import websockets
import requests
import time
from datetime import datetime

# Authentication and WebSocket connection settings
API_BASE = "http://localhost:8000/api"
WS_BASE = "ws://localhost:8000/api"
USERNAME = "admin"  # Correct test credentials
PASSWORD = "123456"  # Updated with correct password
CAMERA_ID = 1  # Change this to a valid camera ID in your system

async def test_websocket_live_detection():
    """
    Test the WebSocket live detection endpoint by:
    1. Getting a JWT token via login
    2. Connecting to the WebSocket endpoint
    3. Receiving and verifying messages for a few seconds
    4. Disconnecting
    """
    print(f"\n{'=' * 50}")
    print(f"WEBSOCKET LIVE DETECTION TEST - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 50}\n")
    
    # Step 1: Get JWT Token
    print("1. Getting JWT token...")
    try:
        login_response = requests.post(
            f"{API_BASE}/token",
            data={"username": USERNAME, "password": PASSWORD}
        )
        
        if login_response.status_code != 200:
            print(f"❌ Login failed with status code: {login_response.status_code}")
            print(f"Response: {login_response.text}")
            return
        
        token = login_response.json().get("access_token")
        if not token:
            print("❌ No access_token found in login response")
            return
            
        print("✅ Successfully obtained JWT token")
    except Exception as e:
        print(f"❌ Exception during login: {str(e)}")
        return
    
    # Step 2: Connect to WebSocket
    print(f"\n2. Connecting to WebSocket at {WS_BASE}/ws/live-detections/{CAMERA_ID}?token={token[:10]}...")
    
    try:
        async with websockets.connect(f"{WS_BASE}/ws/live-detections/{CAMERA_ID}?token={token}") as websocket:
            print("✅ Successfully connected to WebSocket")
            
            # Step 3: Receive connection confirmation
            print("\n3. Waiting for connection confirmation...")
            response = await websocket.recv()
            connection_data = json.loads(response)
            
            if connection_data.get("status") == "connected":
                print("✅ Received connection confirmation:")
                print(f"   Message: {connection_data.get('message')}")
            else:
                print("❌ Did not receive proper connection confirmation:")
                print(f"   Received: {connection_data}")
            
            # Step 4: Receive and verify detection messages
            print("\n4. Receiving detection messages (waiting for 10 seconds)...")
            print("   Format verification:\n")
            
            start_time = time.time()
            message_count = 0
            
            try:
                while time.time() - start_time < 10:  # Test for 10 seconds
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    message_count += 1
                    
                    try:
                        detection_data = json.loads(response)
                        
                        # Check if it has the expected format
                        required_fields = ["camera_id", "timestamp", "detections", "status"]
                        missing_fields = [field for field in required_fields if field not in detection_data]
                        
                        if missing_fields:
                            print(f"❌ Message missing required fields: {missing_fields}")
                            print(f"   Received: {detection_data}")
                        else:
                            print(f"✅ Received message #{message_count} with {len(detection_data.get('detections', []))} detections")
                            
                            # Only print full message for the first detection
                            if message_count == 1:
                                print(f"   Sample message format: {json.dumps(detection_data, indent=2)}")
                            
                            # If this was a crossing event, highlight it
                            if detection_data.get("crossing_detected"):
                                event_type = detection_data.get("event", "unknown")
                                print(f"🔔 DETECTED EVENT: {event_type.upper()} at {detection_data.get('timestamp')}")
                    
                    except json.JSONDecodeError:
                        print(f"❌ Received non-JSON message: {response}")
                    
                    await asyncio.sleep(0.1)  # Small delay to prevent tight loop
            
            except asyncio.TimeoutError:
                if message_count == 0:
                    print("❌ No messages received within timeout period!")
                else:
                    print(f"ℹ️ No more messages received after {message_count} messages")
            
            print(f"\n✅ Received {message_count} messages over {time.time() - start_time:.1f} seconds")
            
            # Step 5: Close the connection
            print("\n5. Test complete, closing WebSocket connection...")
    
    except Exception as e:
        print(f"❌ Exception during WebSocket test: {str(e)}")
        return
    
    print("\n✅ WebSocket test completed successfully")
    print(f"{'=' * 50}\n")

if __name__ == "__main__":
    asyncio.run(test_websocket_live_detection()) 