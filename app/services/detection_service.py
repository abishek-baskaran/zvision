from typing import Dict, List, Optional
from app.inference.pipeline import process_camera_stream
from app.database.events import add_event
from app.database.cameras import get_camera_by_id
from datetime import datetime
import cv2
import numpy as np
from app.database.calibration import fetch_calibration_for_camera
from app.inference.detection import run_yolo_inference

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
    
    # Get calibration data to properly crop the frame
    calib = fetch_calibration_for_camera(camera_id)
    if not calib:
        # Try to just process the full frame if no calibration
        cap = cv2.VideoCapture(source_path)
        if not cap.isOpened():
            return response
        
        ret, frame = cap.read()
        if not ret or frame is None:
            cap.release()
            return response
        
        # Run detection on the frame
        boxes, scores, labels = run_yolo_inference(frame)
        
        all_boxes = []
        for i, box in enumerate(boxes):
            if scores[i] > 0.5:  # Only keep boxes with confidence > 50%
                all_boxes.append(box)
        
        # Update response
        if all_boxes:
            response = {
                "status": "people_detected",
                "bounding_boxes": all_boxes,
                "crossing_detected": False,
                "count": len(all_boxes)
            }
        
        cap.release()
        return response
    
    # Extract calibration data
    square_data = calib["square"]
    crop_x1, crop_y1, crop_x2, crop_y2 = (
        int(square_data["crop_x1"]),
        int(square_data["crop_y1"]),
        int(square_data["crop_x2"]),
        int(square_data["crop_y2"]),
    )
    
    # Open the camera
    cap = cv2.VideoCapture(source_path)
    if not cap.isOpened():
        return response
    
    ret, frame = cap.read()
    if not ret or frame is None:
        cap.release()
        return response
    
    # Crop frame to detection area
    try:
        frame = frame[crop_y1:crop_y2, crop_x1:crop_x2]
    except:
        # If cropping fails, use the full frame
        pass
    
    # Resize for faster processing
    detection_frame = cv2.resize(frame, (0, 0), fx=0.7, fy=0.7)
    
    # Run detection
    boxes, scores, labels = run_yolo_inference(detection_frame)
    
    # Process results
    all_boxes = []
    for i, box in enumerate(boxes):
        if scores[i] > 0.5:  # Only keep boxes with confidence > 50%
            x_min, y_min, x_max, y_max = box
            # Scale back to original size
            scale_factor = 1.0 / 0.7
            x_min = int(x_min * scale_factor)
            y_min = int(y_min * scale_factor)
            x_max = int(x_max * scale_factor)
            y_max = int(y_max * scale_factor)
            all_boxes.append([x_min, y_min, x_max, y_max])
    
    # Update response with detections
    if all_boxes:
        response = {
            "status": "people_detected",
            "bounding_boxes": all_boxes,
            "crossing_detected": False,
            "count": len(all_boxes)
        }
    
    cap.release()
    return response