from typing import Dict, List, Optional
from app.inference.pipeline import process_camera_stream
from app.database.events import add_event
from app.database.cameras import get_camera_by_id
from datetime import datetime

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

    # Process the camera stream and get results
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