"""
Test script for the CameraWorker process.

This script tests that the camera worker process can capture frames continuously
and provide them through a queue to the main process.

Usage:
    python -m app.tests.test_camera_worker
"""

import time
import cv2
import numpy as np
from multiprocessing import Process
import os
import sys
import argparse
from typing import Optional

# Add the project root to the path so we can import our modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.camera_manager import CameraWorker, CameraManager

def display_frames(camera_id: int, source_path: str, fps: Optional[float] = None):
    """
    Display frames from a camera worker in a window.
    
    Args:
        camera_id: ID of the camera
        source_path: Path or URL to the camera source
        fps: Optional target FPS
    """
    print(f"Creating camera worker for camera {camera_id} with source {source_path}")
    
    # Create and start a camera worker
    worker = CameraWorker(camera_id, source_path, target_fps=fps)
    worker.start()
    
    try:
        # Display frames in a window
        cv2.namedWindow(f"Camera {camera_id}", cv2.WINDOW_NORMAL)
        
        start_time = time.time()
        frame_count = 0
        running = True
        
        while running:
            # Get a frame from the worker
            result = worker.get_frame()
            
            if result is not None:
                frame, timestamp = result
                frame_count += 1
                
                # Calculate FPS
                elapsed = time.time() - start_time
                if elapsed >= 1.0:
                    fps = frame_count / elapsed
                    print(f"FPS: {fps:.2f}, Queue size: {worker.frame_queue.qsize()}")
                    start_time = time.time()
                    frame_count = 0
                
                # Display the frame
                cv2.imshow(f"Camera {camera_id}", frame)
            
            # Handle keyboard input (press 'q' to quit)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                running = False
    
    finally:
        # Clean up
        worker.stop()
        cv2.destroyAllWindows()

def test_camera_manager(camera_id: int, source_path: str):
    """
    Test the CameraManager with the specified camera.
    
    Args:
        camera_id: ID of the camera
        source_path: Path or URL to the camera source
    """
    print(f"Testing CameraManager with camera {camera_id} and source {source_path}")
    
    # Create a camera manager
    manager = CameraManager()
    
    try:
        # Display frames in a window
        cv2.namedWindow(f"Camera {camera_id}", cv2.WINDOW_NORMAL)
        
        start_time = time.time()
        frame_count = 0
        running = True
        
        while running:
            # Get a frame from the manager
            frame = manager.get_frame(camera_id, source_path)
            
            if frame is not None:
                frame_count += 1
                
                # Calculate FPS
                elapsed = time.time() - start_time
                if elapsed >= 1.0:
                    fps = frame_count / elapsed
                    print(f"FPS: {fps:.2f}")
                    
                    # Also print the camera status
                    status = manager.get_camera_status(camera_id)
                    print(f"Camera status: {status}")
                    
                    start_time = time.time()
                    frame_count = 0
                
                # Display the frame
                cv2.imshow(f"Camera {camera_id}", frame)
            
            # Handle keyboard input (press 'q' to quit)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                running = False
    
    finally:
        # Clean up
        manager.release_all()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test the CameraWorker")
    parser.add_argument("--source", type=str, default="0", 
                       help="Camera source (ID, file path, or RTSP URL)")
    parser.add_argument("--id", type=int, default=1, 
                       help="Camera ID (for identification)")
    parser.add_argument("--fps", type=float, default=None, 
                       help="Target FPS (if not specified, use camera's native FPS)")
    parser.add_argument("--manager", action="store_true", 
                       help="Test CameraManager instead of CameraWorker directly")
    
    args = parser.parse_args()
    
    # Convert source to int if it's a numeric string (for webcam index)
    source = args.source
    if source.isdigit():
        source = int(source)
    
    if args.manager:
        test_camera_manager(args.id, source)
    else:
        display_frames(args.id, source, args.fps) 