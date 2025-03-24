# ZVision Code Collection

This file contains relevant code sections from the ZVision project related to WebRTC, WebSockets, detection, and video streaming.

## Table of Contents

1. [WebRTC Implementation](#webrtc-implementation)
2. [WebSocket Implementation](#websocket-implementation)
3. [Detection Pipeline](#detection-pipeline)
4. [Camera Management](#camera-management)
5. [Test and Demo Files](#test-and-demo-files)
6. [Extract Script](#extract-script)

## WebRTC Implementation
File: `app/routes/webrtc.py`
```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, status, Request
from fastapi.responses import JSONResponse
from typing import Dict, List, Optional, Any
import json
import asyncio
import time
import uuid
import os
import cv2
import threading
import base64
import logging
from pydantic import BaseModel
import random
import re

from app.routes.websockets import verify_token
from app.database.cameras import get_camera_by_id
from app.routes.camera import _fetch_camera_source_by_id

router = APIRouter()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webrtc")

# Store active WebRTC connections and their signaling data
class RTCSignalingData(BaseModel):
    connection_id: str
    camera_id: int
    offer: Optional[Dict[str, Any]] = None
    answer: Optional[Dict[str, Any]] = None
    ice_candidates: List[Dict[str, Any]] = []

# Store active signaling connections
rtc_connections: Dict[str, RTCSignalingData] = {}

# Store connection_ids by camera_id for cleanup
camera_connections: Dict[int, List[str]] = {}

# Store camera streams
camera_streams = {}

def get_rtsp_stream(camera_id: int) -> Optional[str]:
    """Get the RTSP stream URL for a camera"""
    source_path = _fetch_camera_source_by_id(camera_id)
    if not source_path:
        logger.error(f"Camera source not found for camera_id={camera_id}")
        return None
    
    # Handle both file paths and RTSP URLs
    if source_path.startswith(('rtsp://', 'http://', 'https://')):
        return source_path
    
    # Local file path
    if os.path.exists(source_path):
        # Return the file path directly - we'll handle it as a video file
        return source_path
    
    return None

class RTSPStreamManager:
    """Manages RTSP streams for WebRTC connections"""
    
    def __init__(self, camera_id: int, source_path: str):
        self.camera_id = camera_id
        self.source_path = source_path
        self.active = False
        self.thread = None
        self.cap = None
        self.frame_queue = asyncio.Queue(maxsize=10)  # Limit queue size to avoid memory issues
        self.clients = set()
        self.main_loop = asyncio.get_event_loop()  # Store reference to main event loop
        logger.info(f"Created RTSP Stream Manager for camera {camera_id}, source: {source_path}")
    
    def start(self):
        """Start the stream in a background thread"""
        if self.active:
            return
        
        self.active = True
        self.thread = threading.Thread(target=self._stream_thread, daemon=True)
        self.thread.start()
        logger.info(f"Starting RTSP stream for camera {self.camera_id}")
    
    def stop(self):
        """Stop the stream"""
        self.active = False
        if self.cap:
            self.cap.release()
        
        if self.thread:
            self.thread.join(timeout=1.0)
        
        logger.info(f"Stopped RTSP stream for camera {self.camera_id}")
    
    def add_client(self, connection_id: str):
        """Add a client to this stream"""
        self.clients.add(connection_id)
        logger.info(f"Added client {connection_id} to camera {self.camera_id} stream")
    
    def remove_client(self, connection_id: str):
        """Remove a client from this stream"""
        if connection_id in self.clients:
            self.clients.remove(connection_id)
            logger.info(f"Removed client {connection_id} from camera {self.camera_id} stream")
        
        # If no more clients, stop the stream
        if not self.clients:
            logger.info(f"No more clients for camera {self.camera_id}, stopping stream")
            self.stop()
    
    def _stream_thread(self):
        """Background thread to read from RTSP stream"""
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Open the video capture
            self.cap = cv2.VideoCapture(self.source_path)
            
            if not self.cap.isOpened():
                logger.error(f"Failed to open video source: {self.source_path}")
                self.active = False
                return
            
            # Get video properties
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 30  # Default if unable to determine
            
            frame_delay = 1.0 / fps
            logger.info(f"Stream opened: {self.source_path}, FPS: {fps}")
            
            # Main streaming loop
            last_frame_time = time.time()
            
            while self.active:
                current_time = time.time()
                elapsed = current_time - last_frame_time
                
                # Try to maintain proper FPS
                if elapsed < frame_delay:
                    time.sleep(frame_delay - elapsed)
                
                ret, frame = self.cap.read()
                if not ret:
                    logger.warning(f"Failed to read frame from {self.source_path}")
                    # For video files, we might want to loop
                    if not self.source_path.startswith(('rtsp://', 'http://', 'https://')):
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    else:
                        # For streams, try to reconnect
                        time.sleep(1.0)
                        self.cap.release()
                        self.cap = cv2.VideoCapture(self.source_path)
                        continue
                
                last_frame_time = time.time()
                
                # Convert frame to JPEG for WebSocket transmission
                _, jpeg_frame = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                frame_data = jpeg_frame.tobytes()
                
                # Instead of base64 encoding, we could use binary WebSocket frames
                # But for testing/debugging, base64 is more convenient
                encoded_frame = base64.b64encode(frame_data).decode('utf-8')
                
                # Put frame in queue
                try:
                    # Use the thread's own event loop to run the coroutine
                    future = asyncio.run_coroutine_threadsafe(
                        self.frame_queue.put({
                            'frame': encoded_frame,
                            'timestamp': time.time()
                        }),
                        self.main_loop  # Use the stored main event loop
                    )
                    # Wait for the result with a timeout
                    future.result(timeout=0.1)
                except (asyncio.QueueFull, asyncio.TimeoutError, RuntimeError):
                    # Queue is full or operation timed out, skip this frame
                    pass
                except Exception as e:
                    logger.error(f"Error putting frame in queue: {e}")
        
        except Exception as e:
            logger.error(f"Error in stream thread: {e}")
        finally:
            if self.cap:
                self.cap.release()
            self.active = False

def get_or_create_stream(camera_id: int) -> Optional[RTSPStreamManager]:
    """Get or create an RTSP stream for a camera"""
    global camera_streams
    
    if camera_id in camera_streams:
        return camera_streams[camera_id]
    
    # Get the stream URL
    stream_url = get_rtsp_stream(camera_id)
    if not stream_url:
        return None
    
    # Create a new stream manager
    stream = RTSPStreamManager(camera_id, stream_url)
    camera_streams[camera_id] = stream
    return stream

def parse_sdp(sdp: str) -> Dict[str, Any]:
    """Parse SDP into a structured object for easier manipulation"""
    parsed = {
        'session': [],
        'media': []
    }
    
    current_media = None
    lines = sdp.split('\r\n' if '\r\n' in sdp else '\n')
    
    for line in lines:
        if not line:
            continue
            
        if line.startswith('m='):
            # Starting a new media section
            current_media = {
                'type': line[2:].split(' ')[0],
                'lines': [line]
            }
            parsed['media'].append(current_media)
        elif current_media is not None:
            # Within a media section
            current_media['lines'].append(line)
        else:
            # Session description
            parsed['session'].append(line)
    
    return parsed

def generate_matching_answer(offer_sdp: str) -> str:
    """Generate an SDP answer that matches the offer's m-line structure"""
    parsed_offer = parse_sdp(offer_sdp)
    
    # Extract session-level lines from offer (v=, o=, s=, t=, etc.)
    session_lines = parsed_offer['session']
    
    # Create our own session description
    session = [
        'v=0',
        'o=- ' + str(int(time.time())) + ' 1 IN IP4 127.0.0.1',
        's=-',
        't=0 0',
        'a=group:BUNDLE ' + ' '.join([str(i) for i in range(len(parsed_offer['media']))]),
        'a=msid-semantic: WMS'
    ]
    
    # Generate a proper fingerprint
    fingerprint_parts = []
    for _ in range(32):
        fingerprint_parts.append(f"{random.randint(0, 255):02X}")
    fingerprint = ":".join(fingerprint_parts)
    
    # Create an answer that follows the offer structure
    media_sections = []
    
    for i, media in enumerate(parsed_offer['media']):
        media_type = media['type']
        
        # Basic media line parsing to extract protocol and formats
        media_line = media['lines'][0]  # m=video 9 UDP/TLS/RTP/SAVPF 96 97 98...
        m_parts = media_line.split(' ')
        protocol = m_parts[2]
        formats = m_parts[3:]
        
        if media_type == 'video':
            media_section = [
                f'm=video 9 {protocol} {" ".join(formats)}',
                'c=IN IP4 0.0.0.0',
                'a=rtcp:9 IN IP4 0.0.0.0',
                f'a=ice-ufrag:{uuid.uuid4().hex[:4]}',
                f'a=ice-pwd:{uuid.uuid4().hex[:22]}',
                f'a=fingerprint:sha-256 {fingerprint}',
                'a=setup:active',
                f'a=mid:{i}',
                'a=extmap:1 urn:ietf:params:rtp-hdrext:ssrc-audio-level',
                'a=sendonly',
                'a=rtcp-mux'
            ]
            
            # Add codec-specific lines (find them in the offer)
            for line in media['lines']:
                if line.startswith('a=rtpmap:') or line.startswith('a=rtcp-fb:') or line.startswith('a=fmtp:'):
                    media_section.append(line)
            
            media_sections.append(media_section)
        
        elif media_type == 'audio':
            media_section = [
                f'm=audio 9 {protocol} {" ".join(formats)}',
                'c=IN IP4 0.0.0.0',
                'a=rtcp:9 IN IP4 0.0.0.0',
                f'a=ice-ufrag:{uuid.uuid4().hex[:4]}',
                f'a=ice-pwd:{uuid.uuid4().hex[:22]}',
                f'a=fingerprint:sha-256 {fingerprint}',
                'a=setup:active',
                f'a=mid:{i}',
                'a=extmap:1 urn:ietf:params:rtp-hdrext:ssrc-audio-level',
                'a=sendonly',
                'a=rtcp-mux'
            ]
            
            # Add codec-specific lines
            for line in media['lines']:
                if line.startswith('a=rtpmap:') or line.startswith('a=rtcp-fb:') or line.startswith('a=fmtp:'):
                    media_section.append(line)
            
            media_sections.append(media_section)
        
        elif media_type == 'application':
            # For data channels, create the section but avoid problematic attributes
            media_section = [
                f'm=application 9 {protocol} {" ".join(formats)}',
                'c=IN IP4 0.0.0.0',
                f'a=ice-ufrag:{uuid.uuid4().hex[:4]}',
                f'a=ice-pwd:{uuid.uuid4().hex[:22]}',
                f'a=fingerprint:sha-256 {fingerprint}',
                'a=setup:active',
                f'a=mid:{i}',
                'a=sctpmap:5000 webrtc-datachannel 1024'
            ]
            
            # Skip adding any data channel attributes from the offer
            # as they may cause compatibility issues
            
            media_sections.append(media_section)
        
        else:
            # For other media types, echo back most of the offer lines
            media_section = []
            for line in media['lines']:
                if line.startswith('m='):
                    media_section.append(line)
                elif line.startswith('c='):
                    media_section.append('c=IN IP4 0.0.0.0')
                elif line.startswith('a=ice-ufrag:'):
                    media_section.append(f'a=ice-ufrag:{uuid.uuid4().hex[:4]}')
                elif line.startswith('a=ice-pwd:'):
                    media_section.append(f'a=ice-pwd:{uuid.uuid4().hex[:22]}')
                elif line.startswith('a=fingerprint:'):
                    media_section.append(f'a=fingerprint:sha-256 {fingerprint}')
                elif line.startswith('a=setup:'):
                    media_section.append('a=setup:active')
                elif line.startswith('a=mid:'):
                    media_section.append(f'a=mid:{i}')
                # Skip problematic attributes
                elif line.startswith('a=max-message-size:'):
                    continue
                else:
                    media_section.append(line)
            
            media_sections.append(media_section)
    
    # Combine everything into an SDP string
    answer_lines = session + sum(media_sections, [])
    return '\n'.join(answer_lines)

# WebRTC signaling endpoints
@router.post("/rtc/offer/{camera_id}")
async def webrtc_offer(camera_id: int, request: Request, token: Optional[str] = Query(None)):
    """
    Accept WebRTC offer for a camera
    """
    # Verify the token
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication token")
        
    user = await verify_token(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")
    
    # Verify the camera exists
    camera = get_camera_by_id(camera_id)
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Camera with ID {camera_id} not found")
    
    # Get the JSON data from the request
    offer_data = await request.json()
    if not offer_data or "sdp" not in offer_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid SDP offer format")
    
    # Create a new connection ID
    connection_id = str(uuid.uuid4())
    
    # Store the connection data
    rtc_connections[connection_id] = RTCSignalingData(
        connection_id=connection_id,
        camera_id=camera_id,
        offer=offer_data
    )
    
    # Add to camera connections for cleanup
    if camera_id not in camera_connections:
        camera_connections[camera_id] = []
    camera_connections[camera_id].append(connection_id)
    
    # Initialize the stream (but don't start it yet)
    stream = get_or_create_stream(camera_id)
    if not stream:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                           detail=f"Failed to initialize stream for camera {camera_id}")
    
    # Add this client to the stream
    stream.add_client(connection_id)
    
    # Generate answer with matching m-lines
    answer_sdp = generate_matching_answer(offer_data["sdp"])
    
    # Create answer
    answer = {
        "type": "answer",
        "sdp": answer_sdp
    }
    
    # Store the answer
    rtc_connections[connection_id].answer = answer
    
    # Return the connection ID
    return {"connection_id": connection_id}

@router.get("/rtc/answer/{connection_id}")
async def webrtc_get_answer(connection_id: str, token: Optional[str] = Query(None)):
    """
    Get the WebRTC answer for a connection
    """
    # Verify the token
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication token")
        
    user = await verify_token(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")
    
    # Check if the connection exists
    if connection_id not in rtc_connections:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Connection ID {connection_id} not found")
    
    # Get the connection data
    connection_data = rtc_connections[connection_id]
    
    # Check if an answer is available
    if not connection_data.answer:
        # Return a 202 Accepted status to indicate processing
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"status": "pending", "message": "Answer not yet available"}
        )
    
    # Return the answer
    return {"answer": connection_data.answer}

@router.post("/rtc/ice-candidate/{connection_id}")
async def webrtc_ice_candidate(connection_id: str, request: Request, token: Optional[str] = Query(None)):
    """
    Add an ICE candidate for a connection
    """
    # Verify the token
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication token")
        
    user = await verify_token(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")
    
    # Check if the connection exists
    if connection_id not in rtc_connections:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Connection ID {connection_id} not found")
    
    # Get the ICE candidate data
    ice_data = await request.json()
    if not ice_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ICE candidate format")
    
    # Store the ICE candidate
    rtc_connections[connection_id].ice_candidates.append(ice_data)
    
    # Return a success response
    return {"status": "success", "message": "ICE candidate added"}

@router.get("/rtc/ice-candidates/{connection_id}")
async def webrtc_get_ice_candidates(connection_id: str, token: Optional[str] = Query(None)):
    """
    Get all ICE candidates for a connection
    """
    # Verify the token
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication token")
        
    user = await verify_token(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")
    
    # Check if the connection exists
    if connection_id not in rtc_connections:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Connection ID {connection_id} not found")
    
    # Get the connection data
    connection_data = rtc_connections[connection_id]
    
    # Return the ICE candidates
    return {"ice_candidates": connection_data.ice_candidates}

@router.websocket("/ws/rtc-signaling/{camera_id}")
async def rtc_signaling(websocket: WebSocket, camera_id: int, token: Optional[str] = Query(None)):
    """
    WebSocket endpoint for WebRTC signaling
    """
    # Verify token
    user = await verify_token(token)
    if not user:
        await websocket.close(code=1008, reason="Invalid authentication token")
        return
    
    # Verify camera exists
    camera = get_camera_by_id(camera_id)
    if not camera:
        await websocket.close(code=1008, reason=f"Camera with ID {camera_id} not found")
        return
    
    # Accept the connection
    await websocket.accept()
    
    # Create a new connection ID
    connection_id = str(uuid.uuid4())
    
    # Store the connection data
    rtc_connections[connection_id] = RTCSignalingData(
        connection_id=connection_id,
        camera_id=camera_id
    )
    
    # Add to camera connections for cleanup
    if camera_id not in camera_connections:
        camera_connections[camera_id] = []
    camera_connections[camera_id].append(connection_id)
    
    # Send connection info
    await websocket.send_json({
        "type": "connected",
        "connection_id": connection_id
    })
    
    try:
        # Main websocket loop
        while True:
            # Wait for a message
            message = await websocket.receive_json()
            
            # Process the message based on its type
            if "type" not in message:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid message format, missing 'type'"
                })
                continue
            
            message_type = message.get("type")
            
            if message_type == "offer":
                # Store the offer
                if "sdp" not in message:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid offer format, missing 'sdp'"
                    })
                    continue
                
                # Store the offer data
                rtc_connections[connection_id].offer = message
                await websocket.send_json({
                    "type": "offer_received",
                    "connection_id": connection_id
                })
                
                # Generate answer using the SDP parser and generator
                offer_sdp = message.get("sdp", "")
                answer_sdp = generate_matching_answer(offer_sdp)
                
                # Create answer
                answer = {
                    "type": "answer",
                    "sdp": answer_sdp
                }
                
                # Store the answer
                rtc_connections[connection_id].answer = answer
                
                # Get or create stream
                stream = get_or_create_stream(camera_id)
                if not stream:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Failed to initialize stream for camera {camera_id}"
                    })
                    continue
                
                # Add this client to the stream
                stream.add_client(connection_id)
                
                # Start the stream
                stream.start()
                
                # Send the answer
                await websocket.send_json(answer)
                
            elif message_type == "ice_candidate":
                # Store and broadcast an ICE candidate
                if "candidate" not in message:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid ICE candidate format, missing 'candidate'"
                    })
                    continue
                
                # Store the candidate
                rtc_connections[connection_id].ice_candidates.append(message)
                
                # Acknowledge
                await websocket.send_json({
                    "type": "ice_candidate_received",
                    "connection_id": connection_id
                })
            
            else:
                # Unknown message type
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                })
    
    except WebSocketDisconnect:
        logger.info(f"WebRTC signaling WebSocket disconnected for connection {connection_id}")
    except Exception as e:
        logger.error(f"Error in WebRTC signaling WebSocket: {e}")
    finally:
        # Clean up the connection
        if connection_id in rtc_connections:
            # Get the stream
            stream = camera_streams.get(camera_id)
            if stream:
                # Remove this client from the stream
                stream.remove_client(connection_id)
            
            # Remove the connection data
            del rtc_connections[connection_id]
            
            # Remove from camera connections
            if camera_id in camera_connections and connection_id in camera_connections[camera_id]:
                camera_connections[camera_id].remove(connection_id)

@router.websocket("/ws/rtc-video/{camera_id}")
async def rtc_video(websocket: WebSocket, camera_id: int, token: Optional[str] = Query(None)):
    """
    WebSocket endpoint for video frames
    """
    # Verify token
    user = await verify_token(token)
    if not user:
        await websocket.close(code=1008, reason="Invalid authentication token")
        return
    
    # Verify camera exists
    camera = get_camera_by_id(camera_id)
    if not camera:
        await websocket.close(code=1008, reason=f"Camera with ID {camera_id} not found")
        return
    
    # Accept the WebSocket connection
    await websocket.accept()
    
    # Generate a unique connection ID
    connection_id = str(uuid.uuid4())
    
    # Get or create stream
    stream = get_or_create_stream(camera_id)
    if not stream:
        await websocket.send_json({
            "status": "error",
            "message": f"Failed to initialize stream for camera {camera_id}"
        })
        await websocket.close(code=1011)
        return
    
    # Add this client to the stream
    stream.add_client(connection_id)
    
    # Start the stream
    stream.start()
    
    # Send initial message
    await websocket.send_json({
        "status": "connected",
        "message": f"Connected to video stream for camera {camera_id}"
    })
    
    try:
        # Main websocket loop
        while True:
            try:
                # Non-blocking check for frame with a timeout
                frame_data = await asyncio.wait_for(stream.frame_queue.get(), timeout=1.0)
                
                # Send the frame to the client
                await websocket.send_json({
                    "frame": frame_data["frame"],
                    "timestamp": frame_data["timestamp"]
                })
            except asyncio.TimeoutError:
                # No frame available, send a keepalive message
                try:
                    await websocket.send_json({
                        "status": "alive",
                        "timestamp": time.time()
                    })
                except WebSocketDisconnect:
                    break
    except WebSocketDisconnect:
        logger.info(f"Video WebSocket disconnected for camera {camera_id}")
    except Exception as e:
        logger.error(f"Error in video WebSocket: {e}")
    finally:
        # Remove client and cleanup
        stream.remove_client(connection_id)
        logger.info(f"Video WebSocket connection closed for camera {camera_id}") 
```

## WebSocket Implementation
File: `app/routes/websockets.py`
```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, status
from typing import Dict, List, Optional, Any
import json
import asyncio
import cv2
import base64
from datetime import datetime
from jose import JWTError, jwt
from pydantic import BaseModel
import time
import statistics  # Add statistics module for calculating averages

from app.config import SECRET_KEY, ALGORITHM
from app.services.detection_service import detect_person_crossing
from app.database.cameras import get_camera_by_id
from app.routes.camera import _resize_frame, _fetch_camera_source_by_id
from app.database.calibration import fetch_calibration_for_camera

router = APIRouter()

# Store active connections
active_connections: Dict[int, List[WebSocket]] = {}

# Model for WebSocket responses
class DetectionWSResponse(BaseModel):
    camera_id: int
    timestamp: str
    frame: str  # Base64 encoded image frame
    detections: List[Dict[str, Any]]
    event: Optional[str] = None
    status: str = "no_motion"
    crossing_detected: bool = False
    actual_fps: Optional[float] = None
    target_fps: Optional[float] = None
    hardware_limited: Optional[bool] = None

# New response model for detection-only data
class DetectionOnlyResponse(BaseModel):
    camera_id: int
    timestamp: str
    detections: List[Dict[str, Any]]
    event: Optional[str] = None
    status: str = "no_motion"
    crossing_detected: bool = False

# Verify token similar to get_current_user but for WebSockets
async def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        is_admin: bool = payload.get("admin", False)
        
        if username is None:
            return None
            
        return {"username": username, "is_admin": is_admin}
    except JWTError:
        return None

@router.websocket("/ws/live-detections/{camera_id}")
async def live_detections(
    websocket: WebSocket, 
    camera_id: int, 
    token: Optional[str] = Query(None),
    frame_rate: Optional[int] = Query(None)  # Add explicit frame_rate parameter
):
    """
    WebSocket endpoint for real-time video streaming with detection results
    Requires a valid JWT token as a query parameter
    """
    # Verify the token
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing authentication token")
        return
        
    user = await verify_token(token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid authentication token")
        return
    
    # Verify the camera exists
    camera = get_camera_by_id(camera_id)
    if not camera:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=f"Camera with ID {camera_id} not found")
        return
    
    # Accept the connection
    await websocket.accept()
    
    # Add to active connections
    if camera_id not in active_connections:
        active_connections[camera_id] = []
    active_connections[camera_id].append(websocket)
    
    # Get camera source
    source_path = _fetch_camera_source_by_id(camera_id)
    if not source_path:
        await websocket.send_json({
            "status": "error",
            "message": f"Camera source not found for camera_id={camera_id}"
        })
        if camera_id in active_connections and websocket in active_connections[camera_id]:
            active_connections[camera_id].remove(websocket)
        return

    # Open video capture once at the beginning
    cap = cv2.VideoCapture(source_path)
    if not cap.isOpened():
        await websocket.send_json({
            "status": "error",
            "message": f"Failed to open camera/video source '{source_path}'"
        })
        if camera_id in active_connections and websocket in active_connections[camera_id]:
            active_connections[camera_id].remove(websocket)
        return
    
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "status": "connected",
            "message": f"Connected to live video stream for camera {camera_id}"
        })
        
        # Get calibration data to determine frame rate
        calib_data = fetch_calibration_for_camera(camera_id)
        
        # Detection state
        detection_result = None
        last_detection_time = 0
        
        # Use frame_rate parameter from query if provided, otherwise from calibration
        if frame_rate is not None:
            # URL parameter takes precedence
            configured_frame_rate = frame_rate
        elif calib_data and "frame_rate" in calib_data:
            configured_frame_rate = calib_data.get("frame_rate", 5)  # Default to 5 FPS
        else:
            configured_frame_rate = 5  # Default if no other source available
            
        # Ensure frame_rate is valid
        if configured_frame_rate <= 0:
            configured_frame_rate = 5  # Fallback to 5 FPS
            
        # Convert frame_rate to detection interval (seconds between detections)
        detection_interval = 1.0 / configured_frame_rate
        log_message = f"Using configured frame rate: {configured_frame_rate} FPS (interval: {detection_interval:.3f}s)"
        
        print(f"Camera {camera_id}: {log_message}")
        
        # Add performance tracking variables
        frame_count = 0
        start_time = time.time()
        last_frame_time = start_time
        frame_times = []
        processing_times = []
        send_times = []
        
        # Log initial connection details
        print(f"Camera {camera_id}: WebSocket connection established, target FPS: {configured_frame_rate:.1f} for detection, ~20 FPS for streaming")
        
        # Set quality based on frame rate
        if configured_frame_rate > 15:
            # Use lower quality for high frame rates
            jpeg_quality = 40
            max_height = 160
        elif configured_frame_rate > 8:
            # Medium quality for medium frame rates
            jpeg_quality = 50
            max_height = 180
        else:
            # Better quality for low frame rates
            jpeg_quality = 60
            max_height = 180
            
        # Main streaming loop
        while True:
            try:
                loop_start = time.time()
                
                # Read frame
                ret, frame = cap.read()
                
                if not ret or frame is None:
                    # If we're at the end of a video file, try to reopen it
                    cap.release()
                    cap = cv2.VideoCapture(source_path)
                    if not cap.isOpened():
                        await websocket.send_json({
                            "status": "error",
                            "message": f"Failed to reopen video source '{source_path}'"
                        })
                        break
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        await websocket.send_json({
                            "status": "error",
                            "message": "Unable to read a frame from the camera/video"
                        })
                        break
                
                # Make a copy for streaming
                display_frame = frame.copy()
                
                # Resize the frame to a smaller size for WebSocket streaming
                display_frame = _resize_frame(display_frame, max_height=max_height)
                
                # Track time for frame processing
                processing_start = time.time()
                
                # Only run detection periodically to improve performance
                current_time = time.time()
                if current_time - last_detection_time >= detection_interval:
                    # Run detection in background (non-blocking)
                    detection_task = asyncio.create_task(asyncio.to_thread(detect_person_crossing, camera_id))
                    try:
                        # Wait with a timeout to avoid blocking the stream
                        detection_result = await asyncio.wait_for(detection_task, timeout=0.2)
                        last_detection_time = current_time
                    except asyncio.TimeoutError:
                        # Detection is taking too long, continue with the stream
                        pass
                
                # Encode frame to JPEG and then base64 with quality based on frame rate
                encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]
                success, encoded_img = cv2.imencode(".jpg", display_frame, encode_params)
                if not success:
                    await websocket.send_json({
                        "status": "error",
                        "message": "Failed to encode frame to JPEG"
                    })
                    continue
                    
                frame_base64 = base64.b64encode(encoded_img.tobytes()).decode('utf-8')
                
                # Record processing time
                processing_end = time.time()
                processing_time = processing_end - processing_start
                processing_times.append(processing_time)
                
                # Format the response
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if detection_result:
                    timestamp = detection_result.get("timestamp", timestamp)
                timestamp_iso = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").isoformat()
                
                # Format detection results
                detections = []
                event = None
                status = "no_motion"
                crossing_detected = False
                
                if detection_result:
                    # Format bounding boxes
                    for bbox in detection_result.get("bounding_boxes", []):
                        detections.append({
                            "label": "person",  # Currently only detecting people
                            "confidence": 0.9,  # Placeholder, real confidence scores would be better
                            "bbox": bbox
                        })
                    
                    # Check if an event was detected
                    if "status" in detection_result:
                        status = detection_result["status"]
                        if status == "entry_detected":
                            event = "entry"
                        elif status == "exit_detected":
                            event = "exit"
                        
                    crossing_detected = detection_result.get("crossing_detected", False)
                
                # Calculate current actual FPS
                current_time = time.time()
                elapsed = current_time - start_time
                actual_fps = frame_count / elapsed if elapsed > 0 else 0
                
                # Determine if hardware is limiting the frame rate
                hardware_limited = (configured_frame_rate > 6.0 and actual_fps < configured_frame_rate * 0.7)
                
                # Create response
                response = DetectionWSResponse(
                    camera_id=camera_id,
                    timestamp=timestamp_iso,
                    frame=frame_base64,
                    detections=detections,
                    event=event,
                    status=status,
                    crossing_detected=crossing_detected,
                    actual_fps=round(actual_fps, 1),
                    target_fps=configured_frame_rate,
                    hardware_limited=hardware_limited
                )
                
                # Track send time
                send_start = time.time()
                
                # Send update to client
                await websocket.send_json(response.dict())
                
                # Record send completion time
                send_end = time.time()
                send_time = send_end - send_start
                send_times.append(send_time)
                
                # Increment frame counter and calculate FPS
                frame_count += 1
                current_time = time.time()
                time_since_last_frame = current_time - last_frame_time
                frame_times.append(time_since_last_frame)
                last_frame_time = current_time
                
                # Log performance metrics every 30 frames
                if frame_count % 30 == 0:
                    elapsed = current_time - start_time
                    actual_fps = frame_count / elapsed
                    
                    # Calculate average times
                    avg_frame_time = sum(frame_times) / len(frame_times) if frame_times else 0
                    avg_processing = sum(processing_times) / len(processing_times) if processing_times else 0
                    avg_send = sum(send_times) / len(send_times) if send_times else 0
                    
                    # Calculate standard deviation to show consistency
                    frame_time_std = statistics.stdev(frame_times) if len(frame_times) > 1 else 0
                    
                    print(f"Camera {camera_id} WebSocket metrics:")
                    print(f"  - Frames sent: {frame_count}, Average FPS: {actual_fps:.2f} (target: {configured_frame_rate})")
                    print(f"  - Average frame interval: {avg_frame_time:.4f}s (±{frame_time_std:.4f}s)")
                    print(f"  - Processing time: {avg_processing:.4f}s, Send time: {avg_send:.4f}s")
                    print(f"  - Frame size: {len(frame_base64) / 1024:.1f} KB, Quality: {jpeg_quality}%")
                    print(f"  - Hardware limited: {hardware_limited}")
                    
                    # Reset for next window
                    if len(frame_times) > 100:  # Limit the array size
                        frame_times = frame_times[-100:]
                        processing_times = processing_times[-100:]
                        send_times = send_times[-100:]
                
                # Adaptive sleep to maintain consistent frame rate
                elapsed = time.time() - loop_start
                
                # Try to achieve at least 10 FPS for reasonable smoothness, regardless of target
                # But don't exceed target frame rate
                min_fps = min(10.0, configured_frame_rate)
                max_wait = 1.0 / min_fps
                target_wait = 1.0 / configured_frame_rate if configured_frame_rate > 0 else 0.1
                
                sleep_time = max(0, min(max_wait, target_wait - elapsed))
                await asyncio.sleep(sleep_time)
                
            except WebSocketDisconnect:
                print(f"WebSocket disconnected for camera {camera_id}")
                break
            except Exception as e:
                print(f"Error in streaming: {str(e)}")
                await asyncio.sleep(1.0)  # Wait before retrying
    
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for camera {camera_id}")
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
    finally:
        # Log final statistics
        end_time = time.time()
        total_duration = end_time - start_time
        if frame_count > 0:
            final_fps = frame_count / total_duration
            print(f"Camera {camera_id} WebSocket connection closed:")
            print(f"  - Total frames: {frame_count}, Duration: {total_duration:.2f}s")
            print(f"  - Average FPS: {final_fps:.2f}")
        
        # Always release the camera when done
        if cap and cap.isOpened():
            cap.release()
        # Remove from active connections
        if camera_id in active_connections and websocket in active_connections[camera_id]:
            active_connections[camera_id].remove(websocket)
            if not active_connections[camera_id]:
                del active_connections[camera_id]

# The implementation for multiple cameras would need similar modifications
@router.websocket("/ws/detections")
async def multiple_detections(
    websocket: WebSocket, 
    camera_ids: str = Query(...),  # Comma-separated list of camera IDs
    token: Optional[str] = Query(None),
    frame_rate: Optional[int] = Query(None)  # Add explicit frame_rate parameter
):
    """
    WebSocket endpoint for real-time video streaming from multiple cameras
    Requires a valid JWT token as a query parameter
    """
    # Verify the token
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing authentication token")
        return
        
    user = await verify_token(token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid authentication token")
        return
    
    # Parse camera IDs
    try:
        camera_id_list = [int(cid.strip()) for cid in camera_ids.split(",") if cid.strip()]
    except ValueError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid camera IDs format")
        return
    
    if not camera_id_list:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="No camera IDs provided")
        return
    
    # Verify all cameras exist and prepare camera sources
    camera_sources = {}
    camera_captures = {}
    for cam_id in camera_id_list:
        camera = get_camera_by_id(cam_id)
        if not camera:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=f"Camera with ID {cam_id} not found")
            return
        
        # Get camera source path
        source_path = _fetch_camera_source_by_id(cam_id)
        if not source_path:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=f"Camera source not found for camera_id={cam_id}")
            return
        
        camera_sources[cam_id] = source_path
        
        # Open video capture
        cap = cv2.VideoCapture(source_path)
        if not cap.isOpened():
            # Close any already opened captures
            for opened_cap in camera_captures.values():
                opened_cap.release()
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=f"Failed to open camera/video source '{source_path}'")
            return
        
        camera_captures[cam_id] = cap
    
    # Accept the connection
    await websocket.accept()
    
    # Send initial confirmation
    await websocket.send_json({
        "status": "connected",
        "message": f"Connected to view {len(camera_id_list)} cameras",
        "camera_ids": camera_id_list
    })
    
    # Track camera data and state
    camera_data = {}
    
    # Performance tracking for multiple cameras
    start_time = time.time()
    total_frames = 0
    frames_per_camera = {cam_id: 0 for cam_id in camera_id_list}
    last_metrics_time = start_time
    
    # Initialize camera data with detection intervals from calibration
    for camera_id in camera_id_list:
        # Get calibration data to determine frame rate
        calib_data = fetch_calibration_for_camera(camera_id)
        
        # Calculate detection interval from frame_rate in calibration
        if calib_data and "frame_rate" in calib_data:
            frame_rate = calib_data.get("frame_rate", 5)  # Default to 5 FPS
            # Ensure frame_rate is valid
            if frame_rate <= 0:
                frame_rate = 5  # Fallback to 5 FPS
            # Convert frame_rate to detection interval (seconds between detections)
            detection_interval = 1.0 / frame_rate
            log_message = f"Using configured frame rate from calibration: {frame_rate} FPS (interval: {detection_interval:.3f}s)"
        else:
            # Default values if no calibration data
            frame_rate = 5
            detection_interval = 0.2  # Default 5 FPS
            log_message = f"No frame rate in calibration, using default: {frame_rate} FPS (interval: {detection_interval:.3f}s)"
        
        print(f"Camera {camera_id}: {log_message}")
        
        camera_data[camera_id] = {
            "source_path": _fetch_camera_source_by_id(camera_id),
            "detection_result": None,
            "last_detection_time": 0,
            "detection_interval": detection_interval,
            "last_frame_time": time.time(),
            "processing_times": [],
            "send_times": []
        }
    
    # Main processing loop
    try:
        while True:
            try:
                # Process a single camera at a time in a round-robin fashion
                current_index = 0
                for camera_id in camera_id_list:
                    # Skip cameras with invalid source paths
                    if not camera_data[camera_id]["source_path"]:
                        continue
                        
                    # Get camera source
                    source_path = camera_data[camera_id]["source_path"]
                    
                    # Open video capture
                    cap = cv2.VideoCapture(source_path)
                    if not cap.isOpened():
                        await websocket.send_json({
                            "status": "error",
                            "message": f"Failed to open camera/video source '{source_path}'"
                        })
                        continue
                    
                    loop_start = time.time()
                    
                    # Read frame
                    ret, frame = cap.read()
                    
                    if not ret or frame is None:
                        cap.release()
                        await websocket.send_json({
                            "status": "error",
                            "message": f"Unable to read a frame from camera {camera_id}"
                        })
                        continue
                    
                    # Resize the frame to a smaller size for WebSocket streaming
                    frame = _resize_frame(frame, max_height=180)
                    
                    processing_start = time.time()
                    
                    # Only run detection based on the camera's frame rate/interval
                    current_time = time.time()
                    camera_data_obj = camera_data[camera_id]
                    last_detection_time = camera_data_obj["last_detection_time"]
                    detection_interval = camera_data_obj["detection_interval"]
                    
                    if current_time - last_detection_time >= detection_interval:
                        # Run detection in background (non-blocking)
                        detection_task = asyncio.create_task(asyncio.to_thread(detect_person_crossing, camera_id))
                        try:
                            # Wait with a timeout to avoid blocking the stream
                            detection_result = await asyncio.wait_for(detection_task, timeout=0.2)
                            camera_data_obj["detection_result"] = detection_result
                            camera_data_obj["last_detection_time"] = current_time
                        except asyncio.TimeoutError:
                            # Detection is taking too long, continue with the stream
                            pass
                    else:
                        # Use the cached result
                        detection_result = camera_data_obj["detection_result"]
                    
                    # Record processing time
                    processing_time = time.time() - processing_start
                    camera_data_obj["processing_times"].append(processing_time)
                    
                    # Encode frame to JPEG and then base64
                    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 60]  # 60% quality
                    success, encoded_img = cv2.imencode(".jpg", frame, encode_params)
                    if not success:
                        cap.release()
                        continue
                        
                    frame_base64 = base64.b64encode(encoded_img.tobytes()).decode('utf-8')
                    
                    # Format the response
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if detection_result:
                        timestamp = detection_result.get("timestamp", timestamp)
                    timestamp_iso = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").isoformat()
                    
                    # Format detection results
                    detections = []
                    event = None
                    status = "no_motion"
                    crossing_detected = False
                    
                    if detection_result:
                        # Format bounding boxes
                        for bbox in detection_result.get("bounding_boxes", []):
                            detections.append({
                                "label": "person",  # Currently only detecting people
                                "confidence": 0.9,  # Placeholder, real confidence scores would be better
                                "bbox": bbox
                            })
                        
                        # Check if an event was detected
                        if "status" in detection_result:
                            status = detection_result["status"]
                            if status == "entry_detected":
                                event = "entry"
                            elif status == "exit_detected":
                                event = "exit"
                            
                        crossing_detected = detection_result.get("crossing_detected", False)
                    
                    # Create response
                    response = DetectionWSResponse(
                        camera_id=camera_id,
                        timestamp=timestamp_iso,
                        frame=frame_base64,
                        detections=detections,
                        event=event,
                        status=status,
                        crossing_detected=crossing_detected
                    )
                    
                    # Track send time
                    send_start = time.time()
                    
                    # Send update to client
                    await websocket.send_json(response.dict())
                    
                    # Track send completion
                    send_time = time.time() - send_start
                    camera_data_obj["send_times"].append(send_time)
                    
                    # Track frame time
                    current_time = time.time()
                    frame_interval = current_time - camera_data_obj["last_frame_time"]
                    camera_data_obj["last_frame_time"] = current_time
                    
                    # Update frame counters
                    total_frames += 1
                    frames_per_camera[camera_id] += 1
                    
                    # Close the capture
                    cap.release()
                    
                    # Log performance metrics periodically
                    if current_time - last_metrics_time >= 10.0:  # Every 10 seconds
                        elapsed = current_time - start_time
                        overall_fps = total_frames / elapsed
                        
                        print(f"Multiple camera WebSocket metrics after {elapsed:.1f}s:")
                        print(f"  - Total frames: {total_frames}, Overall FPS: {overall_fps:.2f}")
                        
                        for cam_id in camera_id_list:
                            cam_frames = frames_per_camera[cam_id]
                            cam_fps = cam_frames / elapsed if elapsed > 0 else 0
                            cam_data = camera_data[cam_id]
                            
                            # Calculate averages if we have data
                            avg_proc = sum(cam_data["processing_times"]) / len(cam_data["processing_times"]) if cam_data["processing_times"] else 0
                            avg_send = sum(cam_data["send_times"]) / len(cam_data["send_times"]) if cam_data["send_times"] else 0
                            
                            print(f"  - Camera {cam_id}: {cam_frames} frames, {cam_fps:.2f} FPS")
                            print(f"    Processing: {avg_proc:.4f}s, Send: {avg_send:.4f}s")
                            
                            # Limit array sizes
                            if len(cam_data["processing_times"]) > 100:
                                cam_data["processing_times"] = cam_data["processing_times"][-100:]
                            if len(cam_data["send_times"]) > 100:
                                cam_data["send_times"] = cam_data["send_times"][-100:]
                        
                        last_metrics_time = current_time
                
                # Add a small delay between iterations
                await asyncio.sleep(0.05)
                
            except WebSocketDisconnect:
                print(f"WebSocket disconnected for multiple cameras")
                break
            except Exception as e:
                print(f"Error in multiple camera streaming: {str(e)}")
                # Move to next camera if there's an error with the current one
                current_index = (current_index + 1) % len(camera_id_list)
                await asyncio.sleep(1.0)  # Wait before retrying
            
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for multiple cameras")
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
    finally:
        # Log final statistics
        end_time = time.time()
        total_duration = end_time - start_time
        
        if total_frames > 0:
            overall_fps = total_frames / total_duration
            print(f"Multiple camera WebSocket connection closed:")
            print(f"  - Total duration: {total_duration:.2f}s")
            print(f"  - Total frames: {total_frames}, Overall FPS: {overall_fps:.2f}")
            
            for cam_id in camera_id_list:
                cam_frames = frames_per_camera[cam_id]
                cam_fps = cam_frames / total_duration if total_duration > 0 else 0
                print(f"  - Camera {cam_id}: {cam_frames} frames, {cam_fps:.2f} FPS")
        
        # Release all camera captures
        for cam_id, cap in camera_captures.items():
            if cap and cap.isOpened():
                cap.release()
                
        # Remove from active connections for all cameras
        for cam_id in camera_id_list:
            if cam_id in active_connections and websocket in active_connections[cam_id]:
                active_connections[cam_id].remove(websocket)
                if not active_connections[cam_id]:
                    del active_connections[cam_id] 

# Add a new WebSocket endpoint for detection data only (for use with WebRTC video)
@router.websocket("/ws/detection-data/{camera_id}")
async def detection_data_only(
    websocket: WebSocket, 
    camera_id: int, 
    token: Optional[str] = Query(None),
    frame_rate: Optional[int] = Query(None)
):
    """
    WebSocket endpoint for detection data only, without video frames.
    To be used in conjunction with WebRTC video streaming.
    Requires a valid JWT token as a query parameter.
    """
    # Verify the token
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing authentication token")
        return
        
    user = await verify_token(token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid authentication token")
        return
    
    # Verify the camera exists
    camera = get_camera_by_id(camera_id)
    if not camera:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=f"Camera with ID {camera_id} not found")
        return
    
    # Accept the connection
    await websocket.accept()
    
    # Get camera source
    source_path = _fetch_camera_source_by_id(camera_id)
    if not source_path:
        await websocket.send_json({
            "status": "error",
            "message": f"Camera source not found for camera_id={camera_id}"
        })
        return
    
    # Get calibration data to determine frame rate
    calib_data = fetch_calibration_for_camera(camera_id)
    
    # Detection state
    detection_result = None
    last_detection_time = 0
    
    # Use frame_rate parameter from query if provided, otherwise from calibration
    if frame_rate is not None:
        # URL parameter takes precedence
        configured_frame_rate = frame_rate
    elif calib_data and "frame_rate" in calib_data:
        configured_frame_rate = calib_data.get("frame_rate", 5)
    else:
        configured_frame_rate = 5  # Default if no other source available
        
    # Ensure frame_rate is valid
    if configured_frame_rate <= 0:
        configured_frame_rate = 5
        
    # Convert frame_rate to detection interval (seconds between detections)
    detection_interval = 1.0 / configured_frame_rate
    log_message = f"Using configured frame rate: {configured_frame_rate} FPS (interval: {detection_interval:.3f}s)"
    
    print(f"Camera {camera_id}: {log_message} (detection data only)")
    
    # Add performance tracking variables
    detection_count = 0
    start_time = time.time()
    
    # Send initial connection confirmation
    await websocket.send_json({
        "status": "connected",
        "message": f"Connected to detection data stream for camera {camera_id}",
        "detection_interval": detection_interval
    })
    
    try:
        # Main detection loop
        while True:
            try:
                loop_start = time.time()
                
                # Only run detection periodically based on the frame rate
                current_time = time.time()
                if current_time - last_detection_time >= detection_interval:
                    # Run detection in background (non-blocking)
                    detection_task = asyncio.create_task(asyncio.to_thread(detect_person_crossing, camera_id))
                    try:
                        # Wait with a timeout to avoid blocking
                        detection_result = await asyncio.wait_for(detection_task, timeout=0.5)
                        last_detection_time = current_time
                    except asyncio.TimeoutError:
                        # Detection is taking too long, continue
                        print(f"Camera {camera_id}: Detection timeout, skipping...")
                        await asyncio.sleep(0.1)
                        continue
                    
                    # Format detection results
                    if detection_result:
                        # Format the response
                        timestamp = detection_result.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                        timestamp_iso = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").isoformat()
                        
                        # Format bounding boxes and other detection data
                        detections = []
                        event = None
                        status = "no_motion"
                        crossing_detected = False
                        
                        # Format bounding boxes
                        for bbox in detection_result.get("bounding_boxes", []):
                            detections.append({
                                "label": "person",  # Currently only detecting people
                                "confidence": 0.9,  # Placeholder
                                "bbox": bbox
                            })
                        
                        # Check if an event was detected
                        if "status" in detection_result:
                            status = detection_result["status"]
                            if status == "entry_detected":
                                event = "entry"
                            elif status == "exit_detected":
                                event = "exit"
                            
                        crossing_detected = detection_result.get("crossing_detected", False)
                        
                        # Create detection-only response
                        response = DetectionOnlyResponse(
                            camera_id=camera_id,
                            timestamp=timestamp_iso,
                            detections=detections,
                            event=event,
                            status=status,
                            crossing_detected=crossing_detected
                        )
                        
                        # Send update to client
                        await websocket.send_json(response.dict())
                        
                        # Track statistics
                        detection_count += 1
                        
                        # Log detection info periodically
                        if detection_count % 10 == 0:
                            elapsed = time.time() - start_time
                            detection_rate = detection_count / elapsed
                            print(f"Camera {camera_id}: Sent {detection_count} detection updates, rate: {detection_rate:.2f}/s")
                
                # Add a small delay to avoid busy-waiting
                elapsed = time.time() - loop_start
                sleep_time = max(0, detection_interval - elapsed)
                await asyncio.sleep(sleep_time)
                
            except WebSocketDisconnect:
                print(f"WebSocket disconnected for camera {camera_id} (detection data)")
                break
            except Exception as e:
                print(f"Error in detection data stream: {str(e)}")
                await asyncio.sleep(1.0)  # Wait before retrying
    
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for camera {camera_id} (detection data)")
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
    finally:
        # Log final statistics
        end_time = time.time()
        total_duration = end_time - start_time
        if detection_count > 0:
            avg_rate = detection_count / total_duration
            print(f"Camera {camera_id} detection WebSocket closed:")
            print(f"  - Total detections: {detection_count}, Duration: {total_duration:.2f}s")
            print(f"  - Average rate: {avg_rate:.2f} detections/s")

# Similar endpoint for multiple cameras could be added here 
```

## Detection Pipeline
File: `app/inference/pipeline.py`
```python
# app/inference/pipeline.py

import cv2
import time
import os
import psutil
from typing import Optional, List, Tuple, Dict, Union
from app.database.calibration import fetch_calibration_for_camera
from app.inference.detection import run_yolo_inference
from app.inference.crossing import compute_side_of_line, check_line_crossings

def process_camera_stream(
    camera_id: int,
    source_path: str,
    skip_frame: int = 1
) -> Optional[Dict[str, Union[str, List]]]:
    """
    Processes the camera stream to detect people and determine if a person enters or exits.
    
    Args:
        camera_id: ID of the camera.
        source_path: Path to the video source (file path or RTSP URL).
        skip_frame: Determines how often frames are processed (default: every frame).
            Note: This parameter is deprecated and will be overridden by calibration's frame_rate.
    
    Returns:
        Dictionary with:
        - "event_type": "entry" if a person enters, "exit" if a person exits, None if no detection.
        - "bounding_boxes": List of bounding boxes as [x1, y1, x2, y2]
    """
    
    # Fetch calibration data
    calib = fetch_calibration_for_camera(camera_id)
    if not calib:
        # Silently return None instead of printing error
        return None

    # Removed debug print about loaded calibration
    line_data = calib["line"]
    square_data = calib["square"]
    orientation = calib.get("orientation", "leftToRight")  # Default to leftToRight if orientation not specified
    frame_rate = calib.get("frame_rate", 5)  # Default to 5 FPS if not specified

    x1, y1, x2, y2 = (
        line_data["line_start_x"],
        line_data["line_start_y"],
        line_data["line_end_x"],
        line_data["line_end_y"],
    )

    crop_x1, crop_y1, crop_x2, crop_y2 = (
        int(square_data["crop_x1"]),
        int(square_data["crop_y1"]),
        int(square_data["crop_x2"]),
        int(square_data["crop_y2"]),
    )

    # Try a more efficient approach - grab a single frame for detection
    cap = cv2.VideoCapture(source_path)
    if not cap.isOpened():
        return None
    
    ret, frame = cap.read()
    if not ret or frame is None:
        cap.release()
        return None
    
    # Process just one frame - crop to detection area
    frame = frame[crop_y1:crop_y2, crop_x1:crop_x2]
    
    # For detection, we can resize to a smaller frame to speed up processing
    detection_frame = cv2.resize(frame, (0, 0), fx=0.7, fy=0.7)
    
    # Run detection on the resized frame
    boxes, scores, labels = run_yolo_inference(detection_frame)
    
    # If no detections, return early
    if len(boxes) == 0:
        cap.release()
        return None
    
    # Adjust bounding boxes back to original frame size
    all_boxes = []
    for i, box in enumerate(boxes):
        if scores[i] > 0.5:  # Only keep boxes with confidence > 50%
            x_min, y_min, x_max, y_max = box
            # Scale back to original size
            x_min *= 2
            y_min *= 2
            x_max *= 2
            y_max *= 2
            all_boxes.append([int(x_min), int(y_min), int(x_max), int(y_max)])
    
    # We only need the center points. For each box, compute center (cx, cy).
    this_frame_centers = []
    for box in all_boxes:
        x_min, y_min, x_max, y_max = box
        cx = (x_min + x_max) / 2.0
        cy = (y_min + y_max) / 2.0
        this_frame_centers.append((cx, cy))
    
    # Calculate which side of the line each center is on
    center_sides = []
    for cx, cy in this_frame_centers:
        side = compute_side_of_line(cx, cy, x1, y1, x2, y2)
        center_sides.append(side)
    
    # Check if we have detections on both sides of the line
    if len(center_sides) >= 2 and len(set(center_sides)) > 1:
        # We have points on both sides, let's grab a few more frames to confirm movement
        old_centers = []
        for cx, cy in this_frame_centers:
            side = compute_side_of_line(cx, cy, x1, y1, x2, y2)
            old_centers.append((cx, cy, side))
        
        # Check a few more frames for crossing detection
        entry_count = 0
        exit_count = 0
        frame_check_count = 0
        max_check_frames = 5  # Only check a few more frames
        
        while frame_check_count < max_check_frames:
            ret, frame = cap.read()
            if not ret or frame is None:
                break
                
            frame = frame[crop_y1:crop_y2, crop_x1:crop_x2]
            detection_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            
            boxes, scores, labels = run_yolo_inference(detection_frame)
            
            this_frame_centers = []
            for i, box in enumerate(boxes):
                if scores[i] > 0.5:
                    x_min, y_min, x_max, y_max = box
                    # Scale back
                    x_min *= 2
                    y_min *= 2 
                    x_max *= 2
                    y_max *= 2
                    
                    cx = (x_min + x_max) / 2.0
                    cy = (y_min + y_max) / 2.0
                    this_frame_centers.append((cx, cy))
                    all_boxes.append([int(x_min), int(y_min), int(x_max), int(y_max)])
            
            # Check for line crossings
            entry_count, exit_count = check_line_crossings(
                this_frame_centers, old_centers, line_data, entry_count, exit_count, camera_id, orientation
            )
            
            # Update old_centers
            new_old_centers = []
            for cx, cy in this_frame_centers:
                side = compute_side_of_line(cx, cy, x1, y1, x2, y2)
                new_old_centers.append((cx, cy, side))
            old_centers = new_old_centers
            
            frame_check_count += 1
            
            # If we detected a crossing, we can exit early
            if entry_count > 0 or exit_count > 0:
                break
        
        cap.release()
        
        # Return a dictionary with event type and bounding boxes
        if entry_count > 0:
            return {
                "event_type": "entry",
                "bounding_boxes": all_boxes
            }
        elif exit_count > 0:
            return {
                "event_type": "exit",
                "bounding_boxes": all_boxes
            }
    
    cap.release()
    return None

```

File: `app/inference/detection.py`
```python
import cv2
import numpy as np
from ultralytics import YOLO

# Initialize YOLO model with verbose=False to disable debug prints
_yolo_model = YOLO("./checkpoints/yolov8n.pt")

def run_yolo_inference(frame):
    """
    Accepts a BGR image (NumPy array), returns (boxes, scores, labels).
    boxes -> [ [x1, y1, x2, y2], ... ]
    scores -> [ s1, s2, ... ]
    labels -> [ l1, l2, ... ]
    """
    # Set verbose=False to disable YOLO's verbose output
    results = _yolo_model.predict(source=frame, classes=[0], verbose=False)
    yolo_result = results[0]

    xyxy = yolo_result.boxes.xyxy.cpu().numpy()  # shape: (num_det, 4)
    conf = yolo_result.boxes.conf.cpu().numpy()  # shape: (num_det,)
    cls  = yolo_result.boxes.cls.cpu().numpy()   # shape: (num_det,)

    boxes, scores, labels = [], [], []
    for i in range(len(xyxy)):
        x1, y1, x2, y2 = xyxy[i]
        boxes.append([int(x1), int(y1), int(x2), int(y2)])
        scores.append(float(conf[i]))
        labels.append(int(cls[i]))

    return boxes, scores, labels

```

File: `app/inference/crossing.py`
```python
from typing import List, Tuple, Dict
from datetime import datetime
from app.database.cameras import get_store_for_camera
from app.database.events import add_event

def compute_side_of_line(px: float, py: float,
                         x1: float, y1: float, x2: float, y2: float) -> int:
    """
    Returns +1 or -1 depending on which side of the line (x1,y1)->(x2,y2) the point (px,py) is on.
    0 if exactly on the line.
    """
    vx = x2 - x1
    vy = y2 - y1
    dx = px - x1
    dy = py - y1
    cross = vx * dy - vy * dx
    if cross > 0:
        return +1
    elif cross < 0:
        return -1
    else:
        return 0

def find_closest_center(cx: float, cy: float, old_centers: List[Tuple[float, float, int]], max_dist=50.0):
    """
    Return old center within max_dist, or None if none close enough.
    old_centers is a list of (oldCx, oldCy, oldSide).
    """
    best_center = None
    best_dist = max_dist
    for (ocx, ocy, oside) in old_centers:
        dist = ((cx - ocx)**2 + (cy - ocy)**2)**0.5
        if dist < best_dist:
            best_dist = dist
            best_center = (ocx, ocy, oside)
    return best_center

def check_line_crossings(
    this_frame_centers, old_centers, line_data, entry_count, exit_count, camera_id_int, orientation="leftToRight"
):
    """
    Compare new centers to old centers, checking if side changed across the line.
    Return updated (entry_count, exit_count).
    Additionally, log the crossing event to the DB if desired.
    
    orientation: "leftToRight" or "rightToLeft" - changes which direction is considered entry vs exit
    """

    if not old_centers:
        return entry_count, exit_count

    x1 = line_data["line_start_x"]
    y1 = line_data["line_start_y"]
    x2 = line_data["line_end_x"]
    y2 = line_data["line_end_y"]

    # Get store_id once, reuse it
    try:
        store_id = get_store_for_camera(camera_id_int)
    except ValueError as e:
        print(f"Warning: {e}, cannot log events.")
        store_id = None

    for (cx, cy) in this_frame_centers:
        old_center = find_closest_center(cx, cy, old_centers)
        if old_center is None:
            continue

        (ocx, ocy, old_side) = old_center
        if old_side is None:
            old_side = compute_side_of_line(ocx, ocy, x1, y1, x2, y2)
        new_side = compute_side_of_line(cx, cy, x1, y1, x2, y2)

        if old_side != 0 and new_side != 0 and old_side != new_side:
            # crossing occurred
            event_type = None
            
            # Default orientation (leftToRight):
            # - going from +1 to -1 means entry
            # - going from -1 to +1 means exit
            if orientation == "leftToRight":
                if old_side < 0 and new_side > 0:
                    exit_count += 1
                    event_type = "exit"
                elif old_side > 0 and new_side < 0:
                    entry_count += 1
                    event_type = "entry"
            # Reversed orientation (rightToLeft):
            # - going from +1 to -1 means exit
            # - going from -1 to +1 means entry
            elif orientation == "rightToLeft":
                if old_side < 0 and new_side > 0:
                    entry_count += 1
                    event_type = "entry"
                elif old_side > 0 and new_side < 0:
                    exit_count += 1
                    event_type = "exit"

            # If store_id was found, log the event
            if store_id and event_type:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # e.g., we might set clip_path to empty or a known file
                clip_path = "annotated_clip.mp4"
                add_event(store_id, event_type, clip_path, now_str)

    return entry_count, exit_count

```

## Camera Management
File: `app/routes/camera.py`
```python
import cv2
import os
from fastapi import APIRouter, HTTPException, Response, Depends
from pydantic import BaseModel
from typing import List, Optional

from app.database.cameras import add_camera, get_cameras_for_store, get_camera_by_id
from app.database.stores import get_store_by_id
from app.database.connection import get_connection
from app.routes.auth import get_current_user
from app.database.calibration import store_calibration, fetch_calibration_for_camera

router = APIRouter()

class CameraCreate(BaseModel):
    store_id: int
    camera_name: str
    source: str  # RTSP link or local file

class CameraResponse(BaseModel):
    camera_id: int
    store_id: int
    camera_name: str
    source: str
    status: str = "online"  # Placeholder status 

class ROI(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float

class Line(BaseModel):
    startX: float
    startY: float
    endX: float
    endY: float

class CalibrationData(BaseModel):
    roi: ROI
    line: Line
    orientation: str = "leftToRight"  # Default value if not provided
    frame_rate: int = 5  # Default value of 5 FPS if not provided

@router.post("/cameras", response_model=CameraResponse)
def create_camera(cam_data: CameraCreate, current_user: dict = Depends(get_current_user)):
    """
    Create a camera in the DB, referencing a store_id.
    """
    store = get_store_by_id(cam_data.store_id)
    if not store:
        raise HTTPException(status_code=400, detail="Invalid store_id; store not found.")

    camera_id = add_camera(cam_data.store_id, cam_data.camera_name, cam_data.source)
    
    # Return full camera object with the created camera_id
    return CameraResponse(
        camera_id=camera_id,
        store_id=cam_data.store_id,
        camera_name=cam_data.camera_name,
        source=cam_data.source
    )

@router.get("/cameras", response_model=List[CameraResponse])
def list_cameras(store_id: Optional[int] = None, current_user: dict = Depends(get_current_user)):
    """
    List cameras, optionally filtered by store_id.
    """
    if store_id is None:
        # Optionally, implement a get_all_cameras() if you want to return everything
        # For now, let's enforce store_id param:
        raise HTTPException(status_code=400, detail="You must supply store_id to list cameras for that store.")

    cameras = get_cameras_for_store(store_id)
    camera_list = []
    
    # Convert to CameraResponse objects and add status field
    for camera in cameras:
        # Add status field for frontend compatibility
        camera["status"] = "online"
        camera_list.append(CameraResponse(**camera))
            
    return camera_list

@router.get("/stores/{store_id}/cameras", response_model=List[CameraResponse])
def get_cameras_for_store_endpoint(store_id: int, current_user: dict = Depends(get_current_user)):
    """
    List all cameras for a specific store.
    """
    # First check if store exists
    store = get_store_by_id(store_id)
    if not store:
        raise HTTPException(status_code=404, detail=f"Store with ID {store_id} not found")
    
    cameras = get_cameras_for_store(store_id)
    camera_list = []
    
    # Convert to CameraResponse objects and add status field
    for camera in cameras:
        # Add status field for frontend compatibility
        camera["status"] = "online"
        camera_list.append(CameraResponse(**camera))
            
    return camera_list

@router.get("/cameras/{camera_id}", response_model=CameraResponse)
def get_camera_by_id_endpoint(camera_id: int, current_user: dict = Depends(get_current_user)):
    """
    Get a specific camera by ID.
    """
    camera = get_camera_by_id(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera with ID {camera_id} not found")
    
    # Add status field for frontend compatibility
    camera["status"] = "online"
    return CameraResponse(**camera)

def _resize_frame(frame, max_height=500):
    """
    Resize a frame to exactly the specified height while maintaining aspect ratio.
    
    Args:
        frame: The input frame (numpy array)
        max_height: Target height in pixels (default: 500)
        
    Returns:
        Resized frame
    """
    height, width = frame.shape[:2]
    
    # Always resize to the target height, whether upscaling or downscaling
    aspect_ratio = width / height
    new_height = max_height
    new_width = int(new_height * aspect_ratio)
    return cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)

@router.get("/camera/{camera_id}/snapshot")
def get_camera_snapshot(camera_id: int, current_user: dict = Depends(get_current_user)):
    """
    Returns a single frame (image) from the chosen camera/video source.
    This can be used by the front-end to display a reference snapshot for calibration.
    """
    source_path = _fetch_camera_source_by_id(camera_id)
    if not source_path:
        raise HTTPException(
            status_code=404,
            detail=f"No camera found for camera_id={camera_id} in DB"
        )

    cap = cv2.VideoCapture(source_path)
    if not cap.isOpened():
        raise HTTPException(
            status_code=500,
            detail=f"Failed to open camera/video source '{source_path}'"
        )

    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        raise HTTPException(
            status_code=500,
            detail="Unable to read a frame from the camera/video."
        )

    # Resize the frame before encoding
    frame = _resize_frame(frame)

    success, encoded_img = cv2.imencode(".jpg", frame)
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to encode frame to JPEG."
        )

    return Response(content=encoded_img.tobytes(), media_type="image/jpeg")

@router.get("/cameras/{camera_id}/snapshot")
def get_camera_snapshot_plural(camera_id: int, current_user: dict = Depends(get_current_user)):
    """
    Alias endpoint that matches the plural 'cameras' pattern used in other endpoints.
    Returns a single frame (image) from the chosen camera/video source.
    """
    return get_camera_snapshot(camera_id, current_user)

@router.get("/camera/feed")
def get_camera_feed(camera_id: int, current_user: dict = Depends(get_current_user)):
    """
    Returns a live feed from the camera as a JPEG stream.
    This matches the API documentation.
    """
    source_path = _fetch_camera_source_by_id(camera_id)
    if not source_path:
        raise HTTPException(
            status_code=404,
            detail=f"No camera found for camera_id={camera_id} in DB"
        )

    cap = cv2.VideoCapture(source_path)
    if not cap.isOpened():
        raise HTTPException(
            status_code=500,
            detail=f"Failed to open camera/video source '{source_path}'"
        )

    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        raise HTTPException(
            status_code=500,
            detail="Unable to read a frame from the camera/video."
        )

    # Resize the frame before encoding
    frame = _resize_frame(frame)

    success, encoded_img = cv2.imencode(".jpg", frame)
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to encode frame to JPEG."
        )

    return Response(content=encoded_img.tobytes(), media_type="image/jpeg")

@router.get("/camera/{camera_id}/feed")
def get_camera_feed(camera_id: int, current_user: dict = Depends(get_current_user)):
    """
    Returns a live feed from the camera as a JPEG stream.
    This matches the API documentation.
    """
    source_path = _fetch_camera_source_by_id(camera_id)
    if not source_path:
        raise HTTPException(
            status_code=404,
            detail=f"No camera found for camera_id={camera_id} in DB"
        )

    cap = cv2.VideoCapture(source_path)
    if not cap.isOpened():
        raise HTTPException(
            status_code=500,
            detail=f"Failed to open camera/video source '{source_path}'"
        )

    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        raise HTTPException(
            status_code=500,
            detail="Unable to read a frame from the camera/video."
        )

    # Resize the frame before encoding
    frame = _resize_frame(frame)

    success, encoded_img = cv2.imencode(".jpg", frame)
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to encode frame to JPEG."
        )

    return Response(content=encoded_img.tobytes(), media_type="image/jpeg")

@router.delete("/cameras/{camera_id}")
def delete_camera(camera_id: int, current_user: dict = Depends(get_current_user)):
    """
    Delete a camera by ID.
    """
    # First check if camera exists
    camera = get_camera_by_id(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera with ID {camera_id} not found")
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM cameras WHERE camera_id = ?', (camera_id,))
    conn.commit()
    conn.close()
    
    return {"message": f"Camera {camera_id} deleted successfully"}

def _fetch_camera_source_by_id(camera_id: int) -> Optional[str]:
    """
    Helper function to fetch the 'source' field from the cameras table.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT source FROM cameras WHERE camera_id=?', (camera_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0]
    return None

@router.post("/cameras/{camera_id}/calibrate")
def set_camera_calibration(
    camera_id: int, 
    calibration_data: CalibrationData, 
    current_user: dict = Depends(get_current_user)
):
    """
    Set calibration data (ROI and line) for a specific camera.
    
    Example request:
    ```
    POST /api/cameras/1/calibrate
    {
      "roi": { "x1": 100, "y1": 100, "x2": 500, "y2": 400 },
      "line": {
        "startX": 200,
        "startY": 300,
        "endX": 400,
        "endY": 300
      },
      "orientation": "leftToRight",  // or "rightToLeft"
      "frame_rate": 5  // frames per second for detection
    }
    ```
    """
    # First check if camera exists
    camera = get_camera_by_id(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera with ID {camera_id} not found")
    
    # Extract values from the request body
    roi = calibration_data.roi
    line = calibration_data.line
    orientation = calibration_data.orientation
    frame_rate = calibration_data.frame_rate
    
    # Validate orientation
    if orientation not in ["leftToRight", "rightToLeft"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid orientation value: {orientation}. Valid values are 'leftToRight' or 'rightToLeft'"
        )
    
    # Validate frame_rate
    if frame_rate <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid frame_rate value: {frame_rate}. Value must be greater than 0."
        )
    
    # Store calibration in database
    store_calibration(
        camera_id, 
        line.startX, line.startY, line.endX, line.endY,
        roi.x1, roi.y1, roi.x2, roi.y2,
        orientation,
        frame_rate
    )
    
    return {
        "message": "Calibration data saved successfully",
        "camera_id": camera_id,
        "roi": {
            "x1": roi.x1,
            "y1": roi.y1,
            "x2": roi.x2,
            "y2": roi.y2
        },
        "line": {
            "startX": line.startX,
            "startY": line.startY,
            "endX": line.endX,
            "endY": line.endY
        },
        "orientation": orientation,
        "frame_rate": frame_rate
    }

@router.get("/cameras/{camera_id}/calibrate")
def get_camera_calibration(
    camera_id: int, 
    current_user: dict = Depends(get_current_user)
):
    """
    Get calibration data (ROI and line) for a specific camera.
    If no calibration exists, return null values.
    
    Example response:
    ```
    {
      "camera_id": 1,
      "roi": { "x1": 100, "y1": 100, "x2": 500, "y2": 400 },
      "line": {
        "startX": 200,
        "startY": 300,
        "endX": 400,
        "endY": 300
      },
      "orientation": "leftToRight",
      "frame_rate": 5
    }
    ```
    
    Or if no calibration exists:
    ```
    {
      "camera_id": 1,
      "roi": null,
      "line": null,
      "orientation": null,
      "frame_rate": null
    }
    ```
    """
    # First check if camera exists
    camera = get_camera_by_id(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera with ID {camera_id} not found")
    
    # Get calibration from database
    calibration_data = fetch_calibration_for_camera(camera_id)
    
    if not calibration_data:
        # Return empty/null calibration if none exists
        return {
            "camera_id": camera_id,
            "roi": None,
            "line": None,
            "orientation": None,
            "frame_rate": None
        }
    
    # Transform the database format to the frontend format
    line_data = calibration_data["line"]
    roi_data = calibration_data["square"]  # Square is used for ROI in the database
    orientation = calibration_data.get("orientation", "leftToRight")  # Default if not in DB
    frame_rate = calibration_data.get("frame_rate", 5)  # Default to 5 if not in DB
    
    return {
        "camera_id": camera_id,
        "roi": {
            "x1": roi_data["crop_x1"],
            "y1": roi_data["crop_y1"],
            "x2": roi_data["crop_x2"],
            "y2": roi_data["crop_y2"]
        },
        "line": {
            "startX": line_data["line_start_x"],
            "startY": line_data["line_start_y"],
            "endX": line_data["line_end_x"],
            "endY": line_data["line_end_y"]
        },
        "orientation": orientation,
        "frame_rate": frame_rate
    }

@router.get("/cameras/{camera_id}/feed")
def get_camera_feed_plural(camera_id: int, current_user: dict = Depends(get_current_user)):
    """
    Alias endpoint that matches the plural 'cameras' pattern used in other endpoints.
    Returns a live feed from the camera as a JPEG stream.
    """
    return get_camera_feed(camera_id, current_user)
```

## Test and Demo Files
File: `app/temp/webrtc_hybrid_test.html`
```html
# Run this command to see the full file:
# cat app/temp/webrtc_hybrid_test.html
```

File: `app/temp/test_webrtc.py`
```python
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WebRTC + WebSocket Hybrid Test</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }
        h1 {
            color: #333;
        }
        .video-container {
            position: relative;
            margin: 20px 0;
            background-color: #000;
            border-radius: 4px;
            overflow: hidden;
        }
        video {
            width: 100%;
            max-height: 500px;
            display: block;
        }
        canvas {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
        }
        .controls {
            margin: 20px 0;
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
        button {
            padding: 8px 16px;
            background-color: #4285f4;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        button:hover {
            background-color: #3367d6;
        }
        button:disabled {
            background-color: #cccccc;
            cursor: not-allowed;
        }
        .status {
            margin-top: 20px;
            padding: 10px;
            background-color: #f0f0f0;
            border-radius: 4px;
            font-family: monospace;
            white-space: pre-wrap;
            word-wrap: break-word;
            max-height: 300px;
            overflow-y: auto;
        }
        .input-group {
            margin: 10px 0;
            display: flex;
            flex-direction: column;
        }
        label {
            margin-bottom: 5px;
        }
        input, select {
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
        }
        .detection-box {
            position: absolute;
            border: 2px solid red;
            box-sizing: border-box;
        }
        .detection-text {
            position: absolute;
            background-color: rgba(255, 0, 0, 0.7);
            color: white;
            padding: 2px 5px;
            font-size: 12px;
        }
        .frame-rate-control {
            display: flex;
            align-items: center;
            margin: 10px 0;
            flex-wrap: wrap;
        }
        .frame-rate-control label {
            margin-right: 10px;
            min-width: 150px;
        }
        .frame-rate-control input {
            flex: 1;
            max-width: 400px;
            margin-right: 10px;
        }
        .frame-rate-control span {
            min-width: 30px;
        }
        #logOutput {
            max-height: 200px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 12px;
            background-color: #f8f8f8;
            padding: 10px;
            border-radius: 4px;
            border: 1px solid #ddd;
            margin-top: 20px;
        }
        .log-entry {
            margin-bottom: 3px;
        }
        .log-info {
            color: #333;
        }
        .log-error {
            color: #d32f2f;
        }
        .log-warning {
            color: #f57c00;
        }
        .log-success {
            color: #388e3c;
        }
        .log-debug {
            color: #0288d1;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>WebRTC + WebSocket Hybrid Test</h1>
        
        <div class="input-group">
            <label for="apiUrl">API URL:</label>
            <input type="text" id="apiUrl" value="http://localhost:8000/api" placeholder="http://localhost:8000/api">
        </div>
        
        <div class="input-group">
            <label for="cameraId">Camera ID:</label>
            <input type="number" id="cameraId" value="1" min="1">
        </div>
        
        <div class="input-group">
            <label for="username">Username:</label>
            <input type="text" id="username" value="admin" placeholder="Username">
        </div>
        
        <div class="input-group">
            <label for="password">Password:</label>
            <input type="password" id="password" value="123456" placeholder="Password">
        </div>
        
        <div class="frame-rate-control">
            <label for="frameRateSlider">Detection Frame Rate:</label>
            <input type="range" id="frameRateSlider" min="1" max="30" value="5">
            <span id="frameRateValue">5 FPS</span>
        </div>
        
        <div class="video-container">
            <video id="videoElement" autoplay playsinline muted></video>
            <canvas id="detectionCanvas"></canvas>
        </div>
        
        <div class="controls">
            <button id="startButton">Start</button>
            <button id="stopButton" disabled>Stop</button>
            <button id="testToken">Test Token</button>
        </div>
        
        <div class="status" id="statusElement">Status: Disconnected</div>
        <div id="logOutput"></div>
    </div>

    <script>
        // Configuration and state
        const config = {
            apiUrl: '',
            cameraId: 1,
            token: '',
            username: '',
            password: '',
            frameRate: 5
        };
        
        let rtcSignalingConnection = null;
        let rtcVideoConnection = null;
        let detectionDataConnection = null;
        let peerConnection = null;
        let videoStream = null;
        let isConnected = false;
        let isVideoPlaying = false;
        let lastReceivedFrame = null;
        let lastDetectionData = null;
        let videoFallbackMode = false;
        let connectionId = null;
        let videoSocket = null;
        let wsFallbackActive = false;
        
        // DOM Elements
        const videoElement = document.getElementById('videoElement');
        const detectionCanvas = document.getElementById('detectionCanvas');
        const statusElement = document.getElementById('statusElement');
        const startButton = document.getElementById('startButton');
        const stopButton = document.getElementById('stopButton');
        const apiUrlInput = document.getElementById('apiUrl');
        const cameraIdInput = document.getElementById('cameraId');
        const usernameInput = document.getElementById('username');
        const passwordInput = document.getElementById('password');
        const frameRateSlider = document.getElementById('frameRateSlider');
        const frameRateValue = document.getElementById('frameRateValue');
        const logOutput = document.getElementById('logOutput');
        
        // Canvas context for drawing detection boxes
        const ctx = detectionCanvas.getContext('2d');
        
        // Update frame rate display
        frameRateSlider.addEventListener('input', () => {
            const value = frameRateSlider.value;
            config.frameRate = parseInt(value);
            frameRateValue.textContent = `${value} FPS`;
        });
        
        // Remote logging functionality
        const consoleLog = {
            log: (...args) => {
                console.log(...args);
                appendLogEntry('info', args.join(' '));
            },
            error: (...args) => {
                console.error(...args);
                appendLogEntry('error', args.join(' '));
            },
            warn: (...args) => {
                console.warn(...args);
                appendLogEntry('warning', args.join(' '));
            },
            info: (...args) => {
                console.info(...args);
                appendLogEntry('info', args.join(' '));
            },
            debug: (...args) => {
                console.debug(...args);
                appendLogEntry('debug', args.join(' '));
            },
            success: (...args) => {
                appendLogEntry('success', args.join(' '));
            }
        };
        
        function appendLogEntry(type, message) {
            const entry = document.createElement('div');
            entry.className = `log-entry log-${type}`;
            const timestamp = new Date().toLocaleTimeString();
            entry.textContent = `[${timestamp}] ${message}`;
            logOutput.appendChild(entry);
            logOutput.scrollTop = logOutput.scrollHeight;
            
            // Limit log entries to 100
            while (logOutput.children.length > 100) {
                logOutput.removeChild(logOutput.firstChild);
            }
        }
        
        // Event listeners
        startButton.addEventListener('click', startStreaming);
        stopButton.addEventListener('click', stopStreaming);
        document.getElementById('testToken').addEventListener('click', async () => {
            consoleLog.info('Testing token acquisition...');
            const success = await getToken();
            if (success) {
                consoleLog.success('Token test successful!');
                alert('Authentication successful! Token: ' + config.token.substring(0, 20) + '...');
            } else {
                consoleLog.error('Token test failed!');
                alert('Authentication failed! Check console for details.');
            }
        });
        
        // Handle video sizing and canvas resizing
        function resizeCanvas() {
            detectionCanvas.width = videoElement.clientWidth;
            detectionCanvas.height = videoElement.clientHeight;
        }
        
        window.addEventListener('resize', resizeCanvas);
        videoElement.addEventListener('loadedmetadata', resizeCanvas);
        
        // Get authentication token
        async function getToken() {
            config.apiUrl = apiUrlInput.value.trim();
            config.username = usernameInput.value.trim();
            config.password = passwordInput.value.trim();
            
            consoleLog.info(`Attempting authentication to ${config.apiUrl}/token with username: ${config.username}`);
            
            try {
                const response = await fetch(`${config.apiUrl}/token`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    body: `username=${encodeURIComponent(config.username)}&password=${encodeURIComponent(config.password)}`
                });
                
                if (!response.ok) {
                    const errorText = await response.text();
                    consoleLog.error(`Authentication failed: ${response.status} ${response.statusText}`);
                    consoleLog.error(`Error details: ${errorText}`);
                    throw new Error(`Authentication failed: ${response.status} ${response.statusText}`);
                }
                
                const data = await response.json();
                config.token = data.access_token;
                consoleLog.success(`Authentication successful! Token: ${config.token.substring(0, 10)}...`);
                return true;
            } catch (error) {
                consoleLog.error('Failed to get authentication token:', error.message);
                updateStatus(`Authentication failed: ${error.message}`);
                return false;
            }
        }
        
        // Start streaming
        async function startStreaming() {
            if (isConnected) return;
            
            // Update config
            config.cameraId = parseInt(cameraIdInput.value);
            
            // Disable start button during connection
            startButton.disabled = true;
            updateStatus('Authenticating...');
            
            // Get authentication token
            if (!await getToken()) {
                startButton.disabled = false;
                return;
            }
            
            updateStatus('Connecting...');
            
            try {
                await connectWebRTC();
                
                // If WebRTC failed, fall back to WebSocket
                if (!isVideoPlaying && videoFallbackMode) {
                    updateStatus('Falling back to WebSocket video...');
                    await connectVideoWebSocket();
                }
                
                // Connect to detection data WebSocket in parallel
                await connectDetectionWebSocket();
                
                isConnected = true;
                startButton.disabled = true;
                stopButton.disabled = false;
                updateStatus('Connected');
            } catch (error) {
                consoleLog.error('Failed to start streaming:', error.message);
                updateStatus(`Connection failed: ${error.message}`);
                stopStreaming();
            }
        }
        
        // Stop streaming
        async function stopStreaming() {
            updateStatus('Disconnecting...');
            
            // Close RTCPeerConnection
            if (peerConnection) {
                // Close data channel
                if (dataChannel) {
                    dataChannel.close();
                    consoleLog.info('Data channel closed');
                }
                
                // Close WebRTC connection
                peerConnection.close();
                peerConnection = null;
            }
            
            // Close signaling WebSocket
            if (rtcSignalingConnection) {
                rtcSignalingConnection.close();
                rtcSignalingConnection = null;
            }
            
            // Close video WebSocket
            if (rtcVideoConnection) {
                rtcVideoConnection.close();
                rtcVideoConnection = null;
            }
            
            // Close detection data WebSocket
            if (detectionDataConnection) {
                detectionDataConnection.close();
                detectionDataConnection = null;
            }
            
            // Reset flags and UI
            isConnected = false;
            isVideoPlaying = false;
            videoFallbackMode = false;
            wsFallbackActive = false;
            startButton.disabled = false;
            stopButton.disabled = true;
            updateStatus('Disconnected');
        }
        
        // Connect to WebRTC
        async function connectWebRTC() {
            return new Promise(async (resolve, reject) => {
                try {
                    // Connect to signaling WebSocket
                    const wsUrl = `${config.apiUrl.replace('http', 'ws')}/ws/rtc-signaling/${config.cameraId}?token=${config.token}`;
                    rtcSignalingConnection = new WebSocket(wsUrl);
                    
                    // Set timeout for connection
                    const connectionTimeout = setTimeout(() => {
                        if (!isVideoPlaying) {
                            consoleLog.warn('WebRTC connection timed out, falling back to WebSocket video');
                            videoFallbackMode = true;
                            resolve();
                        }
                    }, 5000);
                    
                    rtcSignalingConnection.onopen = async () => {
                        updateStatus('Signaling connection established');
                        consoleLog.success('WebRTC signaling connection opened');
                    };
                    
                    rtcSignalingConnection.onmessage = async (event) => {
                        const message = JSON.parse(event.data);
                        consoleLog.debug('WebRTC signaling message received:', message.type);
                        
                        if (message.type === 'connected') {
                            // Store connection ID for further API requests
                            connectionId = message.connection_id;
                            consoleLog.success('WebRTC signaling connected with ID:', connectionId);
                            
                            // Create RTCPeerConnection
                            try {
                                await createPeerConnection();
                            } catch (error) {
                                consoleLog.error('Failed to create peer connection:', error.message);
                                videoFallbackMode = true;
                                clearTimeout(connectionTimeout);
                                resolve();
                            }
                        } else if (message.type === 'answer') {
                            // Set remote description from answer
                            try {
                                await setRemoteDescription(message);
                            } catch (error) {
                                consoleLog.error('Failed to set remote description:', error.message);
                            }
                        } else if (message.type === 'ice_candidate_received') {
                            // Get ICE candidates if needed
                            consoleLog.debug('ICE candidate received by server');
                        } else if (message.type === 'error') {
                            consoleLog.error('WebRTC signaling error:', message.message);
                        } else if (message.type === 'frame') {
                            // This is only for debugging - actual video frames will come through the peer connection
                            consoleLog.debug('Received frame via signaling channel (for debugging)');
                        }
                    };
                    
                    rtcSignalingConnection.onclose = () => {
                        consoleLog.warn('WebRTC signaling connection closed');
                        if (!isVideoPlaying && !videoFallbackMode) {
                            videoFallbackMode = true;
                            clearTimeout(connectionTimeout);
                            resolve();
                        }
                    };
                    
                    rtcSignalingConnection.onerror = (error) => {
                        consoleLog.error('WebRTC signaling error:', error);
                        if (!isVideoPlaying) {
                            videoFallbackMode = true;
                            clearTimeout(connectionTimeout);
                            resolve();
                        }
                    };
                    
                } catch (error) {
                    consoleLog.error('Failed to connect WebRTC:', error.message);
                    videoFallbackMode = true;
                    resolve();
                }
            });
        }
        
        // Create WebRTC peer connection
        async function createPeerConnection() {
            peerConnection = new RTCPeerConnection({
                iceServers: [
                    { urls: 'stun:stun.l.google.com:19302' }
                ]
            });
            
            peerConnection.onicecandidate = async (event) => {
                if (event.candidate) {
                    // Send ICE candidate to signaling channel
                    if (rtcSignalingConnection && rtcSignalingConnection.readyState === WebSocket.OPEN) {
                        rtcSignalingConnection.send(JSON.stringify({
                            type: 'ice_candidate',
                            candidate: event.candidate
                        }));
                        consoleLog.debug('ICE candidate sent to server');
                    }
                }
            };
            
            peerConnection.ontrack = (event) => {
                consoleLog.success('Received remote track from WebRTC');
                videoElement.srcObject = event.streams[0];
                videoStream = event.streams[0];
                isVideoPlaying = true;
            };
            
            peerConnection.oniceconnectionstatechange = () => {
                consoleLog.debug('ICE connection state:', peerConnection.iceConnectionState);
                if (peerConnection.iceConnectionState === 'failed' || 
                    peerConnection.iceConnectionState === 'disconnected' || 
                    peerConnection.iceConnectionState === 'closed') {
                    consoleLog.warn('ICE connection failed or closed');
                    if (!isVideoPlaying) {
                        videoFallbackMode = true;
                    }
                }
            };
            
            // Create data channel for additional communication if needed
            const dataChannel = peerConnection.createDataChannel('data');
            dataChannel.onopen = () => consoleLog.success('Data channel opened');
            dataChannel.onclose = () => consoleLog.warn('Data channel closed');
            dataChannel.onmessage = (event) => consoleLog.debug('Data channel message:', event.data);
            
            try {
                // Create offer
                const offer = await peerConnection.createOffer();
                await peerConnection.setLocalDescription(offer);
                
                // Send offer to signaling channel
                if (rtcSignalingConnection && rtcSignalingConnection.readyState === WebSocket.OPEN) {
                    rtcSignalingConnection.send(JSON.stringify({
                        type: 'offer',
                        sdp: offer.sdp
                    }));
                    consoleLog.success('WebRTC offer sent to server');
                }
            } catch (error) {
                consoleLog.error('Failed to create or send offer:', error.message);
                throw error;
            }
        }
        
        // Set remote description (answer from server)
        async function setRemoteDescription(answer) {
            try {
                consoleLog.info('Setting remote description from answer');
                
                // Clean up the fingerprint if it contains placeholders
                if (answer.sdp && answer.sdp.includes('XX:XX:XX:XX')) {
                    consoleLog.warning('Found placeholder fingerprint, skipping WebRTC and using WebSocket fallback');
                    startWebSocketFallback();
                    return false;
                }
                
                await peerConnection.setRemoteDescription(answer);
                consoleLog.success('Remote description set successfully');
                return true;
            } catch (error) {
                consoleLog.error('Failed to set remote description:', error.message);
                startWebSocketFallback();
                return false;
            }
        }
        
        // Start WebSocket fallback for video
        function startWebSocketFallback() {
            consoleLog.info('WebRTC connection timed out, falling back to WebSocket video');
            
            // Close any existing video WebSocket
            if (videoSocket && videoSocket.readyState === WebSocket.OPEN) {
                videoSocket.close();
            }
            
            // Connect to video WebSocket
            const videoUrl = `ws://${config.apiUrl.replace('http://', '').replace('https://', '').replace('/api', '')}/api/ws/rtc-video/${config.cameraId}?token=${config.token}`;
            videoSocket = new WebSocket(videoUrl);
            
            videoSocket.onopen = () => {
                consoleLog.info('Video WebSocket connection opened');
            };
            
            videoSocket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                
                // Handle frame data
                if (data.frame) {
                    if (!wsFallbackActive) {
                        consoleLog.success('Connected to video WebSocket');
                        wsFallbackActive = true;
                        updateStatus('Connected via WebSocket');
                    }
                    
                    // Display the frame
                    displayFrame(data.frame);
                }
            };
            
            videoSocket.onclose = () => {
                consoleLog.info('Video WebSocket connection closed');
                wsFallbackActive = false;
            };
            
            videoSocket.onerror = (error) => {
                consoleLog.error('Video WebSocket error:', error);
            };
        }
        
        // Connect to Video WebSocket as fallback
        async function connectVideoWebSocket() {
            return new Promise((resolve, reject) => {
                try {
                    const wsUrl = `${config.apiUrl.replace('http', 'ws')}/ws/rtc-video/${config.cameraId}?token=${config.token}`;
                    rtcVideoConnection = new WebSocket(wsUrl);
                    
                    rtcVideoConnection.onopen = () => {
                        updateStatus('Video WebSocket connection established');
                        consoleLog.success('Video WebSocket connection opened');
                        resolve();
                    };
                    
                    rtcVideoConnection.onmessage = (event) => {
                        const message = JSON.parse(event.data);
                        
                        if (message.status === 'connected') {
                            consoleLog.success('Connected to video WebSocket');
                        } else if (message.frame) {
                            // Display the frame
                            lastReceivedFrame = message;
                            displayVideoFrame(message.frame);
                        } else if (message.type === 'error') {
                            consoleLog.error('Video WebSocket error:', message.message);
                        }
                    };
                    
                    rtcVideoConnection.onclose = () => {
                        consoleLog.warn('Video WebSocket connection closed');
                        if (isConnected) {
                            stopStreaming();
                        }
                    };
                    
                    rtcVideoConnection.onerror = (error) => {
                        consoleLog.error('Video WebSocket error:', error);
                        reject(new Error('Video WebSocket connection failed'));
                    };
                } catch (error) {
                    consoleLog.error('Failed to connect to Video WebSocket:', error.message);
                    reject(error);
                }
            });
        }
        
        // Display video frame from WebSocket
        function displayVideoFrame(base64Frame) {
            const img = new Image();
            img.onload = () => {
                // Clear previous frame
                videoElement.style.display = 'none';
                
                // Set canvas size if needed
                if (detectionCanvas.width !== img.width || detectionCanvas.height !== img.height) {
                    detectionCanvas.width = img.width;
                    detectionCanvas.height = img.height;
                }
                
                // Draw the frame
                ctx.drawImage(img, 0, 0, detectionCanvas.width, detectionCanvas.height);
                
                // Draw detection boxes if available
                if (lastDetectionData && lastDetectionData.detections) {
                    drawDetectionBoxes(lastDetectionData.detections);
                }
                
                isVideoPlaying = true;
            };
            img.onerror = () => {
                consoleLog.error('Failed to load video frame');
            };
            img.src = 'data:image/jpeg;base64,' + base64Frame;
        }
        
        // Connect to Detection WebSocket
        async function connectDetectionWebSocket() {
            return new Promise((resolve, reject) => {
                try {
                    const wsUrl = `${config.apiUrl.replace('http', 'ws')}/ws/detection-data/${config.cameraId}?token=${config.token}&frame_rate=${config.frameRate}`;
                    detectionDataConnection = new WebSocket(wsUrl);
                    
                    detectionDataConnection.onopen = () => {
                        updateStatus('Detection WebSocket connection established');
                        consoleLog.success('Detection WebSocket connection opened');
                        resolve();
                    };
                    
                    detectionDataConnection.onmessage = (event) => {
                        try {
                            const data = JSON.parse(event.data);
                            
                            if (data.status === 'connected') {
                                consoleLog.success('Connected to detection data WebSocket');
                            } else if (data.detections !== undefined) {
                                // Store detection data
                                lastDetectionData = data;
                                
                                // Update detection status
                                const numDetections = Array.isArray(data.detections) ? data.detections.length : 0;
                                updateStatus(`Connected - ${numDetections} detections`);
                                
                                // Draw detection boxes if video is playing
                                if (isVideoPlaying) {
                                    drawDetectionBoxes(data.detections);
                                }
                            }
                        } catch (error) {
                            consoleLog.error('Error processing detection message:', error.message);
                        }
                    };
                    
                    detectionDataConnection.onclose = () => {
                        consoleLog.warn('Detection WebSocket connection closed');
                    };
                    
                    detectionDataConnection.onerror = (error) => {
                        consoleLog.error('Detection WebSocket error:', error);
                        reject(new Error('Detection WebSocket connection failed'));
                    };
                } catch (error) {
                    consoleLog.error('Failed to connect to Detection WebSocket:', error.message);
                    reject(error);
                }
            });
        }
        
        // Draw detection boxes on canvas
        function drawDetectionBoxes(detections) {
            if (!detections || !Array.isArray(detections) || detections.length === 0) {
                return;
            }
            
            // If using WebSocket video mode (fallback), we already have the frame on canvas
            // If using WebRTC, we need to draw on top of the video
            if (!videoFallbackMode) {
                // Clear previous drawings
                ctx.clearRect(0, 0, detectionCanvas.width, detectionCanvas.height);
            }
            
            // Draw each detection box
            detections.forEach(detection => {
                const { x, y, width, height, label, confidence } = detection;
                
                // Calculate scaled coordinates (assuming detection coordinates are normalized 0-1)
                let boxX, boxY, boxWidth, boxHeight;
                
                if (x >= 0 && x <= 1 && y >= 0 && y <= 1 && width >= 0 && width <= 1 && height >= 0 && height <= 1) {
                    // Normalized coordinates
                    boxX = x * detectionCanvas.width;
                    boxY = y * detectionCanvas.height;
                    boxWidth = width * detectionCanvas.width;
                    boxHeight = height * detectionCanvas.height;
                } else {
                    // Absolute pixel coordinates
                    boxX = x;
                    boxY = y;
                    boxWidth = width;
                    boxHeight = height;
                }
                
                // Draw the box
                ctx.strokeStyle = 'red';
                ctx.lineWidth = 2;
                ctx.strokeRect(boxX, boxY, boxWidth, boxHeight);
                
                // Draw label with confidence
                const displayText = label ? `${label} ${Math.round(confidence * 100)}%` : `${Math.round(confidence * 100)}%`;
                ctx.fillStyle = 'rgba(255, 0, 0, 0.7)';
                ctx.fillRect(boxX, boxY - 20, ctx.measureText(displayText).width + 10, 20);
                ctx.fillStyle = 'white';
                ctx.font = '12px Arial';
                ctx.fillText(displayText, boxX + 5, boxY - 5);
            });
        }
        
        // Update status display
        function updateStatus(message) {
            statusElement.textContent = `Status: ${message}`;
        }
        
        // Initialize with default values
        window.addEventListener('DOMContentLoaded', () => {
            // Set initial frame rate display
            frameRateValue.textContent = `${frameRateSlider.value} FPS`;
            
            // Initialize video element
            videoElement.addEventListener('play', () => {
                resizeCanvas();
                isVideoPlaying = true;
            });
            
            consoleLog.info('WebRTC + WebSocket Hybrid Test page loaded');
        });
    </script>
</body>
</html> 
```

## Extract Script

You can use the following script to extract all the relevant files into a single archive for analysis:

```bash
#!/bin/bash

# Create a directory for the extraction
mkdir -p zvision_extract

# Copy WebRTC implementation
cp app/routes/webrtc.py zvision_extract/
cp app/temp/webrtc_hybrid_test.html zvision_extract/
cp app/temp/test_webrtc.py zvision_extract/
cp app/temp/serve_webrtc_test.py zvision_extract/

# Copy WebSocket implementation
cp app/routes/websockets.py zvision_extract/
cp app/temp/websocket_browser_test.html zvision_extract/
cp app/temp/serve_websocket_test.py zvision_extract/
cp app/temp/test_websocket.py zvision_extract/

# Copy Detection Pipeline
cp app/routes/detection.py zvision_extract/
cp app/inference/pipeline.py zvision_extract/
cp app/inference/detection.py zvision_extract/
cp app/inference/crossing.py zvision_extract/

# Copy Camera Management
cp app/routes/camera.py zvision_extract/
cp app/database/cameras.py zvision_extract/
cp app/database/calibration.py zvision_extract/

# Create a archive
tar -czvf zvision_code.tar.gz zvision_extract/

echo "Extraction complete. Archive created at: zvision_code.tar.gz"
```

Save this script as `extract_code.sh`, make it executable with `chmod +x extract_code.sh`, and then run it with `./extract_code.sh`.

## Instructions

To view the complete content of any file, you can use the appropriate `cat` command listed under each section.

For example:
```bash
cat app/routes/webrtc.py
```

This will allow you to analyze the full implementations for WebRTC, WebSockets, detection, and video streaming in the ZVision project.
