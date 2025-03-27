#!/usr/bin/env python3
"""
Test script for multiple camera streams with detection

This script tests the system's ability to handle multiple camera streams simultaneously,
with each stream having its own detection worker. It verifies resource isolation,
performance metrics, and proper cleanup of resources.
"""

import argparse
import os
import sys
import time
import json
import signal
import threading
import requests
from typing import Dict, List, Any, Optional
import psutil

# Add parent directory to path to import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.analytics import analytics
from app.camera_manager import camera_manager
from app.detection_worker import detection_manager


def monitor_resources(duration: int = 30, interval: float = 2.0):
    """
    Monitor system resources during test
    
    Args:
        duration: Duration to monitor in seconds
        interval: Sampling interval in seconds
    """
    print("\n=== Resource Monitoring ===")
    start_time = time.time()
    end_time = start_time + duration
    
    # Track peak usage
    peak_cpu = 0
    peak_memory = 0
    peak_memory_percent = 0
    
    while time.time() < end_time:
        # Get CPU and memory usage
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        memory_used_mb = memory.used / (1024 * 1024)
        memory_percent = memory.percent
        
        # Update peak values
        peak_cpu = max(peak_cpu, cpu_percent)
        peak_memory = max(peak_memory, memory_used_mb)
        peak_memory_percent = max(peak_memory_percent, memory_percent)
        
        # Print current usage
        elapsed = time.time() - start_time
        print(f"[{elapsed:.1f}s] CPU: {cpu_percent:.1f}% | Memory: {memory_used_mb:.1f}MB ({memory_percent:.1f}%)")
        
        # Sleep for the interval
        time.sleep(interval)
    
    # Print summary
    print("\n=== Resource Usage Summary ===")
    print(f"Peak CPU: {peak_cpu:.1f}%")
    print(f"Peak Memory: {peak_memory:.1f}MB ({peak_memory_percent:.1f}%)")


def test_camera_stream(camera_id: int, source: str, duration: int = 30, detection: bool = True):
    """
    Test a single camera stream with or without detection
    
    Args:
        camera_id: Camera ID to use
        source: Camera source (file path, device index, or URL)
        duration: Duration to run the test in seconds
        detection: Whether to enable detection
    """
    print(f"\n=== Testing Camera {camera_id} (Source: {source}) ===")
    print(f"Detection enabled: {detection}")
    
    # Start camera
    camera = camera_manager.get_camera(camera_id, source, enable_detection=detection)
    
    if not camera:
        print(f"Failed to start camera {camera_id}")
        return
    
    print(f"Camera {camera_id} started successfully")
    
    # Monitor for the specified duration
    start_time = time.time()
    end_time = start_time + duration
    
    while time.time() < end_time:
        # Get camera status
        camera_status = camera_manager.get_camera_status(camera_id)
        
        if camera_status:
            status = camera_status.get('status', 'unknown')
            fps = camera_status.get('fps', 0)
            print(f"Camera {camera_id} status: {status} | FPS: {fps:.2f}")
            
            # Get detection status if enabled
            if detection:
                detection_status = detection_manager.get_worker_status(camera_id)
                if detection_status:
                    det_status = detection_status.get('status', 'unknown')
                    det_fps = detection_status.get('fps', 0)
                    det_count = detection_status.get('detection_count', 0)
                    print(f"Detection {camera_id} status: {det_status} | FPS: {det_fps:.2f} | Count: {det_count}")
        
        # Get a frame to verify stream is working
        frame = camera_manager.get_frame(camera_id, source)
        if frame is not None:
            height, width = frame.shape[:2]
            print(f"Frame received: {width}x{height}")
        else:
            print("No frame available")
        
        # Sleep for a bit
        time.sleep(5)
    
    # Release camera
    camera_manager.release_camera(camera_id)
    print(f"Camera {camera_id} released")


