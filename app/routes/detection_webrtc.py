"""
WebRTC-based detection endpoints for ZVision.

This module provides endpoints for direct detection from WebRTC streams
at regular intervals, removing the need for websockets.
"""

import base64
import cv2
import io
import logging
import numpy as np
import time
from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

# Import auth for JWT validation
from app.routes.auth import get_current_user

# Import camera utilities
from app.routes.camera import _fetch_camera_source_by_id

# Import detection function
from app.inference.detection import run_yolo_inference

# Import webrtc frame extractor
from app.webrtc.frame_extractor import (
    create_frame_extractor, 
    start_frame_extractor,
    stop_frame_extractor,
    update_frame_rate
)

# Import WebRTC handler components
from app.webrtc.aiortc_handler import peer_connections

router = APIRouter()

# Configure logging
logger = logging.getLogger(__name__)

class DetectionRequest(BaseModel):
    camera_id: int
    image: Optional[str] = None  # Base64 encoded image (for direct API detection)
    frame_rate: Optional[int] = None  # Frame rate for WebRTC stream detection

class DetectionResponse(BaseModel):
    camera_id: int
    timestamp: float
    detections: List[Dict[str, Any]]

# Store active detection sessions
active_detection_sessions: Dict[int, Dict[str, Any]] = {}

