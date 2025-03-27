"""
Headless test script for the CameraWorker process.

This script tests that the camera worker process can capture frames continuously
without requiring a GUI display.

Usage:
    python -m app.tests.test_camera_worker_headless
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

def list_available_cameras():
    """
    List all available camera devices
    """
    print("Looking for available cameras...")
    
    # Check common camera indices
    for i in range(10):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            name = f"Camera {i}"
            width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            fps = cap.get(cv2.CAP_PROP_FPS)
            cap.release()
            print(f"✅ Found camera at index {i}: {width}x{height} @ {fps}fps")
        else:
            print(f"❌ No camera at index {i}")

    # Check for video4linux devices
    if os.path.exists('/dev'):
        v4l_devices = [d for d in os.listdir('/dev') if d.startswith('video')]
        if v4l_devices:
            print("\nVideo4Linux devices found:")
            for device in v4l_devices:
                print(f" - /dev/{device}")
        else:
            print("\nNo Video4Linux devices found in /dev")

def test_camera_worker_headless(camera_id: int, source_path: str, fps: Optional[float] = None, 
                               output_dir: str = "output", num_frames: int = 10):
    """
    Test the CameraWorker by saving frames to files instead of displaying them.
    
    Args:
        camera_id: ID of the camera
        source_path: Path or URL to the camera source
        fps: Optional target FPS
        output_dir: Directory to save output frames
        num_frames: Number of frames to capture
    """
    print(f"Creating camera worker for camera {camera_id} with source {source_path}")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Create and start a camera worker
    worker = CameraWorker(camera_id, source_path, target_fps=fps)
    worker.start()
    
    try:
        print(f"Waiting for worker to initialize...")
        time.sleep(2)  # Give some time for the camera to initialize
        
        # Print worker status
        print(f"Worker status: {worker.shared_state.get('status', 'unknown')}")
        
        start_time = time.time()
        frame_count = 0
        saved_count = 0
        
        print(f"Attempting to capture {num_frames} frames...")
        
        # Try to get frames for a limited time
        timeout = time.time() + 30  # 30 second timeout
        
        while saved_count < num_frames and time.time() < timeout:
            # Get a frame from the worker
            result = worker.get_frame()
            
            if result is not None:
                frame, timestamp = result
                frame_count += 1
                
                # Save every 5th frame to a file
                if frame_count % 5 == 0:
                    filename = os.path.join(output_dir, f"camera_{camera_id}_frame_{saved_count}.jpg")
                    cv2.imwrite(filename, frame)
                    saved_count += 1
                    print(f"Saved frame {saved_count}/{num_frames} to {filename}")
                
                # Calculate and display FPS periodically
                elapsed = time.time() - start_time
                if elapsed >= 1.0:
                    fps = frame_count / elapsed
                    print(f"FPS: {fps:.2f}, Queue size: {worker.frame_queue.qsize()}")
                    start_time = time.time()
                    frame_count = 0
            else:
                print("No frame available, waiting...")
                time.sleep(0.1)
        
        if saved_count >= num_frames:
            print(f"✅ Successfully saved {saved_count} frames to {output_dir}/")
        else:
            print(f"⚠️ Only captured {saved_count}/{num_frames} frames before timeout")
    
    except Exception as e:
        print(f"Error during testing: {e}")
    
    finally:
        # Clean up
        worker.stop()
        print("Worker stopped")

def test_camera_manager_headless(camera_id: int, source_path: str, output_dir: str = "output", 
                                num_frames: int = 10):
    """
    Test the CameraManager by saving frames to files instead of displaying them.
    
    Args:
        camera_id: ID of the camera
        source_path: Path or URL to the camera source
        output_dir: Directory to save output frames
        num_frames: Number of frames to capture
    """
    print(f"Testing CameraManager with camera {camera_id} and source {source_path}")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Create a camera manager
    manager = CameraManager()
    
    try:
        print(f"Getting camera from manager...")
        manager.get_camera(camera_id, source_path)
        
        # Give some time for the camera to initialize
        time.sleep(2)
        
        # Print camera status
        status = manager.get_camera_status(camera_id)
        print(f"Camera status: {status}")
        
        start_time = time.time()
        frame_count = 0
        saved_count = 0
        
        print(f"Attempting to capture {num_frames} frames...")
        
        # Try to get frames for a limited time
        timeout = time.time() + 30  # 30 second timeout
        
        while saved_count < num_frames and time.time() < timeout:
            # Get a frame from the manager
            frame = manager.get_frame(camera_id, source_path)
            
            if frame is not None:
                frame_count += 1
                
                # Save every 5th frame to a file
                if frame_count % 5 == 0:
                    filename = os.path.join(output_dir, f"manager_camera_{camera_id}_frame_{saved_count}.jpg")
                    cv2.imwrite(filename, frame)
                    saved_count += 1
                    print(f"Saved frame {saved_count}/{num_frames} to {filename}")
                
                # Calculate and display FPS periodically
                elapsed = time.time() - start_time
                if elapsed >= 1.0:
                    fps = frame_count / elapsed
                    print(f"FPS: {fps:.2f}")
                    
                    # Also print the camera status
                    status = manager.get_camera_status(camera_id)
                    print(f"Camera status: {status}")
                    
                    start_time = time.time()
                    frame_count = 0
            else:
                print("No frame available, waiting...")
                time.sleep(0.1)
        
        if saved_count >= num_frames:
            print(f"✅ Successfully saved {saved_count} frames to {output_dir}/")
        else:
            print(f"⚠️ Only captured {saved_count}/{num_frames} frames before timeout")
    
    except Exception as e:
        print(f"Error during testing: {e}")
    
    finally:
        # Clean up
        manager.release_all()
        print("Manager released all cameras")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test the CameraWorker without GUI")
    parser.add_argument("--source", type=str, default="0", 
                       help="Camera source (ID, file path, or RTSP URL)")
    parser.add_argument("--id", type=int, default=1, 
                       help="Camera ID (for identification)")
    parser.add_argument("--fps", type=float, default=None, 
                       help="Target FPS (if not specified, use camera's native FPS)")
    parser.add_argument("--manager", action="store_true", 
                       help="Test CameraManager instead of CameraWorker directly")
    parser.add_argument("--output", type=str, default="output",
                       help="Directory to save output frames")
    parser.add_argument("--frames", type=int, default=5,
                       help="Number of frames to capture")
    parser.add_argument("--list", action="store_true",
                       help="List available cameras and exit")
    
    args = parser.parse_args()
    
    if args.list:
        list_available_cameras()
        sys.exit(0)
    
    # Convert source to int if it's a numeric string (for webcam index)
    source = args.source
    if source.isdigit():
        source = int(source)
    
    if args.manager:
        test_camera_manager_headless(args.id, source, args.output, args.frames)
    else:
        test_camera_worker_headless(args.id, source, args.fps, args.output, args.frames) 