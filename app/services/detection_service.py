from typing import Dict, List, Optional
from app.inference.pipeline import process_camera_stream
from app.database.events import add_event
from app.database.cameras import get_camera_by_id
from datetime import datetime
import cv2
import numpy as np
from app.database.calibration import fetch_calibration_for_camera
import time

# Import the new modules
from app.camera_manager import camera_manager
from app.detection_worker import detection_manager
from app.analytics import analytics

def detect_person_crossing(camera_id: int) -> Optional[Dict]:
    """
    Processes the camera stream and determines if a person enters or exits.
    Returns a dictionary with detection status, bounding boxes and crossing detection.
    """
    # Fetch camera source path
    camera = get_camera_by_id(camera_id)
    if not camera:
        return None
    source_path = camera.get("source")
    if not source_path:
        return None

    # For now, still use the existing pipeline function (will change in later phases)
    detection_result = process_camera_stream(camera_id, source_path)
    
    # Default response
    response = {
        "status": "no_motion",
        "bounding_boxes": [],
        "crossing_detected": False
    }
    
    # If we got a detection result
    if detection_result and isinstance(detection_result, dict):
        event_type = detection_result.get("event_type")
        bounding_boxes = detection_result.get("bounding_boxes", [])
        
        # Simulating a clip path (if videos are stored)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        clip_path = f"/recordings/camera_{camera_id}_{event_type}_{timestamp.replace(' ', '_')}.mp4"

        # Log the event if we detected a crossing
        if event_type in ["entry", "exit"]:
            # Add event to database
            event_id = add_event(
                store_id=camera.get("store_id"),
                event_type=event_type,
                clip_path=clip_path,
                timestamp=timestamp,
                camera_id=camera_id
            )
            
            # Update response
            response = {
                "status": f"{event_type}_detected",
                "bounding_boxes": bounding_boxes,
                "crossing_detected": True,
                "event_id": event_id,
                "timestamp": timestamp
            }
    elif detection_result and isinstance(detection_result, str):
        # Handle legacy string return format
        if detection_result in ["entry", "exit"]:
            # Simulating a clip path (if videos are stored)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            clip_path = f"/recordings/camera_{camera_id}_{detection_result}_{timestamp.replace(' ', '_')}.mp4"
            
            # Add event to database
            event_id = add_event(
                store_id=camera.get("store_id"),
                event_type=detection_result,
                clip_path=clip_path,
                timestamp=timestamp,
                camera_id=camera_id
            )
            
            # Update response
            response = {
                "status": f"{detection_result}_detected", 
                "bounding_boxes": [[0, 0, 0, 0]],  # Default bounding box
                "crossing_detected": True,
                "event_id": event_id,
                "timestamp": timestamp
            }

    return response

def detect_all_people(camera_id: int) -> Optional[Dict]:
    """
    Detect all people in the camera feed without checking for line crossing.
    Returns all detected bounding boxes regardless of crossing status.
    
    Args:
        camera_id: ID of the camera to process.
        
    Returns:
        Dictionary with:
        - "status": "people_detected" if people found, "no_motion" otherwise
        - "bounding_boxes": List of all detected bounding boxes
        - "crossing_detected": Always False (crossing logic is disabled)
        - "count": Number of people detected
    """
    # Fetch camera source path
    camera = get_camera_by_id(camera_id)
    if not camera:
        return None
    source_path = camera.get("source")
    if not source_path:
        return None
    
    # Default response
    response = {
        "status": "no_motion",
        "bounding_boxes": [],
        "crossing_detected": False,
        "count": 0
    }
    
    # Start timing
    start_time = time.time()
    
    # Make sure the camera with detection is running
    camera_manager.get_camera(camera_id, source_path, enable_detection=True)
    
    # Get latest detection result from detection manager
    detection_result = detection_manager.get_latest_result(camera_id)
    
    if detection_result is None:
        # No detection result available yet
        analytics.record_call(camera_id, "detect_all_people", "no_result", time.time() - start_time)
        return response
    
    # Process results
    all_boxes = []
    detection_count = 0
    
    # Extract detection information
    for detection in detection_result.detections:
        if detection.score > 0.5:  # Only keep detections with confidence > 50%
            box = detection.bbox  # Already in [x_min, y_min, x_max, y_max] format
            all_boxes.append(box)
            detection_count += 1
    
    # Record analytics for API call
    total_time = time.time() - start_time
    analytics.record_call(camera_id, "detect_all_people", "success", total_time)
    
    # Update response with detections
    if all_boxes:
        response = {
            "status": "people_detected",
            "bounding_boxes": all_boxes,
            "crossing_detected": False,
            "count": len(all_boxes),
            "timestamp": detection_result.timestamp,
            "processing_time_ms": int(total_time * 1000)
        }
    
    return response