"""
Camera streaming implementation for WebRTC using aiortc.

This module provides custom MediaStreamTrack implementations for
camera streaming over WebRTC using the aiortc library.
"""

import asyncio
import cv2
import fractions
import logging
import time
import threading
from typing import Dict, Optional, Any

import av
import numpy as np

# Import mock camera for testing
try:
    from app.webrtc.mock_camera import create_mock_camera
    MOCK_CAMERA_AVAILABLE = True
except ImportError:
    logging.warning("Mock camera module not available.")
    MOCK_CAMERA_AVAILABLE = False

try:
    from aiortc.mediastreams import MediaStreamError, MediaStreamTrack
    from aiortc.contrib.media import MediaRelay
    AIORTC_AVAILABLE = True
except ImportError:
    logging.warning("aiortc not installed. Camera streaming will not be available.")
    AIORTC_AVAILABLE = False
    # Create placeholder classes to avoid errors
    class MediaStreamTrack:
        pass
    class MediaStreamError(Exception):
        pass

# Configure logging
logger = logging.getLogger(__name__)

# Store active camera captures to allow sharing between multiple clients
active_captures: Dict[str, Any] = {}
active_captures_lock = threading.Lock()

class CameraVideoTrack(MediaStreamTrack):
    """
    A video track that captures from a camera source.
    
    This track reads frames from an OpenCV capture (can be RTSP stream, 
    video file, or local camera) and converts them to VideoFrame objects
    for use with aiortc.
    """
    kind = "video"  # MediaStreamTrack type
    
    def __init__(self, source: str, camera_id: int, options: Optional[Dict[str, Any]] = None):
        """
        Initialize the camera video track.
        
        Args:
            source: URL or path to the video source (RTSP, file, etc.)
            camera_id: Unique identifier for this camera
            options: Optional configuration settings for the video capture
        """
        if not AIORTC_AVAILABLE:
            raise RuntimeError("aiortc not available. Cannot create CameraVideoTrack.")
            
        super().__init__()
        self.source = source
        self.camera_id = camera_id
        self.options = options or {}
        
        # Video configuration
        self.pts = 0
        self.time_base = fractions.Fraction(1, 90000)  # Standard for video
        self._start_time = time.time()
        
        # Use thread-safe access to shared captures
        with active_captures_lock:
            capture_key = f"{camera_id}:{source}"
            if capture_key in active_captures:
                logger.info(f"Reusing existing capture for camera {camera_id}")
                self.cap = active_captures[capture_key]["capture"]
                active_captures[capture_key]["ref_count"] += 1
            else:
                logger.info(f"Creating new capture for camera {camera_id}, source: {source}")
                # Create a new capture
                use_mock = self.options.get("use_mock", False)
                
                # Try to create a real camera capture
                if not use_mock:
                    self.cap = cv2.VideoCapture(source)
                    
                    if not self.cap.isOpened():
                        logger.warning(f"Could not open video source: {source}, falling back to mock camera")
                        use_mock = True
                
                # Use mock camera if requested or if real camera failed
                if use_mock:
                    if MOCK_CAMERA_AVAILABLE:
                        logger.info(f"Using mock camera for camera_id={camera_id}")
                        self.cap = create_mock_camera(camera_id, self.options)
                    else:
                        raise RuntimeError(f"Could not open video source: {source} and mock camera not available")
                
                # Set capture properties if specified
                if "width" in self.options and "height" in self.options:
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.options["width"])
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.options["height"])
                
                if "fps" in self.options:
                    self.cap.set(cv2.CAP_PROP_FPS, self.options["fps"])
                
                # Store in active captures
                active_captures[capture_key] = {
                    "capture": self.cap,
                    "ref_count": 1,
                    "last_access": time.time()
                }
            
            # Get actual video properties
            self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
            if self.fps <= 0:
                self.fps = 30.0  # Default if not available
                
            # To track when this track was last used
            self.capture_key = capture_key
            self._last_frame_time = 0
            self._running = True
    
    async def recv(self):
        """
        Receive the next frame from the camera source.
        
        Returns:
            A VideoFrame containing the camera frame data.
            
        Raises:
            MediaStreamError: If reading the frame fails or the track is ended.
        """
        if not self._running:
            raise MediaStreamError("Track has ended")
        
        # Calculate how long to wait to maintain proper FPS
        elapsed = time.time() - self._last_frame_time
        wait_time = 1.0 / self.fps - elapsed
        
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        
        # Update active capture timestamp
        with active_captures_lock:
            if self.capture_key in active_captures:
                active_captures[self.capture_key]["last_access"] = time.time()
        
        # Read frame from the capture
        ret, frame = self.cap.read()
        self._last_frame_time = time.time()
        
        if not ret:
            # For video files, we might want to loop
            if not self.source.startswith(('rtsp://', 'http://', 'https://')):
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
                if not ret:
                    raise MediaStreamError("Failed to read from video file")
            else:
                # For streams, try to reconnect
                logger.warning(f"Failed to read from stream {self.source}, attempting to reconnect")
                with active_captures_lock:
                    if self.capture_key in active_captures:
                        self.cap.release()
                        self.cap = cv2.VideoCapture(self.source)
                        active_captures[self.capture_key]["capture"] = self.cap
                        if not self.cap.isOpened():
                            raise MediaStreamError(f"Failed to reconnect to stream {self.source}")
                        ret, frame = self.cap.read()
                        if not ret:
                            raise MediaStreamError("Failed to read frame after reconnection")
        
        # Convert OpenCV BGR frame to RGB for aiortc
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Create VideoFrame object
        video_frame = av.VideoFrame.from_ndarray(frame, format="rgb24")
        
        # Set timestamp
        pts = int((time.time() - self._start_time) / self.time_base)
        video_frame.pts = pts
        video_frame.time_base = self.time_base
        
        return video_frame
    
    def stop(self):
        """
        Stop the video track and release resources.
        """
        self._running = False
        
        # Decrement reference count for the shared capture
        with active_captures_lock:
            if self.capture_key in active_captures:
                active_captures[self.capture_key]["ref_count"] -= 1
                
                # If this was the last reference, release the capture
                if active_captures[self.capture_key]["ref_count"] <= 0:
                    logger.info(f"Releasing camera capture for {self.camera_id}")
                    self.cap.release()
                    del active_captures[self.capture_key]
                else:
                    logger.info(f"Track stopped, but {active_captures[self.capture_key]['ref_count']} references remain for {self.camera_id}")

