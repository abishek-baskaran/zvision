#!/usr/bin/env python3
"""
Test script for DetectionWorker and DetectionManager

This script tests the functionality of the DetectionWorker in a separate process,
verifying that it can read frames from a camera source and run detection successfully.
"""

import argparse
import cv2
import os
import sys
import time
import numpy as np
from multiprocessing import Queue
from typing import List, Optional

# Add parent directory to path to import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.camera_manager import CameraWorker
from app.detection_worker import DetectionWorker, detection_manager, DetectionResult

def list_cameras():
    """
    List all available cameras
    """
    print("Checking available cameras...\n")
    
    available_cameras = []
    for i in range(10):  # Check first 10 camera indices
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            available_cameras.append({
                'index': i,
                'width': width,
                'height': height,
                'fps': fps
            })
            print(f"Camera {i} available: {width}x{height} @ {fps}fps")
            cap.release()
    
    if not available_cameras:
        print("No cameras found.")
    
    return available_cameras

def create_test_frame(width=640, height=480):
    """Create a test frame with a moving rectangle"""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Current time for movement
    t = time.time() * 2
    
    # Calculate position (moving in a circle)
    center_x = width // 2
    center_y = height // 2
    radius = min(width, height) // 4
    
    x = int(center_x + radius * np.cos(t))
    y = int(center_y + radius * np.sin(t))
    
    # Draw a small rectangle (simulating a person)
    person_width = 40
    person_height = 100
    cv2.rectangle(
        frame, 
        (x - person_width//2, y - person_height//2), 
        (x + person_width//2, y + person_height//2), 
        (0, 255, 0), 
        -1
    )
    
    # Add timestamp
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(
        frame, 
        timestamp, 
        (20, height - 20), 
        cv2.FONT_HERSHEY_SIMPLEX, 
        0.5, 
        (255, 255, 255), 
        1
    )
    
    return frame

def test_camera_worker(source, num_frames=10):
    """
    Test the CameraWorker by starting it and displaying frames
    
    Args:
        source: Camera source (index or path)
        num_frames: Number of frames to capture
    """
    print(f"Testing CameraWorker with source: {source}")
    
    # Create output directory
    os.makedirs("output", exist_ok=True)
    
    # Create camera worker
    camera_id = 1  # Test camera ID
    worker = CameraWorker(camera_id, source)
    
    # Create frame queue to pass frames
    frame_queue = Queue(maxsize=10)
    
    # Start worker
    worker.start()
    print(f"Camera worker started. Status: {worker.shared_state.get('status')}")
    
    # Wait for worker to initialize
    time.sleep(2)
    print(f"Camera status after init: {worker.shared_state.get('status')}")
    
    # Capture frames for testing detection
    print("Capturing frames for detection test...")
    frames = []
    
    for i in range(30):  # Try to get 10 frames
        result = worker.get_frame()
        if result is not None:
            frame, timestamp = result
            frames.append((frame.copy(), timestamp))
            print(f"Captured frame {len(frames)}")
            
            if len(frames) >= num_frames:
                break
        else:
            print("No frame available, waiting...")
            time.sleep(0.1)
    
    # Stop the camera worker
    worker.stop()
    print("Camera worker stopped")
    
    # Pass some test frames to the detection worker queue
    print(f"Passing {len(frames)} frames to detection queue")
    for i, (frame, timestamp) in enumerate(frames):
        frame_queue.put((frame, timestamp))
        
        # Save frame for reference
        output_path = f"output/test_frame_{i}.jpg"
        cv2.imwrite(output_path, frame)
        print(f"Saved test frame to {output_path}")
    
    return frame_queue, frames

def test_detection_worker(frame_queue, frames):
    """
    Test the DetectionWorker by starting it and processing frames
    
    Args:
        frame_queue: Queue containing frames to process
        frames: List of frames for reference
    """
    print("\nTesting DetectionWorker...")
    
    # Create output directory
    os.makedirs("output", exist_ok=True)
    
    # Create detection worker
    camera_id = 1  # Test camera ID
    results_queue = Queue()
    detection_worker = DetectionWorker(
        camera_id=camera_id,
        frame_queue=frame_queue,
        results_queue=results_queue,
        target_fps=5.0
    )
    
    # Start worker
    detection_worker.start()
    print("Detection worker started")
    
    # Wait for detections
    print("Waiting for detection results...")
    results = []
    
    # Wait for up to 10 seconds for results
    timeout = time.time() + 10
    while time.time() < timeout and len(results) < len(frames):
        try:
            if not results_queue.empty():
                result = results_queue.get_nowait()
                results.append(result)
                print(f"Got detection result {len(results)}")
        except:
            time.sleep(0.1)
    
    # Stop the detection worker
    detection_worker.stop()
    print("Detection worker stopped")
    
    # Process and display results
    print(f"\nProcessing {len(results)} detection results:")
    
    for i, result in enumerate(results):
        if not isinstance(result, DetectionResult):
            print(f"Result {i} is not a DetectionResult: {result}")
            continue
            
        print(f"\nResult {i}:")
        print(f"  Timestamp: {result.timestamp}")
        print(f"  Processed time: {result.processed_time:.3f}s")
        print(f"  Number of detections: {result.count_detections(0.5)}")
        
        # Draw detections on the frame
        if i < len(frames):
            frame = frames[i][0].copy()
            
            # Get filtered boxes with good confidence
            boxes = result.get_filtered_boxes(0.5)
            
            for j, box in enumerate(boxes):
                # Get corresponding score and label
                score = result.scores[j] if j < len(result.scores) else 0
                label = result.labels[j] if j < len(result.labels) else 0
                
                # Convert box to integers
                box = [int(x) for x in box]
                
                # Draw bounding box
                cv2.rectangle(
                    frame, 
                    (box[0], box[1]), 
                    (box[2], box[3]), 
                    (0, 255, 0), 
                    2
                )
                
                # Draw label and score
                label_text = f"{label}: {score:.2f}"
                cv2.putText(
                    frame, 
                    label_text, 
                    (box[0], box[1] - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 
                    0.5, 
                    (0, 255, 0), 
                    2
                )
            
            # Save frame with detections
            output_path = f"output/detection_result_{i}.jpg"
            cv2.imwrite(output_path, frame)
            print(f"  Saved detection result to {output_path}")
    
    return results

def test_detection_manager(source_or_worker, num_frames=10):
    """
    Test the DetectionManager with a camera source
    
    Args:
        source_or_worker: Camera source (index, path) or CameraWorker object
        num_frames: Number of frames to capture
    """
    print("\nTesting DetectionManager with integrated CameraManager...")
    
    # Create output directory
    os.makedirs("output", exist_ok=True)
    
    # Clear any existing workers
    stop_all_workers()
    
    # Create or use provided camera worker
    camera_id = 1  # Test camera ID
    if isinstance(source_or_worker, CameraWorker):
        worker = source_or_worker
        if not worker._started:
            worker.start()
    else:
        worker = CameraWorker(camera_id, source_or_worker)
        worker.start()
        
    print(f"Camera worker started: {worker.shared_state.get('status')}")
    
    # Wait for camera to initialize
    time.sleep(2)
    
    # Start detection worker through manager
    detection_manager.start_worker(camera_id, worker.frame_queue)
    print(f"Detection worker started through manager for camera {camera_id}")
    
    # Give some time for detections to happen
    print("Waiting for detection results to accumulate...")
    time.sleep(5)
    
    # Get status
    worker_status = detection_manager.get_worker_status(camera_id)
    print(f"Detection worker status: {worker_status}")
    
    # Capture results
    results = []
    for i in range(num_frames):
        result = detection_manager.get_latest_detection(camera_id)
        if result:
            results.append(result)
            print(f"Got result {i+1}: {result.count_detections(0.5)} detections")
            
            # Visualize the result
            frame_result = worker.get_frame()
            if frame_result:
                frame, timestamp = frame_result
                frame = frame.copy()
                
                # Get filtered boxes
                boxes = result.get_filtered_boxes(0.5)
                
                for j, box in enumerate(boxes):
                    # Try to get corresponding score and label
                    try:
                        score = result.scores[j] if j < len(result.scores) else 0
                        label = result.labels[j] if j < len(result.labels) else 0
                    except:
                        score = 0
                        label = 0
                    
                    # Convert box to integers
                    box = [int(x) for x in box]
                    
                    # Draw bounding box
                    cv2.rectangle(
                        frame, 
                        (box[0], box[1]), 
                        (box[2], box[3]), 
                        (0, 255, 0), 
                        2
                    )
                    
                    # Draw label and score
                    label_text = f"{label}: {score:.2f}"
                    cv2.putText(
                        frame, 
                        label_text, 
                        (box[0], box[1] - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 
                        0.5, 
                        (0, 255, 0), 
                        2
                    )
                
                # Save frame with detections
                output_path = f"output/manager_detection_{i}.jpg"
                cv2.imwrite(output_path, frame)
                print(f"Saved detection visualization to {output_path}")
        else:
            print(f"No detection result available for frame {i+1}")
        
        time.sleep(0.5)  # Wait a bit between results
    
    # Clean up
    detection_manager.stop_worker(camera_id)
    if isinstance(source_or_worker, CameraWorker):
        # Only stop if we created it
        if not hasattr(worker, 'get_frame_original'):
            worker.stop()
    else:
        worker.stop()
        
    print("Cleaned up all workers")
    
    return results

def main():
    parser = argparse.ArgumentParser(description="Test script for DetectionWorker")
    parser.add_argument("--list", action="store_true", help="List available cameras")
    parser.add_argument("--source", type=str, default="0", help="Camera source (index or path, or 'test' for synthetic frames)")
    parser.add_argument("--frames", type=int, default=5, help="Number of frames to process")
    parser.add_argument("--manager", action="store_true", help="Test with DetectionManager integration")
    
    args = parser.parse_args()
    
    # List cameras if requested
    if args.list:
        list_cameras()
        return
    
    # Determine source
    source = args.source
    if source.isdigit():
        source = int(source)
    
    # Test with camera manager integration
    if args.manager:
        # For test source with manager
        if source == "test":
            print("Using synthetic frames with detection manager")
            # Create a CameraWorker with test frames
            camera_id = 1
            worker = CameraWorker(camera_id, 0)  # Dummy source
            worker.start()
            
            # Push test frames to the queue
            for i in range(args.frames):
                frame = create_test_frame()
                timestamp = time.time()
                worker.frame_queue.put((frame, timestamp))
                print(f"Pushed test frame {i} to queue")
                
                # Save for reference
                os.makedirs("output", exist_ok=True)
                output_path = f"output/synthetic_manager_frame_{i}.jpg"
                cv2.imwrite(output_path, frame)
            
            test_detection_manager(worker, args.frames)
        else:
            test_detection_manager(source, args.frames)
        return
        
    # For normal test mode
    if source == "test":
        print("Using synthetic test frames")
        
        # Create a queue and populate with test frames
        frame_queue = Queue(maxsize=10)
        frames = []
        
        for i in range(args.frames):
            frame = create_test_frame()
            timestamp = time.time()
            frame_queue.put((frame, timestamp))
            frames.append((frame, timestamp))
            
            # Save test frame
            os.makedirs("output", exist_ok=True)
            output_path = f"output/synthetic_frame_{i}.jpg"
            cv2.imwrite(output_path, frame)
            print(f"Created synthetic frame {i}, saved to {output_path}")
        
        # Test with direct synthetic frames
        test_detection_worker(frame_queue, frames)
        return
    
    # Standard test flow
    frame_queue, frames = test_camera_worker(source, args.frames)
    if frames:
        test_detection_worker(frame_queue, frames)
    else:
        print("No frames captured, cannot test detection")

# Add this function to stop all detection workers
def stop_all_workers():
    """Stop all detection workers in the manager"""
    print("Stopping all detection workers...")
    detection_manager.stop()
    detection_manager.start()  # Restart the manager without workers

if __name__ == "__main__":
    main() 