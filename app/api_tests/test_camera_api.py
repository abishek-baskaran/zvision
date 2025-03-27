#!/usr/bin/env python3
"""
API Test script for Camera functionality

This script tests the camera API endpoints in the ZVision system.
It validates adding, controlling and removing cameras via the API.
"""

import argparse
import os
import sys
import time
import json
import requests
from typing import Dict, Any, Optional, List

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# API base URL
BASE_URL = "http://localhost:8000/api"

def test_add_camera(camera_id: int = 1, source: str = "/dev/video0", 
                   enable_detection: bool = False) -> Dict[str, Any]:
    """
    Test adding a camera via the API
    
    Args:
        camera_id: ID for the camera (integer)
        source: Camera source (device, file, or URL)
        enable_detection: Whether to enable detection
        
    Returns:
        API response as dictionary
    """
    print(f"Adding camera {camera_id} with source {source}")
    
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

def test_camera_status(camera_id: int = 1) -> Dict[str, Any]:
    """
    Test getting camera status via the API
    
    Args:
        camera_id: ID of the camera to check
        
    Returns:
        Camera status as dictionary
    """
    print(f"Checking status of camera {camera_id}")
    
    url = f"{BASE_URL}/camera/{camera_id}/status"
    response = requests.get(url)
    
    if response.status_code == 200:
        status = response.json()
        print(f"Camera {camera_id} status: {json.dumps(status, indent=2)}")
        return status
    else:
        print(f"Failed to get camera status: {response.status_code}, {response.text}")
        return {"error": response.text}

def test_camera_list() -> List[Dict[str, Any]]:
    """
    Test listing all cameras via the API
    
    Returns:
        List of camera information
    """
    print("Getting list of all cameras")
    
    url = f"{BASE_URL}/camera/list"
    response = requests.get(url)
    
    if response.status_code == 200:
        cameras = response.json()
        print(f"Found {len(cameras)} cameras:")
        for camera in cameras:
            print(f"  Camera {camera.get('camera_id')}: {camera.get('status', 'unknown')}")
        return cameras
    else:
        print(f"Failed to get camera list: {response.status_code}, {response.text}")
        return [{"error": response.text}]

def test_enable_detection(camera_id: int = 1) -> Dict[str, Any]:
    """
    Test enabling detection for a camera via the API
    
    Args:
        camera_id: ID of the camera
        
    Returns:
        API response as dictionary
    """
    print(f"Enabling detection for camera {camera_id}")
    
    url = f"{BASE_URL}/camera/{camera_id}/enable_detection"
    response = requests.get(url)
    
    if response.status_code == 200:
        result = response.json()
        print(f"Successfully enabled detection for camera {camera_id}")
        return result
    else:
        print(f"Failed to enable detection: {response.status_code}, {response.text}")
        return {"error": response.text}

def test_disable_detection(camera_id: int = 1) -> Dict[str, Any]:
    """
    Test disabling detection for a camera via the API
    
    Args:
        camera_id: ID of the camera
        
    Returns:
        API response as dictionary
    """
    print(f"Disabling detection for camera {camera_id}")
    
    url = f"{BASE_URL}/camera/{camera_id}/disable_detection"
    response = requests.get(url)
    
    if response.status_code == 200:
        result = response.json()
        print(f"Successfully disabled detection for camera {camera_id}")
        return result
    else:
        print(f"Failed to disable detection: {response.status_code}, {response.text}")
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

def wait_for_camera_status(camera_id: int, target_status: str = "running", 
                          max_wait: int = 30) -> bool:
    """
    Wait for a camera to reach a specific status
    
    Args:
        camera_id: ID of the camera
        target_status: Target status to wait for
        max_wait: Maximum wait time in seconds
        
    Returns:
        True if target status was reached, False if timed out
    """
    print(f"Waiting for camera {camera_id} to reach status '{target_status}'")
    
    start_time = time.time()
    while time.time() - start_time < max_wait:
        status = test_camera_status(camera_id)
        current_status = status.get("status", "unknown")
        
        print(f"Camera status: {current_status}")
        
        if current_status == target_status:
            print(f"Camera {camera_id} reached status '{target_status}'")
            return True
        
        time.sleep(1)
    
    print(f"Timeout: Camera {camera_id} did not reach status '{target_status}' within {max_wait} seconds")
    return False

