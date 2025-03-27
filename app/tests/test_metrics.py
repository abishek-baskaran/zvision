#!/usr/bin/env python3
"""
Test script for metrics collection and API

This script tests the metrics collection by creating a test camera and detection worker,
running them for a short period, and then retrieving metrics from the API endpoints.
"""

import argparse
import os
import sys
import time
import requests
import json
from typing import Dict, Any, Optional

# Add parent directory to path to import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.analytics import analytics
from app.camera_manager import camera_manager
from app.detection_worker import detection_manager


def test_direct_metrics():
    """Test direct access to metrics through the analytics module"""
    print("\n=== Testing Direct Metrics Access ===")
    
    # Get metrics for camera 1 (if available)
    metrics = analytics.get_metrics(1)
    print(f"Camera 1 metrics available: {bool(metrics)}")
    if metrics:
        print(f"  Status: {metrics.get('status')}")
        print(f"  FPS: {metrics.get('fps')}")
        print(f"  Detection counts: {metrics.get('detection_counts', {}).get('total', {})}")
        
        # Print more detailed information about frames
        frame_stats = metrics.get('frame_stats', {})
        print(f"  Processed frames: {frame_stats.get('processed_frames', 0)}")
        print(f"  Dropped frames: {frame_stats.get('dropped_frames', 0)}")
        print(f"  Skipped frames: {frame_stats.get('skipped_frames', 0)}")
        
        # Print resource usage
        resource_usage = metrics.get('resource_usage', {})
        memory = resource_usage.get('memory_mb', {})
        cpu = resource_usage.get('cpu_percent', {})
        
        # Handle possible None values by using string formatting conditionally
        current_mem = memory.get('current')
        max_mem = memory.get('max')
        current_cpu = cpu.get('current')
        max_cpu = cpu.get('max')
        
        print(f"  Memory usage: current={current_mem if current_mem is not None else 'N/A'}MB, max={max_mem if max_mem is not None else 'N/A'}MB")
        print(f"  CPU usage: current={current_cpu if current_cpu is not None else 'N/A'}%, max={max_cpu if max_cpu is not None else 'N/A'}%")
    
    # Try to get all metrics
    all_metrics = analytics.get_all_metrics()
    print(f"Found metrics for {len(all_metrics)} cameras")
    
    # Check the internals of analytics
    with analytics.lock:
        print(f"Analytics data points collected:")
        print(f"  Cameras tracked: {list(analytics.camera_status.keys())}")
        print(f"  Frame times entries: {sum(len(q) for q in analytics.frame_times.values())}")
        print(f"  Inference times entries: {sum(len(q) for q in analytics.inference_times.values())}")
        print(f"  Detection history entries: {sum(len(h) for h in analytics.detection_history.values())}")


def test_metrics_endpoint(base_url: str, token: str):
    """
    Test metrics API endpoints
    
    Args:
        base_url: Base URL for the API (e.g., http://localhost:8000)
        token: JWT token for authentication
    """
    print("\n=== Testing Metrics API Endpoints ===")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Test the main metrics endpoint
    try:
        response = requests.get(f"{base_url}/api/metrics", headers=headers)
        response.raise_for_status()
        data = response.json()
        
        print(f"Main metrics endpoint: {response.status_code}")
        print(f"  Cameras with metrics: {len(data.get('cameras', {}))}")
        print(f"  Camera status entries: {len(data.get('camera_status', {}))}")
        print(f"  Detection status entries: {len(data.get('detection_status', {}))}")
        
    except Exception as e:
        print(f"Error accessing main metrics endpoint: {e}")
    
    # Test the camera-specific metrics endpoint
    try:
        response = requests.get(f"{base_url}/api/metrics/1", headers=headers)
        if response.status_code == 200:
            data = response.json()
            print(f"Camera 1 metrics: {response.status_code}")
            metrics = data.get('metrics', {})
            print(f"  Status: {metrics.get('status')}")
            print(f"  FPS: {metrics.get('fps')}")
            
            frame_stats = metrics.get('frame_stats', {})
            print(f"  Frames processed: {frame_stats.get('processed_frames', 0)}")
            print(f"  Frames dropped: {frame_stats.get('dropped_frames', 0)}")
            
            detection_counts = metrics.get('detection_counts', {}).get('total', {})
            print(f"  Detection counts: {detection_counts}")
        else:
            print(f"Camera 1 metrics not available: {response.status_code}")
    
    except Exception as e:
        print(f"Error accessing camera metrics endpoint: {e}")
    
    # Test the resource metrics endpoint
    try:
        response = requests.get(f"{base_url}/api/metrics/resource", headers=headers)
        response.raise_for_status()
        data = response.json()
        
        print(f"Resource metrics endpoint: {response.status_code}")
        system = data.get('system', {})
        print(f"  CPU: {system.get('cpu_percent')}%")
        print(f"  Memory: {system.get('memory_percent')}%")
        print(f"  Disk: {system.get('disk_percent')}%")
        
    except Exception as e:
        print(f"Error accessing resource metrics endpoint: {e}")


