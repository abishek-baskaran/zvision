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
