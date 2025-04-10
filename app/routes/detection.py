# app/routes/detection.py

from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List, Dict
import cv2
import numpy as np

from app.routes.auth import get_current_user
from app.services.detection_service import detect_person_crossing, detect_all_people
from app.inference.detection import run_yolo_inference

router = APIRouter()

class DetectRequest(BaseModel):
    camera_id: str

@router.post("/detect")
def detect(
    camera_id: Optional[str] = Query(None), 
    req: Optional[DetectRequest] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Endpoint to detect people in the camera feed and trigger entry/exit detection.
    Supports both:
    1. Query parameter: /api/detect?camera_id=1
    2. JSON body: { "camera_id": "1" }
    
    Query parameter takes precedence if both are provided.
    
    Returns detection results with status, bounding boxes, and any crossing events.
    If a crossing is detected, an event is logged in the database.
    """
    # Determine which camera_id to use - query param has precedence
    cam_id_str = camera_id if camera_id is not None else (req.camera_id if req else None)
    
    if not cam_id_str:
        raise HTTPException(
            status_code=400, 
            detail="camera_id is required as either a query parameter or in the request body."
        )
    
    try:
        cam_id = int(cam_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid camera_id (must be an integer).")

    # Use the new function that detects all people without checking crossing
    detection_result = detect_all_people(cam_id)
    
    if detection_result is None:
        raise HTTPException(status_code=500, detail="Detection process failed.")

    # Format response according to API documentation
    return detection_result

class DetectionConfig(BaseModel):
    camera_id: int
    interval_seconds: int = 10  # Default to checking every 10 seconds
    enabled: bool = True

@router.post("/detection/config")
def configure_continuous_detection(
    config: DetectionConfig,
    current_user: dict = Depends(get_current_user),
    background_tasks: BackgroundTasks = None
):
    """
    Configure continuous detection for a camera.
    
    This endpoint allows setting up automatic detection at regular intervals.
    The actual implementation of continuous detection would require a background task system,
    which is beyond the scope of this demonstration.
    
    For a production system, you would need to use a task queue like Celery or a background
    service that maintains state about which cameras are being monitored and at what intervals.
    """
    # In a real implementation, this would save the configuration to a database
    # and start/stop background tasks as needed
    
    return {
        "status": "configured",
        "message": f"Detection configured for camera {config.camera_id} at {config.interval_seconds}s intervals",
        "config": {
            "camera_id": config.camera_id,
            "interval_seconds": config.interval_seconds,
            "enabled": config.enabled
        }
    }

@router.post("/detect_from_image")
async def detect_from_image(
    camera_id: int = Query(..., description="Camera ID for the detection"),
    file: UploadFile = File(..., description="Image file to process"),
    current_user: dict = Depends(get_current_user)
):
    """
    Process an uploaded image for object detection.
    
    Args:
        camera_id: ID of the camera associated with this detection
        file: Uploaded image file to process
        
    Returns:
        Detection results with bounding boxes, count, and status
    """
    # Read image from the uploaded file
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image file.")
    
    # Run YOLO inference on the image
    boxes, scores, labels = run_yolo_inference(img)
    
    # Filter detections with confidence > 50%
    filtered_boxes = []
    for i, box in enumerate(boxes):
        if scores[i] > 0.5:  # Only keep boxes with confidence > 50%
            filtered_boxes.append(box)
    
    # Create response in the standard format
    response = {
        "status": "people_detected" if filtered_boxes else "no_motion",
        "bounding_boxes": filtered_boxes,
        "crossing_detected": False,
        "count": len(filtered_boxes)
    }
    
    return response
