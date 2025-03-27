#!/usr/bin/env python3
"""
API Test script for Detection functionality

This script tests the detection API endpoints in the ZVision system.
It validates detection starting, status checking, and results.
"""

import argparse
import os
import sys
import time
import json
import requests
from typing import Dict, Any, Optional, List
import cv2
import numpy as np
import base64
from PIL import Image
import io

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# API base URL
BASE_URL = "http://localhost:8000/api"

def test_add_camera(camera_id: int = 1, source: str = "/dev/video0", 
                   enable_detection: bool = True) -> Dict[str, Any]:
    """
    Test adding a camera with detection via the API
    
    Args:
        camera_id: ID for the camera (integer)
        source: Camera source (device, file, or URL)
        enable_detection: Whether to enable detection
        
    Returns:
        API response as dictionary
    """
    print(f"Adding camera {camera_id} with source {source} (detection: {enable_detection})")
    
    url = f"{BASE_URL}/camera/add"
    payload = {
        "camera_id": camera_id,
        "source": source,
        "enable_detection": enable_detection
    }
    
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        print(f"Successfully added camera {camera_id}")
        return response.json()
    else:
        print(f"Failed to add camera: {response.status_code}, {response.text}")
        return {"error": response.text}

def test_detection_status(camera_id: int = 1) -> Dict[str, Any]:
    """
    Test getting detection status for a camera via the API
    
    Args:
        camera_id: ID of the camera
        
    Returns:
        Detection status as dictionary
    """
    print(f"Checking detection status for camera {camera_id}")
    
    url = f"{BASE_URL}/camera/{camera_id}/detection/status"
    response = requests.get(url)
    
    if response.status_code == 200:
        status = response.json()
        print(f"Detection status for camera {camera_id}: {json.dumps(status, indent=2)}")
        return status
    else:
        print(f"Failed to get detection status: {response.status_code}, {response.text}")
        return {"error": response.text}

def test_run_detection(camera_id: int = 1) -> Dict[str, Any]:
    """
    Test running detection directly via the API
    
    Args:
        camera_id: ID of the camera
        
    Returns:
        Detection results as dictionary
    """
    print(f"Running detection for camera {camera_id}")
    
    url = f"{BASE_URL}/detect?camera_id={camera_id}"
    response = requests.post(url)
    
    if response.status_code == 200:
        results = response.json()
        print(f"Detection results: {json.dumps(results, indent=2)}")
        return results
    else:
        print(f"Failed to run detection: {response.status_code}, {response.text}")
        return {"error": response.text}

def capture_and_detect_image(camera_id: int = 1) -> Dict[str, Any]:
    """
    Capture an image directly using OpenCV and send it for detection
    
    Args:
        camera_id: ID to use with the detection request
        
    Returns:
        Detection results as dictionary
    """
    # Use the device ID or path as an integer or string
    if isinstance(camera_id, int):
        # For integer camera IDs (e.g., webcam index)
        cap = cv2.VideoCapture(camera_id)
    else:
        # For string paths (e.g., RTSP URL or video file)
        cap = cv2.VideoCapture(camera_id)
    
    if not cap.isOpened():
        print(f"Error: Could not open camera {camera_id}")
        return {"error": "Failed to open camera"}
    
    # Capture a single frame
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        print("Error: Failed to capture image")
        return {"error": "Failed to capture image"}
    
    # Convert to base64
    _, buffer = cv2.imencode('.jpg', frame)
    img_base64 = base64.b64encode(buffer).decode('utf-8')
    
    # Save the image for reference
    os.makedirs("output", exist_ok=True)
    cv2.imwrite(f"output/detection_test_image.jpg", frame)
    print(f"Saved test image to output/detection_test_image.jpg")
    
    # Send to detection endpoint
    url = f"{BASE_URL}/detect"
    payload = {
        "camera_id": str(camera_id),
        "image": img_base64
    }
    
    print("Sending image for detection...")
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        results = response.json()
        print(f"Detection results: {json.dumps(results, indent=2)}")
        return results
    else:
        print(f"Failed to detect objects: {response.status_code}, {response.text}")
        return {"error": response.text}