@router.post("/detect", response_model=DetectionResponse)
async def detect_image(
    request: DetectionRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Detect objects in an image provided as base64 encoded string.
    
    Used by the test page to run detection on frames captured from WebRTC.
    """
    camera_id = request.camera_id
    
    # Check if camera exists
    if not _fetch_camera_source_by_id(camera_id):
        raise HTTPException(
            status_code=404, 
            detail=f"Camera with ID {camera_id} not found"
        )
    
    # Process the image if provided
    if not request.image:
        raise HTTPException(
            status_code=400,
            detail="Image data is required"
        )
    
    try:
        # Decode base64 image
        image_data = base64.b64decode(request.image)
        
        # Convert to OpenCV format
        nparr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            raise HTTPException(
                status_code=400,
                detail="Invalid image data"
            )
        
        # Run detection
        boxes, scores, labels = run_yolo_inference(image)
        
        # Format the results
        detections = []
        for i in range(len(boxes)):
            # Person is class 0 in COCO dataset
            class_name = "person" if labels[i] == 0 else f"class_{labels[i]}"
            
            detections.append({
                "class_id": int(labels[i]),
                "class_name": class_name,
                "confidence": float(scores[i]),
                "bbox": boxes[i]
            })
        
        # Return the detection result
        return DetectionResponse(
            camera_id=camera_id,
            timestamp=time.time(),
            detections=detections
        )
    
    except Exception as e:
        logger.error(f"Error processing detection: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Detection failed: {str(e)}"
        )

@router.post("/webrtc/{camera_id}/detect/start")
async def start_webrtc_detection(
    camera_id: int,
    frame_rate: Optional[int] = None, 
    current_user: dict = Depends(get_current_user)
):
    """
    Start detection on a WebRTC stream.
    
    This will extract frames at regular intervals and run detection on them.
    """
    # Check if camera exists
    if not _fetch_camera_source_by_id(camera_id):
        raise HTTPException(
            status_code=404, 
            detail=f"Camera with ID {camera_id} not found"
        )
    
    # Find an active peer connection for this camera
    active_connection_id = None
    track = None
    
    for conn_id, pc in peer_connections.items():
        if hasattr(pc, "camera_id") and pc.camera_id == camera_id:
            active_connection_id = conn_id
            
            # Get the video track from receivers
            for transceiver in pc.getTransceivers():
                if transceiver.receiver and transceiver.receiver.track and transceiver.receiver.track.kind == "video":
                    track = transceiver.receiver.track
                    break
            
            if track:
                break
    
    if not active_connection_id or not track:
        raise HTTPException(
            status_code=404,
            detail=f"No active WebRTC connection found for camera {camera_id}"
        )
    
    # Create frame extractor if it doesn't exist or update frame rate if it does
    try:
        # Define callback for detections
        def detection_callback(detections):
            session = active_detection_sessions.get(camera_id)
            if session:
                session["latest_detections"] = {
                    "timestamp": time.time(),
                    "detections": detections
                }
        
        # Create or get the frame extractor
        from app.webrtc import frame_extractor
        extractor = frame_extractor.create_frame_extractor(
            camera_id=camera_id,
            video_track=track,
            frame_rate=frame_rate,
            callback=detection_callback
        )
        
        # Start the frame extractor
        await extractor.start()
        
        # Store the session info
        active_detection_sessions[camera_id] = {
            "connection_id": active_connection_id,
            "frame_rate": extractor.frame_rate,
            "start_time": time.time(),
            "latest_detections": None
        }
        
        return {
            "message": f"Detection started for camera {camera_id} at {extractor.frame_rate} FPS",
            "camera_id": camera_id,
            "frame_rate": extractor.frame_rate
        }
    
    except Exception as e:
        logger.error(f"Error starting detection: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start detection: {str(e)}"
        )

@router.post("/webrtc/{camera_id}/detect/stop")
async def stop_webrtc_detection(
    camera_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Stop detection on a WebRTC stream.
    """
    # Check if camera exists
    if not _fetch_camera_source_by_id(camera_id):
        raise HTTPException(
            status_code=404, 
            detail=f"Camera with ID {camera_id} not found"
        )
    
    # Stop frame extractor
    try:
        if await stop_frame_extractor(camera_id):
            # Remove from active sessions
            session_info = active_detection_sessions.pop(camera_id, None)
            
            return {
                "message": f"Detection stopped for camera {camera_id}",
                "camera_id": camera_id
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"No active detection found for camera {camera_id}"
            )
    
    except Exception as e:
        logger.error(f"Error stopping detection: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop detection: {str(e)}"
        )

@router.post("/webrtc/{camera_id}/detect/update")
async def update_webrtc_detection(
    camera_id: int,
    frame_rate: int = Body(..., embed=True),
    current_user: dict = Depends(get_current_user)
):
    """
    Update the frame rate for WebRTC stream detection.
    """
    # Check if camera exists
    if not _fetch_camera_source_by_id(camera_id):
        raise HTTPException(
            status_code=404, 
            detail=f"Camera with ID {camera_id} not found"
        )
    
    # Update frame rate
    try:
        if await update_frame_rate(camera_id, frame_rate):
            # Update session info
            if camera_id in active_detection_sessions:
                active_detection_sessions[camera_id]["frame_rate"] = frame_rate
            
            return {
                "message": f"Detection frame rate updated for camera {camera_id}",
                "camera_id": camera_id,
                "frame_rate": frame_rate
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"No active detection found for camera {camera_id}"
            )
    
    except Exception as e:
        logger.error(f"Error updating detection frame rate: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update detection frame rate: {str(e)}"
        )

@router.get("/webrtc/{camera_id}/detect/status")
async def get_webrtc_detection_status(
    camera_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Get the current status of WebRTC stream detection.
    """
    # Check if camera exists
    if not _fetch_camera_source_by_id(camera_id):
        raise HTTPException(
            status_code=404, 
            detail=f"Camera with ID {camera_id} not found"
        )
    
    # Get session info
    session = active_detection_sessions.get(camera_id)
    if not session:
        return {
            "active": False,
            "camera_id": camera_id,
            "message": f"No active detection for camera {camera_id}"
        }
    
    # Return status
    return {
        "active": True,
        "camera_id": camera_id,
        "frame_rate": session["frame_rate"],
        "running_time": time.time() - session["start_time"],
        "latest_detection_time": session["latest_detections"]["timestamp"] if session["latest_detections"] else None,
        "latest_detections": session["latest_detections"]["detections"] if session["latest_detections"] else []
    }
