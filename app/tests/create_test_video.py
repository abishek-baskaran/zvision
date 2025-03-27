#!/usr/bin/env python3
"""
Generate a test video file for camera testing.

This script creates a simple test video with moving objects for testing the
camera and detection system when physical cameras are not available.
"""

import os
import sys
import argparse
import numpy as np
import cv2
from typing import Tuple, Optional

# Default settings
DEFAULT_WIDTH = 640
DEFAULT_HEIGHT = 480
DEFAULT_FPS = 30
DEFAULT_DURATION = 10  # seconds
DEFAULT_FILENAME = "test_video.mp4"


def create_test_pattern(frame_num: int, width: int, height: int) -> np.ndarray:
    """
    Create a test pattern frame with moving shapes
    
    Args:
        frame_num: Current frame number
        width: Frame width
        height: Frame height
        
    Returns:
        Frame as numpy array
    """
    # Create a blank frame
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Add a time counter
    time_text = f"Frame: {frame_num}"
    cv2.putText(frame, time_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    # Add a moving square (person)
    square_size = 100
    x = int((frame_num * 5) % (width - square_size))
    y = height // 3
    cv2.rectangle(frame, (x, y), (x + square_size, y + square_size), (0, 0, 255), -1)
    cv2.putText(frame, "Person", (x + 10, y + 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    # Add a moving rectangle (car)
    rect_width = 120
    rect_height = 60
    x2 = width - int((frame_num * 3) % (width - rect_width)) - rect_width
    y2 = 2 * height // 3
    cv2.rectangle(frame, (x2, y2), (x2 + rect_width, y2 + rect_height), (0, 255, 0), -1)
    cv2.putText(frame, "Car", (x2 + 20, y2 + 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    
    # Add some noise for realism
    noise = np.random.randint(0, 10, (height, width, 3), dtype=np.uint8)
    frame = cv2.add(frame, noise)
    
    return frame


def create_test_video(output_file: str, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT, 
                     fps: int = DEFAULT_FPS, duration: int = DEFAULT_DURATION) -> bool:
    """
    Create a test video file with moving shapes
    
    Args:
        output_file: Output file path
        width: Frame width
        height: Frame height
        fps: Frames per second
        duration: Duration in seconds
        
    Returns:
        True if successful, False otherwise
    """
    # Create video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_file, fourcc, fps, (width, height))
    
    if not out.isOpened():
        print(f"Error: Could not create video file {output_file}")
        return False
    
    total_frames = fps * duration
    
    print(f"Creating test video: {output_file}")
    print(f"Resolution: {width}x{height}, FPS: {fps}, Duration: {duration}s")
    print(f"Total frames: {total_frames}")
    
    try:
        # Generate and write frames
        for i in range(total_frames):
            progress = (i + 1) / total_frames * 100
            if i % fps == 0:  # Show progress every second
                print(f"Progress: {progress:.1f}% ({i+1}/{total_frames} frames)")
            
            frame = create_test_pattern(i, width, height)
            out.write(frame)
        
        print("Video creation complete!")
        return True
    
    except Exception as e:
        print(f"Error creating video: {e}")
        return False
    
    finally:
        # Release resources
        out.release()


def main():
    parser = argparse.ArgumentParser(description="Create a test video file for camera testing")
    parser.add_argument("--output", type=str, default=DEFAULT_FILENAME, help="Output file path")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH, help="Frame width")
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT, help="Frame height")
    parser.add_argument("--fps", type=int, default=DEFAULT_FPS, help="Frames per second")
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION, help="Duration in seconds")
    
    args = parser.parse_args()
    
    success = create_test_video(args.output, args.width, args.height, args.fps, args.duration)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main() 