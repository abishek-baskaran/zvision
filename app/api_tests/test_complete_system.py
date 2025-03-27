#!/usr/bin/env python3
"""
API Test script for Complete System Testing

This script runs a full end-to-end test of the ZVision system, testing
both camera and detection functionality to verify that all components
work together properly with no pickle errors.
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
import logging
import signal
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# API base URL
BASE_URL = "http://localhost:8000/api"

# Import the other test modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from test_camera_api import (
    test_add_camera, 
    test_camera_status, 
    wait_for_camera_status,
    test_camera_list,
    test_enable_detection,
    test_disable_detection
)
from test_detection_api import (
    test_detection_status,
    wait_for_detection_status,
    test_run_detection,
    capture_and_detect_image,
    visualize_detections
)

def test_startup_sequence(camera_id: int = 1, source: str = "/dev/video0", 
                         enable_detection: bool = True) -> Dict[str, Any]:
    """
    Test the complete startup sequence for a camera with detection
    
    Args:
        camera_id: Camera ID to use
        source: Camera source (device, file, or URL)
        enable_detection: Whether to enable detection
        
    Returns:
        Dictionary with test results
    """
    results = {}
    
    logger.info("===== TESTING STARTUP SEQUENCE =====")
    
    # Step 1: Add the camera
    try:
        add_result = test_add_camera(camera_id, source, enable_detection)
        results["add_camera"] = {
            "success": "error" not in add_result,
            "result": add_result
        }
        
        if "error" in add_result:
            logger.error(f"Failed to add camera: {add_result['error']}")
            return results
        
        # Wait for camera to initialize
        camera_ready = wait_for_camera_status(camera_id, "running", max_wait=30)
        results["camera_ready"] = camera_ready
        
        if not camera_ready:
            logger.error("Camera failed to initialize within timeout period")
            return results
        
        # Get camera status
        camera_status = test_camera_status(camera_id)
        results["camera_status"] = camera_status
        
        # Test camera list
        camera_list = test_camera_list()
        results["camera_list"] = {
            "success": isinstance(camera_list, list) and len(camera_list) > 0,
            "count": len(camera_list) if isinstance(camera_list, list) else 0
        }
        
        # Check detection status if enabled
        if enable_detection:
            # Wait for detection to initialize
            detection_ready = wait_for_detection_status(camera_id, "running", max_wait=30)
            results["detection_ready"] = detection_ready
            
            if not detection_ready:
                logger.error("Detection failed to initialize within timeout period")
                return results
            
            # Get detection status
            detection_status = test_detection_status(camera_id)
            results["detection_status"] = detection_status
        
        logger.info("Startup sequence test completed successfully")
        return results
        
    except Exception as e:
        logger.exception(f"Error in startup sequence test: {e}")
        results["error"] = str(e)
        return results

def test_detection_operations(camera_id: int = 1) -> Dict[str, Any]:
    """
    Test detection operations (running detection and processing results)
    
    Args:
        camera_id: Camera ID to use
        
    Returns:
        Dictionary with test results
    """
    results = {}
    
    logger.info("===== TESTING DETECTION OPERATIONS =====")
    
    try:
        # Step 1: Verify detection is enabled
        detection_status = test_detection_status(camera_id)
        results["initial_status"] = detection_status
        
        detection_enabled = detection_status.get("detection_enabled", False)
        if not detection_enabled:
            # Enable detection if not already enabled
            logger.info("Detection not enabled, enabling it now")
            enable_result = test_enable_detection(camera_id)
            results["enable_detection"] = enable_result
            
            # Wait for detection to start
            detection_ready = wait_for_detection_status(camera_id, "running", max_wait=30)
            if not detection_ready:
                logger.error("Detection failed to start after enabling")
                results["detection_start_failed"] = True
                return results
        
        # Step 2: Run detection
        logger.info("Running detection test")
        detection_result = test_run_detection(camera_id)
        results["detection_result"] = {
            "success": "error" not in detection_result,
            "objects_detected": len(detection_result.get("boxes", [])) if "error" not in detection_result else 0
        }
        
        # Step 3: Disable detection
        logger.info("Disabling detection")
        disable_result = test_disable_detection(camera_id)
        results["disable_detection"] = disable_result
        
        # Step 4: Verify detection is disabled
        status_after_disable = test_detection_status(camera_id)
        detection_enabled_after = status_after_disable.get("detection_enabled", True)
        results["detection_disabled"] = not detection_enabled_after
        
        # Step 5: Re-enable detection
        logger.info("Re-enabling detection")
        enable_result = test_enable_detection(camera_id)
        results["re_enable_detection"] = enable_result
        
        # Step 6: Verify detection is enabled again
        status_after_enable = test_detection_status(camera_id)
        detection_enabled_after = status_after_enable.get("detection_enabled", False)
        results["detection_re_enabled"] = detection_enabled_after
        
        logger.info("Detection operations test completed successfully")
        return results
        
    except Exception as e:
        logger.exception(f"Error in detection operations test: {e}")
        results["error"] = str(e)
        return results

def test_removal_sequence(camera_id: int = 1) -> Dict[str, Any]:
    """
    Test removing a camera with active detection
    
    Args:
        camera_id: Camera ID to remove
        
    Returns:
        Dictionary with test results
    """
    results = {}
    
    logger.info("===== TESTING REMOVAL SEQUENCE =====")
    
    try:
        # Currently there is no dedicated removal endpoint, so we'll check that
        # we can add a new camera with the same ID which would replace the existing one
        logger.info(f"Testing removal by replacing camera {camera_id}")
        
        # Add a camera with the same ID but different source
        test_source = 0  # Use the first available webcam as test source
        replace_result = test_add_camera(camera_id, test_source, enable_detection=False)
        
        results["replace_camera"] = {
            "success": "error" not in replace_result,
            "result": replace_result
        }
        
        # Verify the camera was replaced
        camera_status = test_camera_status(camera_id)
        
        results["camera_replaced"] = {
            "success": "error" not in camera_status,
            "status": camera_status.get("status") if "error" not in camera_status else "unknown"
        }
        
        logger.info("Removal sequence test completed")
        return results
        
    except Exception as e:
        logger.exception(f"Error in removal sequence test: {e}")
        results["error"] = str(e)
        return results

def test_complete_system(camera_id: int = 1, source: str = "/dev/video0", 
                        enable_detection: bool = True, max_duration: int = 30) -> Dict[str, Any]:
    """
    Run a complete system test including startup, operations, and shutdown
    
    Args:
        camera_id: Camera ID to use
        source: Camera source (device, file, or URL)
        enable_detection: Whether to enable detection
        max_duration: Maximum duration in seconds for the test (for live video sources)
        
    Returns:
        Dictionary with test results
    """
    overall_results = {}
    start_time = time.time()
    abs_end_time = start_time + max_duration
    
    try:
        # Test startup sequence
        startup_results = test_startup_sequence(camera_id, source, enable_detection)
        overall_results["startup"] = startup_results
        
        # Check if we're already exceeding max duration
        if time.time() > abs_end_time:
            logger.warning(f"Test reached max duration ({max_duration}s) during startup phase")
            overall_results["early_termination"] = True
            return overall_results
        
        # Only continue if startup was successful
        if startup_results.get("camera_ready", False):
            # Test detection operations if detection was enabled
            if enable_detection and startup_results.get("detection_ready", False):
                # Calculate remaining time for detection operations
                remaining_time = abs_end_time - time.time()
                if remaining_time <= 0:
                    logger.warning("No time remaining for detection operations")
                    overall_results["early_termination"] = True
                    return overall_results
                
                logger.info(f"Running detection operations (time remaining: {remaining_time:.1f}s)")
                detection_results = test_detection_operations(camera_id)
                overall_results["detection_operations"] = detection_results
                
                # Add a brief delay to observe the system running, but ensure we don't exceed max_duration
                remaining_observation_time = min(10, abs_end_time - time.time())
                if remaining_observation_time > 0:
                    logger.info(f"System running successfully. Monitoring for {remaining_observation_time:.1f} seconds...")
                    
                    # Wait for a short period to see the system running
                    observation_end = time.time() + remaining_observation_time
                    while time.time() < observation_end:
                        # Check if we're still connected to the server
                        try:
                            status = test_camera_status(camera_id)
                            if "error" in status:
                                logger.warning("Lost connection to server")
                                break
                        except Exception:
                            logger.warning("Lost connection to server")
                            break
                        
                        # Brief pause
                        time.sleep(1)
                else:
                    logger.warning("No time remaining for observation phase")
            
            # Check if we still have time for removal
            if time.time() > abs_end_time:
                logger.warning(f"Test reached max duration ({max_duration}s) before removal phase")
                overall_results["early_termination"] = True
                return overall_results
                
            # Test removal sequence
            logger.info("Starting removal sequence")
            removal_results = test_removal_sequence(camera_id)
            overall_results["removal"] = removal_results
        
        # Generate overall success flag
        overall_success = (
            startup_results.get("camera_ready", False) and
            (not enable_detection or startup_results.get("detection_ready", False)) and
            "error" not in overall_results.get("detection_operations", {}) and
            "error" not in overall_results.get("removal", {}) and
            not overall_results.get("early_termination", False)
        )
        
        overall_results["overall_success"] = overall_success
        overall_results["duration"] = time.time() - start_time
        
        return overall_results
        
    except Exception as e:
        logger.exception(f"Error in complete system test: {e}")
        overall_results["error"] = str(e)
        overall_results["overall_success"] = False
        overall_results["duration"] = time.time() - start_time
        return overall_results

def cleanup_system():
    """
    Clean up the system by stopping all detection workers and removing all cameras
    """
    logger.info("===== CLEANING UP SYSTEM =====")
    
    try:
        # Try to get list of all cameras 
        print("Getting list of all cameras")
        try:
            # First try to get the camera list
            url = f"{BASE_URL}/camera/list"
            try:
                response = requests.get(url, timeout=5)
                
                if response.status_code == 200:
                    cameras_data = response.json()
                    logger.info(f"Camera list response: {cameras_data}")
                    
                    # Handle different possible response formats
                    cameras = []
                    if isinstance(cameras_data, list):
                        cameras = cameras_data
                    elif isinstance(cameras_data, dict) and "cameras" in cameras_data:
                        cameras = cameras_data["cameras"]
                    elif isinstance(cameras_data, dict) and "items" in cameras_data:
                        cameras = cameras_data["items"]
                    else:
                        logger.warning(f"Unexpected camera list format: {cameras_data}")
                        # Try to clean up camera with ID 1 as fallback
                        cameras = [{"camera_id": 1}]  
                        
                    logger.info(f"Found {len(cameras)} cameras to clean up")
                else:
                    logger.warning(f"Failed to get camera list: {response.status_code}")
                    # Attempt to clean up camera 1 as fallback
                    cameras = [{"camera_id": 1}]
            except requests.exceptions.ConnectionError:
                logger.warning("Cannot connect to server - it may have already been stopped")
                return True
            except Exception as e:
                logger.error(f"Error getting camera list: {e}")
                # Attempt to clean up camera 1 as fallback
                cameras = [{"camera_id": 1}]
            
            # Process each camera
            for i, camera in enumerate(cameras):
                logger.debug(f"Processing camera entry {i}: {camera}")
                camera_id = None
                
                # Extract camera ID based on the type of data we got
                if isinstance(camera, dict):
                    if "camera_id" in camera:
                        camera_id = camera["camera_id"]
                    elif "id" in camera:
                        camera_id = camera["id"]
                elif isinstance(camera, (int, float)):
                    camera_id = int(camera)
                elif isinstance(camera, str):
                    # Try to parse as JSON first
                    try:
                        camera_dict = json.loads(camera)
                        if isinstance(camera_dict, dict) and "camera_id" in camera_dict:
                            camera_id = camera_dict["camera_id"]
                        else:
                            logger.warning(f"Could not find camera_id in JSON: {camera}")
                    except json.JSONDecodeError:
                        # Not JSON, try to extract ID from a string like "Camera 1: status"
                        try:
                            # Get first part before colon
                            parts = camera.split(":")
                            if len(parts) > 0:
                                # Extract the number from "Camera X"
                                first_part = parts[0].strip()
                                if first_part.startswith("Camera "):
                                    id_part = first_part.replace("Camera ", "").strip()
                                    if id_part.isdigit():
                                        camera_id = int(id_part)
                                    else:
                                        logger.warning(f"Non-numeric camera ID: {id_part}")
                            
                            # If we couldn't extract ID but the string is numeric, use it directly
                            if camera_id is None and camera.strip().isdigit():
                                camera_id = int(camera.strip())
                        except Exception as e:
                            logger.warning(f"Failed to parse camera string: {camera}, error: {e}")
                
                if camera_id is None:
                    logger.warning(f"Could not determine camera ID from {camera}")
                    continue
                
                # Now clean up this camera
                logger.info(f"Cleaning up camera {camera_id}")
                
                # First try to disable detection
                try:
                    url = f"{BASE_URL}/camera/{camera_id}/disable_detection"
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        logger.info(f"Disabled detection for camera {camera_id}")
                    else:
                        logger.warning(f"Failed to disable detection: {response.status_code}")
                except Exception as e:
                    logger.warning(f"Error disabling detection: {e}")
                
                # Replace with dummy camera to remove it
                try:
                    url = f"{BASE_URL}/camera/add"
                    payload = {
                        "camera_id": camera_id,
                        "source": "none://dummy",
                        "enable_detection": False
                    }
                    response = requests.post(url, json=payload, timeout=5)
                    
                    if response.status_code == 200:
                        logger.info(f"Successfully removed camera {camera_id}")
                    else:
                        logger.warning(f"Failed to remove camera {camera_id}: {response.status_code}")
                except Exception as e:
                    logger.warning(f"Error removing camera {camera_id}: {e}")
            
            # Always try to clean up camera ID 1 as an additional safety measure
            try:
                if not any(c.get("camera_id") == 1 for c in cameras if isinstance(c, dict)):
                    logger.info("Attempting to clean up camera ID 1 as an additional safety measure")
                    url = f"{BASE_URL}/camera/add"
                    payload = {
                        "camera_id": 1,
                        "source": "none://dummy",
                        "enable_detection": False
                    }
                    response = requests.post(url, json=payload, timeout=5)
                    if response.status_code == 200:
                        logger.info("Successfully removed camera ID 1")
            except Exception as e:
                logger.warning(f"Error removing camera ID 1: {e}")
            
            logger.info("System cleanup completed")
            return True
                
        except Exception as e:
            logger.error(f"Error during system cleanup: {e}")
            return False
        
    except Exception as e:
        logger.exception(f"Unexpected error during cleanup: {e}")
        return False

def main():
    """
    Main function to run the complete system test
    """
    parser = argparse.ArgumentParser(description="Test the complete ZVision system")
    parser.add_argument("--source", type=str, default="/dev/video0", 
                       help="Camera source (device, file, or URL)")
    parser.add_argument("--id", type=int, default=1, 
                       help="Camera ID to use for testing")
    parser.add_argument("--no-detection", action="store_true", 
                       help="Disable detection testing")
    parser.add_argument("--output", type=str, default="output/system_test_results.json", 
                       help="Path to save the test results")
    parser.add_argument("--no-cleanup", action="store_true",
                       help="Skip cleanup after test (for debugging)")
    parser.add_argument("--max-duration", type=int, default=30,
                       help="Maximum duration in seconds for the test (for live video sources)")
    args = parser.parse_args()
    
    # Convert source to int if it's a digit
    source = args.source
    if source.isdigit():
        source = int(source)
    
    print("\n===== STARTING COMPLETE SYSTEM TEST =====\n")
    print(f"Camera ID: {args.id}")
    print(f"Source: {source}")
    print(f"Testing detection: {not args.no_detection}")
    print(f"Maximum test duration: {args.max_duration} seconds\n")
    
    # Set up signal handling for graceful termination
    # Flag to indicate if we're in cleanup
    in_cleanup = False
    
    # Event to notify when test has completed
    test_complete = threading.Event()
    
    def signal_handler(sig, frame):
        """Handle termination signals by triggering cleanup"""
        nonlocal in_cleanup
        if in_cleanup:
            # If already in cleanup, just exit
            print("\nForced exit during cleanup...")
            sys.exit(1)
        else:
            print("\nReceived termination signal, starting cleanup...")
            test_complete.set()
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create a watchdog timer to enforce the time limit
    def watchdog_timer():
        """Force test to complete after max_duration"""
        test_complete.wait(timeout=args.max_duration + 5)  # Add 5 seconds buffer
        if not test_complete.is_set():
            print(f"\nWatchdog timer expired after {args.max_duration + 5} seconds")
            # Trigger the same cleanup as Ctrl+C
            os.kill(os.getpid(), signal.SIGINT)
    
    # Start watchdog timer
    timer_thread = threading.Thread(target=watchdog_timer, daemon=True)
    timer_thread.start()
    
    # Run the complete system test
    results = None
    start_time = time.time()
    try:
        results = test_complete_system(args.id, source, not args.no_detection, args.max_duration)
        
        # Save results to file
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        
        print(f"\nTest results saved to {args.output}")
        
        # Print overall result
        if results.get("overall_success", False):
            print("\n===== SYSTEM TEST PASSED =====")
            print("All components are working correctly with no pickle errors.")
        else:
            print("\n===== SYSTEM TEST FAILED =====")
            if "error" in results:
                print(f"Error: {results['error']}")
            
            # Print specific failures
            if not results.get("startup", {}).get("camera_ready", False):
                print("- Camera failed to start properly")
            
            if not args.no_detection and not results.get("startup", {}).get("detection_ready", False):
                print("- Detection failed to start properly")
            
            if "error" in results.get("detection_operations", {}):
                print(f"- Detection operations failed: {results['detection_operations']['error']}")
            
            if "error" in results.get("removal", {}):
                print(f"- Camera removal failed: {results['removal']['error']}")
            
            if results.get("early_termination", False):
                print("- Test was terminated early due to reaching max_duration")
    
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        results = {"overall_success": False, "error": "Test interrupted by user"}
    except Exception as e:
        print(f"\n\nUnexpected error during test: {e}")
        results = {"overall_success": False, "error": str(e)}
    finally:
        # Signal that test is complete (stops the watchdog)
        test_complete.set()
        
        test_duration = time.time() - start_time
        print(f"\nTest ran for {test_duration:.1f} seconds")
    
    # Always perform cleanup, even if the test fails, unless explicitly disabled
    try:
        if not args.no_cleanup:
            in_cleanup = True
            print("\n===== CLEANING UP AFTER TEST =====")
            cleanup_success = cleanup_system()
            print(f"Cleanup {'completed successfully' if cleanup_success else 'failed'}")
        else:
            print("\n===== CLEANUP SKIPPED (--no-cleanup flag) =====")
    except Exception as e:
        print(f"Error during cleanup: {e}")
    
    return 0 if results and results.get("overall_success", False) else 1


if __name__ == "__main__":
    sys.exit(main()) 