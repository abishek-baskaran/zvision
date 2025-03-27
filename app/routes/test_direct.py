"""
Direct test routes for ZVision.

These routes bypass the normal API structure and directly access the 
camera_manager and detection_manager for testing purposes.
"""

import base64
import cv2
import io
import logging
import time
from fastapi import APIRouter, HTTPException, Form, File, UploadFile
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Dict, List, Optional, Any, Union
import numpy as np

# Import the managers directly
from app.camera_manager import camera_manager
from app.detection_worker import detection_manager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/test", tags=["test"])

# Request/response models
class CameraRequest(BaseModel):
    camera_id: int
    source: str
    enable_detection: bool = False

class ActionRequest(BaseModel):
    camera_id: int


@router.post("/start_camera")
async def start_camera(request: CameraRequest):
    """
    Start a camera directly using the camera_manager
    """
    try:
        # Check if camera already exists
        if request.camera_id in camera_manager.cameras:
            camera_manager.release_camera(request.camera_id)
            logger.info(f"Released existing camera {request.camera_id}")
        
        # Get (start) the camera
        camera = camera_manager.get_camera(
            request.camera_id, 
            request.source, 
            enable_detection=request.enable_detection
        )
        
        if not camera:
            raise HTTPException(status_code=500, detail="Failed to start camera")
        
        # Wait briefly for the camera to initialize
        time.sleep(1)
        
        # Get camera status
        status = camera_manager.get_camera_status(request.camera_id)
        
        return {
            "camera_id": request.camera_id,
            "status": status.get("status", "starting"),
            "message": "Camera started successfully"
        }
    except Exception as e:
        logger.exception(f"Error starting camera: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start camera: {str(e)}")


@router.post("/stop_camera")
async def stop_camera(request: ActionRequest):
    """
    Stop a camera directly using the camera_manager
    """
    try:
        # Check if camera exists
        if request.camera_id not in camera_manager.cameras:
            return {
                "camera_id": request.camera_id,
                "status": "not_found",
                "message": "Camera not found"
            }
        
        # Stop detection worker first if running
        if detection_manager.is_worker_running(request.camera_id):
            detection_manager.stop_worker(request.camera_id)
            logger.info(f"Stopped detection worker for camera {request.camera_id}")
        
        # Release the camera
        success = camera_manager.release_camera(request.camera_id)
        
        return {
            "camera_id": request.camera_id,
            "status": "stopped" if success else "error",
            "message": "Camera stopped successfully" if success else "Failed to stop camera"
        }
    except Exception as e:
        logger.exception(f"Error stopping camera: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to stop camera: {str(e)}")


@router.post("/enable_detection")
async def enable_detection(request: ActionRequest):
    """
    Enable detection for a camera directly
    """
    try:
        # Check if camera exists
        if request.camera_id not in camera_manager.cameras:
            raise HTTPException(status_code=404, detail=f"Camera {request.camera_id} not found")
        
        # Enable detection
        success = camera_manager.enable_detection(request.camera_id)
        
        return {
            "camera_id": request.camera_id,
            "status": "enabled" if success else "error",
            "message": "Detection enabled successfully" if success else "Failed to enable detection"
        }
    except Exception as e:
        logger.exception(f"Error enabling detection: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to enable detection: {str(e)}")


@router.post("/disable_detection")
async def disable_detection(request: ActionRequest):
    """
    Disable detection for a camera directly
    """
    try:
        # Check if camera exists
        if request.camera_id not in camera_manager.cameras:
            raise HTTPException(status_code=404, detail=f"Camera {request.camera_id} not found")
        
        # Disable detection
        success = camera_manager.disable_detection(request.camera_id)
        
        return {
            "camera_id": request.camera_id,
            "status": "disabled" if success else "error",
            "message": "Detection disabled successfully" if success else "Failed to disable detection"
        }
    except Exception as e:
        logger.exception(f"Error disabling detection: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to disable detection: {str(e)}")


@router.get("/get_frame")
async def get_frame(camera_id: int):
    """
    Get a single frame from the camera as JPEG image
    """
    try:
        # Check if camera exists
        if camera_id not in camera_manager.cameras:
            raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
        
        # Get a frame from the camera
        frame_result = camera_manager.cameras[camera_id].get_frame()
        
        if not frame_result:
            raise HTTPException(status_code=500, detail="No frame available")
        
        frame, timestamp = frame_result
        
        # Encode the frame as JPEG
        success, buffer = cv2.imencode(".jpg", frame)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to encode frame")
        
        # Return the image as a streaming response
        return StreamingResponse(io.BytesIO(buffer.tobytes()), media_type="image/jpeg")
    except Exception as e:
        logger.exception(f"Error getting frame: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get frame: {str(e)}")


@router.get("/get_status")
async def get_status(camera_id: int):
    """
    Get camera status directly
    """
    try:
        # Check if camera exists
        if camera_id not in camera_manager.cameras:
            raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
        
        # Get camera status
        status = camera_manager.get_camera_status(camera_id)
        
        return {
            "camera_id": camera_id,
            "camera_status": status.get("status", "unknown"),
            "fps": status.get("fps", 0),
            "frame_count": status.get("frame_count", 0),
            "uptime": status.get("uptime", 0),
            "detection_enabled": status.get("detection_enabled", False)
        }
    except Exception as e:
        logger.exception(f"Error getting status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.get("/get_detection")
async def get_detection(camera_id: int):
    """
    Get detection results directly
    """
    try:
        # Check if camera exists
        if camera_id not in camera_manager.cameras:
            raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
        
        # Check if detection is running
        if not detection_manager.is_worker_running(camera_id):
            return {
                "camera_id": camera_id,
                "status": "detection_not_running",
                "message": "Detection is not running for this camera",
                "boxes": [],
                "scores": [],
                "labels": [],
                "count": 0
            }
        
        # Get latest detection
        result = detection_manager.get_latest_detection(camera_id)
        
        if not result:
            return {
                "camera_id": camera_id,
                "status": "no_detection",
                "message": "No detection results available yet",
                "boxes": [],
                "scores": [],
                "labels": [],
                "count": 0
            }
        
        # Filter detections with confidence > 50%
        filtered_boxes = result.get_filtered_boxes(0.5)
        filtered_scores = [result.scores[i] for i, box in enumerate(result.boxes) if result.scores[i] >= 0.5]
        filtered_labels = [result.labels[i] for i, box in enumerate(result.boxes) if result.scores[i] >= 0.5]
        
        # Format the response
        return {
            "camera_id": camera_id,
            "status": "people_detected" if filtered_boxes else "no_motion",
            "boxes": filtered_boxes,
            "scores": filtered_scores,
            "labels": filtered_labels,
            "count": len(filtered_boxes),
            "timestamp": result.timestamp,
            "processed_time": result.processed_time
        }
    except Exception as e:
        logger.exception(f"Error getting detection: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get detection: {str(e)}") 