def cleanup_old_captures():
    """
    Clean up any captures that haven't been accessed for a while.
    This should be called periodically to free resources.
    """
    with active_captures_lock:
        current_time = time.time()
        keys_to_remove = []
        
        for key, info in active_captures.items():
            # If not accessed in last 5 minutes and no references, remove it
            if current_time - info["last_access"] > 300 and info["ref_count"] <= 0:
                logger.info(f"Cleaning up unused capture: {key}")
                info["capture"].release()
                keys_to_remove.append(key)
        
        # Remove from dictionary
        for key in keys_to_remove:
            del active_captures[key]
            
def get_camera_track(camera_id: int, source: str, options: Optional[Dict[str, Any]] = None) -> Optional[MediaStreamTrack]:
    """
    Create a camera video track for the given camera.
    
    Args:
        camera_id: Unique identifier for the camera
        source: URL or path to the video source
        options: Optional configuration settings
        
    Returns:
        A CameraVideoTrack instance or None if creation fails
    """
    if not AIORTC_AVAILABLE:
        logger.warning("aiortc not available. Cannot create camera track.")
        return None
    
    try:
        return CameraVideoTrack(source=source, camera_id=camera_id, options=options)
    except Exception as e:
        logger.error(f"Failed to create camera track for {camera_id}: {str(e)}")
        return None 