def run_test_camera(duration: int = 30):
    """
    Run a test camera and detection worker for a specified duration
    
    Args:
        duration: Duration in seconds to run the test
    """
    print(f"\n=== Running Test Camera for {duration} seconds ===")
    
    # Start a camera with detection enabled
    camera_id = 1
    
    # Try to use a test video file if available
    source_path = "test_video.mp4"
    if not os.path.exists(source_path):
        # Fall back to webcam
        source_path = 0
    
    print(f"Using source: {source_path}")
    
    # Start camera with detection enabled
    camera_manager.get_camera(camera_id, source_path, enable_detection=True)
    print(f"Started camera {camera_id} with detection")
    
    # Run for the specified duration
    for i in range(duration):
        time.sleep(1)
        if i % 5 == 0 or i == duration-1:  # Report at every 5 seconds and at the end
            print(f"  Running... {i}/{duration} seconds")
            
            # Get status
            camera_status = camera_manager.get_camera_status(camera_id)
            if camera_status:
                print(f"  Camera status: {camera_status.get('status')}")
                print(f"  Camera FPS: {camera_status.get('fps', 0):.2f}")
            
            # Get detection status
            detection_status = detection_manager.get_worker_status(camera_id)
            if detection_status:
                print(f"  Detection status: {detection_status.get('status')}")
                print(f"  Detection FPS: {detection_status.get('fps', 0):.2f}")
                print(f"  Detection count: {detection_status.get('detection_count', 0)}")
                print(f"  Frames processed: {detection_status.get('frames_processed', 0)}")
                print(f"  Frames dropped: {detection_status.get('frames_dropped', 0)}")
    
            # Manually force analytics recording for testing
            analytics.record_frame(camera_id, 0.033)  # ~30fps
            analytics.record_inference(camera_id, 0.15, 3, {"person": 2, "car": 1})
    
    # Release the camera
    camera_manager.release_camera(camera_id)
    print(f"Released camera {camera_id}")


def main():
    parser = argparse.ArgumentParser(description="Test script for metrics collection")
    parser.add_argument("--run", action="store_true", help="Run a test camera")
    parser.add_argument("--duration", type=int, default=30, help="Duration to run the test camera (seconds)")
    parser.add_argument("--test-api", action="store_true", help="Test metrics API endpoints")
    parser.add_argument("--base-url", type=str, default="http://localhost:8000", help="Base URL for API tests")
    parser.add_argument("--token", type=str, help="JWT token for API authentication")
    
    args = parser.parse_args()
    
    # Always test direct metrics
    test_direct_metrics()
    
    # Run a test camera if requested
    if args.run:
        run_test_camera(args.duration)
        
        # Test direct metrics again after running the camera
        test_direct_metrics()
    
    # Test API endpoints if requested
    if args.test_api:
        if not args.token:
            print("Error: JWT token is required for API tests")
            return
        
        test_metrics_endpoint(args.base_url, args.token)


if __name__ == "__main__":
    main() 