def visualize_detections(image_path: str, detection_results: Dict[str, Any], 
                        output_path: str = "output/detection_results.jpg"):
    """
    Visualize detection results on an image
    
    Args:
        image_path: Path to the input image
        detection_results: Detection results from the API
        output_path: Path to save the output image
    """
    print(f"Visualizing detections on {image_path}")
    
    # Load the image
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Could not load image from {image_path}")
        return
    
    # Extract bounding boxes, scores, and labels
    boxes = detection_results.get("boxes", [])
    scores = detection_results.get("scores", [])
    labels = detection_results.get("labels", [])
    
    # Draw bounding boxes on the image
    for i, box in enumerate(boxes):
        score = scores[i] if i < len(scores) else 0
        label = labels[i] if i < len(labels) else 0
        
        if score >= 0.5:  # Only show confident detections
            x1, y1, x2, y2 = box
            
            # Draw bounding box
            cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # Add label and score
            text = f"Class {label}: {score:.2f}"
            cv2.putText(image, text, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    
    # Save the output image
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cv2.imwrite(output_path, image)
    print(f"Saved visualization to {output_path}")

def wait_for_detection_status(camera_id: int, target_status: str = "running", 
                             max_wait: int = 30) -> bool:
    """
    Wait for detection to reach a specific status
    
    Args:
        camera_id: ID of the camera
        target_status: Target status to wait for
        max_wait: Maximum wait time in seconds
        
    Returns:
        True if target status was reached, False if timed out
    """
    print(f"Waiting for detection on camera {camera_id} to reach status '{target_status}'")
    
    start_time = time.time()
    while time.time() - start_time < max_wait:
        status = test_detection_status(camera_id)
        detection_status = status.get("detection_status", {}).get("status", "unknown")
        
        print(f"Detection status: {detection_status}")
        
        if detection_status == target_status:
            print(f"Detection for camera {camera_id} reached status '{target_status}'")
            return True
        
        time.sleep(1)
    
    print(f"Timeout: Detection for camera {camera_id} did not reach status '{target_status}' within {max_wait} seconds")
    return False

def cleanup_detection():
    """
    Clean up by disabling detection for all cameras and removing cameras
    
    Returns:
        True if successful, False otherwise
    """
    print("\nCleaning up detection and cameras...")
    
    try:
        # Import the camera list function
        from test_camera_api import test_camera_list
        
        # Get list of all cameras
        cameras = test_camera_list()
        
        if isinstance(cameras, list):
            print(f"Found {len(cameras)} cameras to clean up")
            
            # Disable detection for each camera and then remove
            for camera in cameras:
                # Handle different possible formats of camera info
                if isinstance(camera, dict) and "camera_id" in camera:
                    camera_id = camera["camera_id"]
                elif isinstance(camera, str):
                    # Try to extract camera ID from string representation
                    try:
                        # Assume format like "Camera 1: running"
                        parts = camera.split(":")
                        if len(parts) > 0:
                            camera_id_part = parts[0].replace("Camera", "").strip()
                            camera_id = int(camera_id_part)
                        else:
                            print(f"Could not extract camera ID from {camera}")
                            continue
                    except (ValueError, IndexError):
                        print(f"Could not extract camera ID from {camera}")
                        continue
                else:
                    print(f"Unrecognized camera format: {camera}")
                    continue
                
                # First disable detection
                print(f"Disabling detection for camera {camera_id}")
                try:
                    url = f"{BASE_URL}/camera/{camera_id}/disable_detection"
                    response = requests.get(url)
                    
                    if response.status_code == 200:
                        print(f"Successfully disabled detection for camera {camera_id}")
                    else:
                        print(f"Failed to disable detection: {response.status_code}, {response.text}")
                except Exception as e:
                    print(f"Error disabling detection: {e}")
                
                # Then replace with dummy camera to remove it
                print(f"Removing camera {camera_id}")
                try:
                    url = f"{BASE_URL}/camera/add"
                    payload = {
                        "camera_id": camera_id,
                        "source": "none://dummy",
                        "enable_detection": False
                    }
                    response = requests.post(url, json=payload)
                    
                    if response.status_code == 200:
                        print(f"Successfully removed camera {camera_id}")
                    else:
                        print(f"Failed to remove camera: {response.status_code}, {response.text}")
                except Exception as e:
                    print(f"Error removing camera: {e}")
            
            print("Detection and camera cleanup completed")
            return True
        else:
            print(f"Failed to get camera list for cleanup: {cameras}")
            return False
            
    except Exception as e:
        print(f"Error during detection cleanup: {e}")
        return False

def main():
    """
    Main function to run detection API tests
    """
    parser = argparse.ArgumentParser(description="Test Detection API endpoints")
    parser.add_argument("--source", type=str, default="/dev/video0", 
                       help="Camera source (device, file, or URL)")
    parser.add_argument("--id", type=int, default=1, 
                       help="Camera ID to use for testing")
    parser.add_argument("--direct-detect", action="store_true", 
                       help="Test direct detection without adding a camera")
    parser.add_argument("--visualize", action="store_true", 
                       help="Visualize detection results")
    parser.add_argument("--cleanup", action="store_true",
                       help="Clean up detection and cameras after test")
    args = parser.parse_args()
    
    # Convert source to int if it's a digit
    source = args.source
    if source.isdigit():
        source = int(source)
    
    try:
        if args.direct_detect:
            print("\n===== Testing direct detection =====\n")
            
            # Capture an image and detect objects
            results = capture_and_detect_image(args.id)
            
            if args.visualize and "error" not in results:
                # Visualize the results
                visualize_detections(
                    "output/detection_test_image.jpg", 
                    results,
                    "output/detection_results.jpg"
                )
        else:
            print("\n===== Testing detection with camera =====\n")
            
            # Step 1: Add camera with detection enabled
            result = test_add_camera(args.id, source, True)
            
            # Step 2: Wait for detection to start
            wait_for_detection_status(args.id, "running", 30)
            
            # Step 3: Get detection status
            detection_status = test_detection_status(args.id)
            
            # Step 4: Run detection
            detection_results = test_run_detection(args.id)
            
            print("\n===== Detection API Test Results =====\n")
            status_obj = detection_status.get("detection_status", {})
            print(f"Detection Status: {status_obj.get('status', 'unknown')}")
            print(f"Detection FPS: {status_obj.get('fps', 0)}")
            print(f"Frames Processed: {status_obj.get('frames_processed', 0)}")
            
            # Print detection results
            if "error" not in detection_results:
                print(f"\nDetections: {len(detection_results.get('boxes', []))}")
                
                if args.visualize:
                    # Capture an image for visualization
                    capture_result = capture_and_detect_image(args.id)
                    if "error" not in capture_result:
                        visualize_detections(
                            "output/detection_test_image.jpg", 
                            capture_result,
                            "output/detection_results.jpg"
                        )
            
            print("\nTest completed successfully!")

    except Exception as e:
        print(f"\nError during test: {e}")
    
    finally:
        # Clean up if requested
        if args.cleanup:
            print("\n===== Cleaning Up =====")
            cleanup_detection()

if __name__ == "__main__":
    main() 