def test_multiple_cameras(sources: List[str], duration: int = 30, detection: bool = True):
    """
    Test multiple camera streams simultaneously
    
    Args:
        sources: List of camera sources
        duration: Duration to run the test in seconds
        detection: Whether to enable detection
    """
    print(f"\n=== Testing {len(sources)} Camera Streams Simultaneously ===")
    print(f"Sources: {sources}")
    print(f"Detection enabled: {detection}")
    
    # Start resource monitoring in a separate thread
    resource_thread = threading.Thread(target=monitor_resources, args=(duration, 2.0))
    resource_thread.daemon = True
    resource_thread.start()
    
    # Start all cameras
    camera_ids = []
    for i, source in enumerate(sources):
        camera_id = i + 1  # Start from 1
        camera = camera_manager.get_camera(camera_id, source, enable_detection=detection)
        if camera:
            camera_ids.append(camera_id)
            print(f"Camera {camera_id} (Source: {source}) started successfully")
        else:
            print(f"Failed to start camera {camera_id} (Source: {source})")
    
    if not camera_ids:
        print("No cameras were started successfully")
        return
    
    print(f"Started {len(camera_ids)} cameras")
    
    # Monitor for the specified duration
    start_time = time.time()
    end_time = start_time + duration
    
    while time.time() < end_time:
        # Check status for each camera
        for camera_id in camera_ids:
            camera_status = camera_manager.get_camera_status(camera_id)
            
            if camera_status:
                status = camera_status.get('status', 'unknown')
                fps = camera_status.get('fps', 0)
                print(f"Camera {camera_id} status: {status} | FPS: {fps:.2f}")
                
                # Get detection status if enabled
                if detection:
                    detection_status = detection_manager.get_worker_status(camera_id)
                    if detection_status:
                        det_status = detection_status.get('status', 'unknown')
                        det_fps = detection_status.get('fps', 0)
                        det_count = detection_status.get('detection_count', 0)
                        print(f"Detection {camera_id} status: {det_status} | FPS: {det_fps:.2f} | Count: {det_count}")
        
        # Get metrics for all cameras
        print("\n--- Metrics ---")
        all_metrics = analytics.get_all_metrics()
        for camera_id, metrics in all_metrics.items():
            print(f"Camera {camera_id} metrics:")
            print(f"  Status: {metrics.get('status')}")
            print(f"  FPS: {metrics.get('fps')}")
            detection_counts = metrics.get('detection_counts', {}).get('total', {})
            print(f"  Detection counts: {detection_counts}")
        
        print("\n")
        # Sleep for a bit
        time.sleep(5)
    
    # Release all cameras
    for camera_id in camera_ids:
        camera_manager.release_camera(camera_id)
        print(f"Camera {camera_id} released")
    
    # Wait for resource monitoring thread to finish
    if resource_thread.is_alive():
        resource_thread.join(timeout=2)


def test_cleanup():
    """Test proper cleanup of resources"""
    print("\n=== Testing Resource Cleanup ===")
    
    # Start multiple cameras
    sources = ["0", "test_video.mp4"]  # Use webcam and test video file
    camera_ids = []
    
    for i, source in enumerate(sources):
        try:
            camera_id = i + 1
            camera = camera_manager.get_camera(camera_id, source, enable_detection=True)
            if camera:
                camera_ids.append(camera_id)
                print(f"Started camera {camera_id} with source {source}")
        except Exception as e:
            print(f"Error starting camera {i+1}: {e}")
    
    # Let them run briefly
    time.sleep(5)
    
    # Check processes before cleanup
    processes_before = len(psutil.Process().children(recursive=True))
    print(f"Child processes before cleanup: {processes_before}")
    
    # Release all cameras
    for camera_id in camera_ids:
        try:
            camera_manager.release_camera(camera_id)
            print(f"Released camera {camera_id}")
        except Exception as e:
            print(f"Error releasing camera {camera_id}: {e}")
    
    # Wait a moment for processes to terminate
    time.sleep(2)
    
    # Check processes after cleanup
    processes_after = len(psutil.Process().children(recursive=True))
    print(f"Child processes after cleanup: {processes_after}")
    print(f"Processes terminated: {processes_before - processes_after}")
    
    # Verify all expected processes were terminated
    if processes_after < processes_before:
        print("✅ Resource cleanup successful")
    else:
        print("❌ Resource cleanup may have issues")
        
        # List remaining processes
        print("Remaining processes:")
        for proc in psutil.Process().children(recursive=True):
            print(f"  PID {proc.pid}: {proc.name()} | CMD: {' '.join(proc.cmdline())}")


