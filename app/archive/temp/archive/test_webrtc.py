#!/usr/bin/env python3
"""
Test script for WebRTC signaling endpoint
"""
import asyncio
import json
import sys
import os
import time
import argparse
import logging
from random import randint

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("webrtc_test")

# Add project root to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

# Parse command line arguments
parser = argparse.ArgumentParser(description='Test WebRTC signaling endpoint')
parser.add_argument('--host', default='localhost', help='Server hostname')
parser.add_argument('--port', type=int, default=8000, help='Server port')
parser.add_argument('--camera', type=int, default=1, help='Camera ID to test')
parser.add_argument('--token', help='JWT token for authentication')
args = parser.parse_args()

# Configuration
API_URL = f"http://{args.host}:{args.port}/api"
CAMERA_ID = args.camera
USERNAME = "admin"
PASSWORD = "123456"

async def get_token():
    """Get an authentication token"""
    logger.info(f"Getting authentication token from {API_URL}/token")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{API_URL}/token",
            data={
                "username": USERNAME,
                "password": PASSWORD
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        ) as response:
            if response.status != 200:
                text = await response.text()
                logger.error(f"Failed to get token: {response.status} - {text}")
                return None
            
            data = await response.json()
            token = data.get("access_token")
            logger.info(f"Successfully retrieved authentication token: {token[:10]}...")
            return token