def cleanup_cameras():
    """
    Clean up by removing all cameras
    
    Returns:
        True if successful, False otherwise
    """
    print("\nCleaning up cameras...")
    
    try:
        # Get list of all cameras
        cameras = test_camera_list()
        
        if isinstance(cameras, list):
            print(f"Found {len(cameras)} cameras to clean up")
            
            # Remove each camera by replacing it with a dummy
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
                
                print(f"Removing camera {camera_id}")
                
                # First disable detection if enabled
                try:
                    test_disable_detection(camera_id)
                except Exception as e:
                    print(f"Failed to disable detection for camera {camera_id}: {e}")
                
                # Replace with dummy camera to remove
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
                        print(f"Failed to remove camera {camera_id}: {response.status_code}, {response.text}")
                except Exception as e:
                    print(f"Error removing camera {camera_id}: {e}")
            
            print("Camera cleanup completed")
            return True
        else:
            print(f"Failed to get camera list for cleanup: {cameras}")
            return False
    
    except Exception as e:
        print(f"Error during camera cleanup: {e}")
        return False

def main():
    """
    Main function to run camera API tests
    """
    parser = argparse.ArgumentParser(description="Test Camera API endpoints")
    parser.add_argument("--source", type=str, default="/dev/video0", 
                       help="Camera source (device, file, or URL)")
    parser.add_argument("--id", type=int, default=1, 
                       help="Camera ID to use for testing")
    parser.add_argument("--with-detection", action="store_true", 
                       help="Enable detection testing")
    parser.add_argument("--full-test", action="store_true", 
                       help="Run a full test cycle (add, status, detection, removal)")
    parser.add_argument("--cleanup", action="store_true",
                       help="Clean up all cameras after test")
    args = parser.parse_args()
    
    # Convert source to int if it's a digit
    source = args.source
    if source.isdigit():
        source = int(source)
    
    try:
        if args.full_test:
            print("\n===== Running full camera API test =====\n")
            
            # Step 1: Add camera
            result = test_add_camera(args.id, source, args.with_detection)
            
            # Step 2: Wait for camera to start
            wait_for_camera_status(args.id, "running", 30)
            
            # Step 3: Get status
            camera_status = test_camera_status(args.id)
            
            # Step 4: List all cameras
            cameras = test_camera_list()
            
            # Step 5: Test detection (if requested)
            if args.with_detection:
                detection_status = test_detection_status(args.id)
                
                # Toggle detection
                disable_result = test_disable_detection(args.id)
                time.sleep(2)
                enable_result = test_enable_detection(args.id)
                time.sleep(2)
                
                # Get updated detection status
                detection_status = test_detection_status(args.id)
            
            print("\n===== Camera API Test Results =====\n")
            print(f"Camera {args.id} with source {source}:")
            print(f"Status: {camera_status.get('status', 'unknown')}")
            print(f"Running: {camera_status.get('running', False)}")
            print(f"FPS: {camera_status.get('fps', 0)}")
            
            if args.with_detection:
                print(f"Detection Enabled: {detection_status.get('detection_enabled', False)}")
                detection_details = detection_status.get('detection_status', {})
                print(f"Detection Status: {detection_details.get('status', 'unknown')}")
            
            print("\nTest completed successfully!")
        
        else:
            # Run individual tests based on arguments
            if args.with_detection:
                # Test with detection
                result = test_add_camera(args.id, source, True)
                time.sleep(2)
                camera_status = test_camera_status(args.id)
                detection_status = test_detection_status(args.id)
            else:
                # Test without detection
                result = test_add_camera(args.id, source, False)
                time.sleep(2)
                camera_status = test_camera_status(args.id)
                
            print("\nTest completed!")
    
    except Exception as e:
        print(f"\nError during test: {e}")
    
    finally:
        # Clean up if requested
        if args.cleanup:
            print("\n===== Cleaning Up =====")
            cleanup_cameras()

if __name__ == "__main__":
    main() 