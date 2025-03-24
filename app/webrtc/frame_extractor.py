"""
WebRTC frame extraction module for ZVision.

This module provides functionality to extract frames from WebRTC streams
at regular intervals defined by calibration settings, and process them
with the YOLO detection model.
"""

import asyncio
import cv2
import logging
import time
import threading
from typing import Dict, Optional, Any, List, Tuple, Callable

import numpy as np

# Import the YOLO detection function
from app.inference.detection import run_yolo_inference

# Import calibration 
from app.database.calibration import fetch_calibration_for_camera

# Configure logging
logger = logging.getLogger(__name__)

# Store active frame extractors
active_extractors: Dict[int, 'FrameExtractor'] = {}
extractors_lock = threading.Lock()

class FrameExtractor:
    """
    Extracts frames from WebRTC video tracks at regular intervals
    and runs detection on them.
    """
    
    def __init__(self, camera_id: int, video_track: Any, 
                 frame_rate: Optional[int] = None,
                 callback: Optional[Callable[[List[Dict[str, Any]]], None]] = None):
        """
        Initialize the frame extractor.
        
        Args:
            camera_id: Unique identifier for the camera
            video_track: The WebRTC video track to extract frames from
            frame_rate: Number of frames per second to extract (default: from calibration or 5)
            callback: Optional callback function to receive detection results
        """
        self.camera_id = camera_id
        self.video_track = video_track
        self.callback = callback
        
        # Get frame rate from calibration if not specified
        if frame_rate is None:
            calibration = fetch_calibration_for_camera(camera_id)
            if calibration and calibration.get("frame_rate"):
                self.frame_rate = calibration.get("frame_rate")
            else:
                self.frame_rate = 5  # Default if not specified or no calibration
        else:
            self.frame_rate = frame_rate
        
        # Extract at 1/frame_rate intervals (in seconds)
        self.interval = 1.0 / self.frame_rate if self.frame_rate > 0 else 0.2
        
        # State variables
        self._running = False
        self._last_frame_time = 0
        self._extract_task = None
        self._frame_count = 0
        self._detection_count = 0
        
        logger.info(f"Created frame extractor for camera {camera_id} at {self.frame_rate} FPS")
    
    async def start(self):
        """
        Start extracting frames and running detection.
        """
        if self._running:
            return
        
        self._running = True
        self._last_frame_time = time.time()
        self._frame_count = 0
        self._detection_count = 0
        
        # Start the extraction task
        self._extract_task = asyncio.create_task(self._extract_frames())
        logger.info(f"Started frame extractor for camera {self.camera_id}")
    
    async def stop(self):
        """
        Stop extracting frames.
        """
        if not self._running:
            return
        
        self._running = False
        
        # Cancel the extraction task if it's running
        if self._extract_task:
            self._extract_task.cancel()
            try:
                await self._extract_task
            except asyncio.CancelledError:
                pass
            self._extract_task = None
        
        logger.info(f"Stopped frame extractor for camera {self.camera_id}")
    
    def update_frame_rate(self, frame_rate: int):
        """
        Update the frame extraction rate.
        
        Args:
            frame_rate: New frame rate in frames per second
        """
        if frame_rate <= 0:
            frame_rate = 1  # Minimum 1 FPS
        
        self.frame_rate = frame_rate
        self.interval = 1.0 / self.frame_rate
        logger.info(f"Updated frame rate for camera {self.camera_id} to {frame_rate} FPS")
    
    async def _extract_frames(self):
        """
        Continuously extract frames at the specified interval and run detection.
        """
        try:
            while self._running:
                # Calculate how long to wait to maintain proper frame rate
                now = time.time()
                elapsed = now - self._last_frame_time
                wait_time = max(0, self.interval - elapsed)
                
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                
                # Extract frame and run detection
                try:
                    await self._extract_and_detect()
                    self._last_frame_time = time.time()
                except Exception as e:
                    logger.error(f"Error extracting frame: {str(e)}")
                    await asyncio.sleep(0.1)  # Avoid tight loop on error
        
        except asyncio.CancelledError:
            logger.info(f"Frame extraction task cancelled for camera {self.camera_id}")
        except Exception as e:
            logger.error(f"Error in frame extraction loop: {str(e)}")
    
    async def _extract_and_detect(self):
        """
        Extract a single frame and run detection on it.
        """
        if not self.video_track:
            return
        
        try:
            # Get a frame from the video track
            frame = await self.video_track.recv()
            
            # Convert the frame to numpy array (for OpenCV/detection)
            frame_array = frame.to_ndarray(format="bgr24")
            
            self._frame_count += 1
            if self._frame_count % 100 == 0:
                logger.debug(f"Extracted {self._frame_count} frames from camera {self.camera_id}")
            
            # Run detection on the frame
            detection_results = await self._run_detection(frame_array)
            
            # Call the callback if provided
            if self.callback and detection_results:
                self.callback(detection_results)
        
        except Exception as e:
            logger.error(f"Error in frame extraction: {str(e)}")
            raise
    
    async def _run_detection(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Run YOLO detection on the frame and return formatted results.
        
        Args:
            frame: OpenCV BGR frame as numpy array
            
        Returns:
            List of detection results in the format:
            [
                {
                    "class_id": 0,
                    "class_name": "person",
                    "confidence": 0.95,
                    "bbox": [x1, y1, x2, y2]
                },
                ...
            ]
        """
        try:
            # Run YOLO inference (this returns boxes, scores, labels)
            loop = asyncio.get_event_loop()
            boxes, scores, labels = await loop.run_in_executor(None, run_yolo_inference, frame)
            
            # Format the results
            results = []
            for i in range(len(boxes)):
                # Person is class 0 in COCO dataset (which YOLO uses)
                class_name = "person" if labels[i] == 0 else f"class_{labels[i]}"
                
                results.append({
                    "class_id": int(labels[i]),
                    "class_name": class_name,
                    "confidence": float(scores[i]),
                    "bbox": boxes[i]
                })
            
            self._detection_count += 1
            if self._detection_count % 10 == 0:
                logger.debug(f"Processed {self._detection_count} detections for camera {self.camera_id}")
            
            return results
        
        except Exception as e:
            logger.error(f"Error running detection: {str(e)}")
            return []


def create_frame_extractor(camera_id: int, video_track: Any, 
                          frame_rate: Optional[int] = None,
                          callback: Optional[Callable] = None) -> FrameExtractor:
    """
    Create a frame extractor for a camera.
    
    Args:
        camera_id: Unique identifier for the camera
        video_track: The WebRTC video track to extract frames from
        frame_rate: Optional frame rate override
        callback: Optional callback function to receive detection results
        
    Returns:
        A FrameExtractor instance
    """
    with extractors_lock:
        # If an extractor already exists for this camera, stop it
        if camera_id in active_extractors:
            logger.info(f"Replacing existing frame extractor for camera {camera_id}")
            # We don't await here to avoid blocking, the old one will be garbage collected
            active_extractors[camera_id]._running = False
        
        # Create a new extractor
        extractor = FrameExtractor(camera_id, video_track, frame_rate, callback)
        active_extractors[camera_id] = extractor
        
        return extractor

async def start_frame_extractor(camera_id: int) -> bool:
    """
    Start the frame extractor for a camera if it exists.
    
    Args:
        camera_id: Unique identifier for the camera
        
    Returns:
        True if started, False if not found
    """
    with extractors_lock:
        if camera_id in active_extractors:
            await active_extractors[camera_id].start()
            return True
        return False

async def stop_frame_extractor(camera_id: int) -> bool:
    """
    Stop the frame extractor for a camera if it exists.
    
    Args:
        camera_id: Unique identifier for the camera
        
    Returns:
        True if stopped, False if not found
    """
    with extractors_lock:
        if camera_id in active_extractors:
            await active_extractors[camera_id].stop()
            return True
        return False

async def update_frame_rate(camera_id: int, frame_rate: int) -> bool:
    """
    Update the frame rate for a camera's extractor if it exists.
    
    Args:
        camera_id: Unique identifier for the camera
        frame_rate: New frame rate in frames per second
        
    Returns:
        True if updated, False if not found
    """
    with extractors_lock:
        if camera_id in active_extractors:
            active_extractors[camera_id].update_frame_rate(frame_rate)
            return True
        return False

async def cleanup_extractors():
    """
    Stop and remove all frame extractors.
    """
    with extractors_lock:
        for camera_id, extractor in active_extractors.items():
            await extractor.stop()
        active_extractors.clear()