def test_api_integration(base_url: str, token: Optional[str] = None):
    """
    Test API integration with cameras and detection
    
    Args:
        base_url: Base URL for the API (e.g., http://localhost:8000)
        token: JWT token for authentication (if needed)
    """
    print(f"\n=== Testing API Integration at {base_url} ===")
    
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    # Start a camera for testing
    camera_id = 1
    camera = camera_manager.get_camera(camera_id, "0", enable_detection=True)
    print(f"Started camera {camera_id} for API testing")
    
    try:
        # Wait for some detections to occur
        time.sleep(10)
        
        # Test camera snapshot endpoint
        try:
            response = requests.get(f"{base_url}/api/camera/{camera_id}/snapshot", headers=headers)
            if response.status_code == 200:
                print(f"Camera snapshot API: ✅ (Status: {response.status_code})")
                # Save the snapshot
                with open(f"camera_{camera_id}_snapshot.jpg", "wb") as f:
                    f.write(response.content)
                print(f"Saved snapshot to camera_{camera_id}_snapshot.jpg")
            else:
                print(f"Camera snapshot API: ❌ (Status: {response.status_code})")
        except Exception as e:
            print(f"Error testing camera snapshot API: {e}")
        
        # Test detection endpoint
        try:
            response = requests.get(f"{base_url}/api/detect", headers=headers)
            if response.status_code == 200:
                data = response.json()
                print(f"Detection API: ✅ (Status: {response.status_code})")
                print(f"Detection results: {json.dumps(data, indent=2)}")
            else:
                print(f"Detection API: ❌ (Status: {response.status_code})")
        except Exception as e:
            print(f"Error testing detection API: {e}")
        
        # Test metrics endpoint
        try:
            response = requests.get(f"{base_url}/api/metrics", headers=headers)
            if response.status_code == 200:
                data = response.json()
                print(f"Metrics API: ✅ (Status: {response.status_code})")
                print(f"Metrics data: {json.dumps(data, indent=2)}")
            else:
                print(f"Metrics API: ❌ (Status: {response.status_code})")
        except Exception as e:
            print(f"Error testing metrics API: {e}")
    
    finally:
        # Clean up
        camera_manager.release_camera(camera_id)
        print(f"Released camera {camera_id}")


def main():
    parser = argparse.ArgumentParser(description="Test multiple camera streams with detection")
    parser.add_argument("--single", action="store_true", help="Test single camera stream")
    parser.add_argument("--multi", action="store_true", help="Test multiple camera streams")
    parser.add_argument("--cleanup", action="store_true", help="Test resource cleanup")
    parser.add_argument("--api", action="store_true", help="Test API integration")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    
    parser.add_argument("--sources", type=str, nargs="+", default=["0"], help="Camera sources (device indices, files, or URLs)")
    parser.add_argument("--duration", type=int, default=30, help="Test duration in seconds")
    parser.add_argument("--no-detection", action="store_true", help="Disable detection")
    
    parser.add_argument("--base-url", type=str, default="http://localhost:8000", help="Base URL for API tests")
    parser.add_argument("--token", type=str, help="JWT token for API authentication")
    
    args = parser.parse_args()
    
    # Create test video if it doesn't exist
    test_video = "test_video.mp4"
    if not os.path.exists(test_video):
        try:
            from app.tests.create_test_video import create_test_video
            create_test_video(test_video)
            print(f"Created test video file: {test_video}")
        except Exception as e:
            print(f"Note: Could not create test video ({e}). Using camera indices only.")
    
    # Run selected tests
    if args.single or args.all:
        source = args.sources[0] if args.sources else "0"
        test_camera_stream(1, source, args.duration, not args.no_detection)
    
    if args.multi or args.all:
        test_multiple_cameras(args.sources, args.duration, not args.no_detection)
    
    if args.cleanup or args.all:
        test_cleanup()
    
    if args.api or args.all:
        test_api_integration(args.base_url, args.token)
    
    # If no test was selected, show help
    if not (args.single or args.multi or args.cleanup or args.api or args.all):
        parser.print_help()


if __name__ == "__main__":
    # Setup signal handler for graceful exit
    def signal_handler(sig, frame):
        print("\nExiting test script and cleaning up...")
        # Release all cameras
        cameras = list(camera_manager.cameras.keys())
        for camera_id in cameras:
            camera_manager.release_camera(camera_id)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    main() 