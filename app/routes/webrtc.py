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
from app.webrtc.aiortc_handler import (
    process_offer, 
    add_ice_candidate,
    cleanup_peer_connection,
    cleanup_camera_connections
)

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
    """
    DEPRECATED: This custom SDP parser will be replaced with aiortc.
    """
    logging.warning("Using deprecated custom SDP parser. To be replaced with aiortc.")
    # Return a simple structure instead of parsing
    return {"original_sdp": sdp}

def generate_matching_answer(offer_sdp: str) -> str:
    """
    DEPRECATED: This custom SDP generator will be replaced with aiortc.
    This will be fully replaced with proper aiortc-generated SDP answers.
    """
    logging.warning("Using deprecated SDP answer generator. To be replaced with aiortc.")
    # Return minimal SDP to indicate this is not functional for media
    # Browsers will recognize this isn't valid and should fall back to alternative methods
    return "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n"

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
    
    try:
        # Process the offer with aiortc
        answer_sdp = await process_offer(connection_id, camera_id, offer_data["sdp"])
        
        # Create answer
        answer = {
            "type": "answer",
            "sdp": answer_sdp
        }
        
        # Store the answer
        rtc_connections[connection_id].answer = answer
        
    except Exception as e:
        # Fallback to deprecated method if aiortc processing fails
        logging.warning(f"aiortc processing failed, falling back: {str(e)}")
        answer_sdp = generate_matching_answer(offer_data["sdp"])
        answer = {
            "type": "answer",
            "sdp": answer_sdp
        }
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
async def add_ice_candidate_endpoint(connection_id: str, request: Request):
    """
    Add ICE candidate for a connection
    """
    # Check if connection exists
    if connection_id not in rtc_connections:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, 
                           detail=f"Connection with ID {connection_id} not found")
    
    # Get the JSON data from the request
    ice_data = await request.json()
    if not ice_data or "candidate" not in ice_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                           detail="Invalid ICE candidate format")
    
    # Add candidate to aiortc peer connection
    success = await add_ice_candidate(connection_id, ice_data["candidate"])
    
    # Store the candidate for potential use in websocket fallback
    if "candidate" not in rtc_connections[connection_id].ice_candidates:
        rtc_connections[connection_id].ice_candidates.append(ice_data["candidate"])
    
    return {"success": success}

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
async def rtc_signaling_websocket(websocket: WebSocket, camera_id: int, token: Optional[str] = Query(None)):
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
                
                try:
                    # Process the offer with aiortc
                    offer_sdp = message.get("sdp", "")
                    answer_sdp = await process_offer(connection_id, camera_id, offer_sdp)
                    
                    # Create answer
                    answer = {
                        "type": "answer",
                        "sdp": answer_sdp
                    }
                    
                    # Store the answer
                    rtc_connections[connection_id].answer = answer
                    
                except Exception as e:
                    # Fallback to deprecated method if aiortc processing fails
                    logging.warning(f"aiortc processing failed in WebSocket, falling back: {str(e)}")
                    offer_sdp = message.get("sdp", "")
                    answer_sdp = generate_matching_answer(offer_sdp)
                    
                    # Create answer
                    answer = {
                        "type": "answer",
                        "sdp": answer_sdp
                    }
                    
                    # Store the answer
                    rtc_connections[connection_id].answer = answer
                
                # Send the answer
                await websocket.send_json(answer)
                
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
                
            elif message_type == "ice_candidate":
                # Add ICE candidate
                if "candidate" not in message:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid ICE candidate format, missing 'candidate'"
                    })
                    continue
                
                # Add candidate to aiortc peer connection
                success = await add_ice_candidate(connection_id, message["candidate"])
                
                # Store the candidate
                rtc_connections[connection_id].ice_candidates.append(message["candidate"])
                
                # Send confirmation
                await websocket.send_json({
                    "type": "ice_candidate_received",
                    "success": success
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