async def test_signaling_websocket(token):
    """Test the WebRTC signaling WebSocket endpoint"""
    ws_url = f"ws://{args.host}:{args.port}/api/ws/rtc-signaling/{CAMERA_ID}?token={token}"
    logger.info(f"Connecting to WebRTC signaling WebSocket: {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            logger.info("Connected to signaling WebSocket")
            
            # Expect initial connection message
            message = await websocket.recv()
            message_data = json.loads(message)
            logger.info(f"Received initial message: {message_data}")
            
            if message_data.get("type") == "connected":
                connection_id = message_data.get("connection_id")
                logger.info(f"Connection established with ID: {connection_id}")
                
                # Send an offer
                offer = {
                    "type": "offer",
                    "sdp": "v=0\r\no=- 1234567890 1 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\na=group:BUNDLE 0\r\na=msid-semantic: WMS\r\nm=video 9 UDP/TLS/RTP/SAVPF 96\r\nc=IN IP4 0.0.0.0\r\na=rtcp:9 IN IP4 0.0.0.0\r\na=ice-ufrag:XXXX\r\na=ice-pwd:XXXX\r\na=fingerprint:sha-256 XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX:XX\r\na=setup:actpass\r\na=mid:0\r\na=extmap:1 urn:ietf:params:rtp-hdrext:ssrc-audio-level\r\na=sendrecv\r\na=rtcp-mux\r\na=rtpmap:96 H264/90000\r\na=rtcp-fb:96 nack\r\na=rtcp-fb:96 nack pli\r\na=rtcp-fb:96 ccm fir\r\na=fmtp:96 level-asymmetry-allowed=1;packetization-mode=1;profile-level-id=42e01f\r\n"
                }
                
                await websocket.send(json.dumps(offer))
                logger.info("Sent WebRTC offer")
                
                # Wait for additional messages with a timeout
                try:
                    # Set a timeout to wait for messages
                    for _ in range(5):  # Wait for up to 5 seconds
                        try:
                            response = await asyncio.wait_for(websocket.recv(), timeout=1)
                            response_data = json.loads(response)
                            logger.info(f"Received response: {response_data}")
                            
                            # If we got an answer, we're good
                            if response_data.get("type") == "answer":
                                logger.info("Successfully received WebRTC answer")
                                return True
                        except asyncio.TimeoutError:
                            # No message received within the timeout
                            continue
                    
                    logger.warning("Timed out waiting for WebRTC answer")
                    return False
                    
                except Exception as e:
                    logger.error(f"Error waiting for additional messages: {e}")
                    return False
            else:
                logger.error(f"Unexpected initial message: {message_data}")
                return False
    except Exception as e:
        logger.error(f"Error connecting to signaling WebSocket: {e}")
        return False

async def test_detection_data_websocket(token):
    """Test the detection data WebSocket endpoint"""
    frame_rate = 5
    ws_url = f"ws://{args.host}:{args.port}/api/ws/detection-data/{CAMERA_ID}?token={token}&frame_rate={frame_rate}"
    logger.info(f"Connecting to detection data WebSocket: {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            logger.info("Connected to detection data WebSocket")
            
            # Expect initial connection message
            message = await websocket.recv()
            message_data = json.loads(message)
            logger.info(f"Received initial message: {message_data}")
            
            # Wait for detection messages
            try:
                start_time = time.time()
                while time.time() - start_time < 10:  # Wait for up to 10 seconds
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=1)
                        message_data = json.loads(message)
                        
                        # Only log status and detection count to avoid cluttering
                        if "detections" in message_data:
                            detection_count = len(message_data.get("detections", []))
                            logger.info(f"Received detection data: status={message_data.get('status', 'unknown')}, {detection_count} detections")
                        else:
                            logger.info(f"Received message: {message_data}")
                            
                    except asyncio.TimeoutError:
                        # No message received within the timeout
                        continue
                
                logger.info("Completed detection data test")
                return True
                
            except Exception as e:
                logger.error(f"Error receiving detection messages: {e}")
                return False
    except Exception as e:
        logger.error(f"Error connecting to detection data WebSocket: {e}")
        return False

async def test_video_websocket(token):
    """Test the WebRTC video WebSocket endpoint"""
    ws_url = f"ws://{args.host}:{args.port}/api/ws/rtc-video/{CAMERA_ID}?token={token}"
    logger.info(f"Connecting to video WebSocket: {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            logger.info("Connected to video WebSocket")
            
            # Expect initial connection message
            message = await websocket.recv()
            message_data = json.loads(message)
            logger.info(f"Received initial message: {message_data}")
            
            # Wait for a few video frames
            try:
                frame_count = 0
                start_time = time.time()
                while time.time() - start_time < 5 and frame_count < 3:  # Wait for up to 5 seconds or 3 frames
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=1)
                        message_data = json.loads(message)
                        
                        if "frame" in message_data:
                            frame_count += 1
                            logger.info(f"Received video frame {frame_count}")
                        else:
                            logger.info(f"Received message: {message_data}")
                            
                    except asyncio.TimeoutError:
                        # No message received within the timeout
                        continue
                
                if frame_count > 0:
                    logger.info(f"Successfully received {frame_count} video frames")
                    return True
                else:
                    logger.warning("No video frames received")
                    return False
                
            except Exception as e:
                logger.error(f"Error receiving video frames: {e}")
                return False
    except Exception as e:
        logger.error(f"Error connecting to video WebSocket: {e}")
        return False

async def main():
    """Main test function"""
    logger.info("Starting WebRTC endpoint tests")
    
    # Get authentication token
    token = await get_token()
    if not token:
        logger.error("Failed to get authentication token, aborting tests")
        return
    
    # Test signaling WebSocket
    logger.info("Testing WebRTC signaling endpoint...")
    signaling_result = await test_signaling_websocket(token)
    logger.info(f"Signaling endpoint test {'PASSED' if signaling_result else 'FAILED'}")
    
    # Test detection data WebSocket
    logger.info("Testing detection data endpoint...")
    detection_result = await test_detection_data_websocket(token)
    logger.info(f"Detection data endpoint test {'PASSED' if detection_result else 'FAILED'}")
    
    # Test video WebSocket
    logger.info("Testing video WebSocket endpoint...")
    video_result = await test_video_websocket(token)
    logger.info(f"Video WebSocket test {'PASSED' if video_result else 'FAILED'}")
    
    # Overall result
    all_passed = signaling_result and detection_result and video_result
    logger.info(f"All tests {'PASSED' if all_passed else 'FAILED'}")

if __name__ == "__main__":
    asyncio.run(main()) 