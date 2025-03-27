"""
Camera Manager Module for ZVision

This module is responsible for managing camera capture processes and providing
access to the latest frames from cameras.
"""

import cv2
import time
from typing import Dict, Optional, Tuple, List, Any
import numpy as np
from multiprocessing import Process, Queue, Event, Manager
import logging
import threading
import queue
import os

logger = logging.getLogger(__name__)

# Import detection manager but don't initialize it yet to avoid circular imports
from app.detection_worker import detection_manager

class CameraWorker(Process):
    """
    Camera worker class that runs in a separate process to continuously capture frames
    from a camera source without blocking the main application.
    """
    
    def __init__(self, camera_id: int, source_path: str, max_queue_size: int = 30, 
                 target_fps: Optional[float] = None):
        """
        Initialize the CameraWorker
        
        Args:
            camera_id: ID of the camera
            source_path: Path or URL to the camera source (file, RTSP, etc.)
            max_queue_size: Maximum number of frames to keep in the queue
            target_fps: Target frame rate (if None, use camera's native fps)
        """
        # Initialize as non-daemon process to allow using Manager
        super().__init__(daemon=False)
        self.camera_id = camera_id
        self.source_path = source_path
        self.max_queue_size = max_queue_size
        self.target_fps = target_fps
        
        # Create a Queue for sharing frames between processes
        self.frame_queue = Queue(maxsize=max_queue_size)
        
        # Event for signaling process termination
        self.stop_event = Event()
        
        # Initialize a regular dictionary to store state
        # We'll create a shared state dictionary in the run method
        self.shared_state = {
            'last_frame_time': 0,
            'fps': 0,
            'frame_count': 0,
            'status': 'initialized'
        }
        
        # Status flags
        self._started = False
    
    def start(self):
        """
        Start the camera capture process
        """
        if not self._started:
            # Use local state before the process starts
            self.shared_state['status'] = 'starting'
            super().start()
            self._started = True
            logger.info(f"Started camera worker process for camera {self.camera_id}")
        return self._started
    
    def stop(self):
        """
        Stop the camera capture process
        """
        if self._started:
            # Signal the process to stop via the event
            self.stop_event.set()
            self.join(timeout=3.0)  # Wait up to 3 seconds for process to terminate
            logger.info(f"Stopped camera worker process for camera {self.camera_id}")
            self._started = False
    
    def run(self):
        """
        Process main function that continuously reads frames from the camera
        """
        # Create a Manager and shared state dict in the child process
        # This ensures thread-safety and proper sharing between processes
        manager = Manager()
        self.shared_state = manager.dict({
            'last_frame_time': 0,
            'fps': 0,
            'frame_count': 0,
            'status': 'initializing'
        })
        
        try:
            # Open the video source
            cap = cv2.VideoCapture(self.source_path)
            if not cap.isOpened():
                self.shared_state['status'] = 'error_opening'
                logger.error(f"Failed to open camera source: {self.source_path}")
                return
            
            # Get camera properties
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            # Default to a reasonable fps if not detected
            if fps <= 0:
                fps = 30.0
            
            # Override with target fps if specified
            if self.target_fps is not None:
                fps = self.target_fps
            
            self.shared_state['fps'] = fps
            frame_delay = 1.0 / fps
            
            # Mark as running
            self.shared_state['status'] = 'running'
            start_time = time.time()
            frame_count = 0
            
            # Main capture loop
            while not self.stop_event.is_set():
                start_capture = time.time()
                
                # Read a frame
                ret, frame = cap.read()
                
                if not ret:
                    self.shared_state['status'] = 'read_error'
                    logger.warning(f"Failed to read frame from source: {self.source_path}")
                    
                    # Handle end of video files by looping
                    if not self.source_path.startswith(('rtsp://', 'http://', 'https://')):
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        time.sleep(0.5)
                        continue
                    else:
                        # For network streams, try to reconnect
                        time.sleep(1.0)
                        cap.release()
                        cap = cv2.VideoCapture(self.source_path)
                        if not cap.isOpened():
                            logger.error(f"Failed to reconnect to source: {self.source_path}")
                            time.sleep(2.0)  # Wait before retrying
                        continue
                
                # Update shared state
                current_time = time.time()
                self.shared_state['last_frame_time'] = current_time
                frame_count += 1
                self.shared_state['frame_count'] = frame_count
                
                # Calculate actual FPS
                elapsed = current_time - start_time
                if elapsed > 1.0:  # Update FPS every second
                    actual_fps = frame_count / elapsed
                    self.shared_state['fps'] = actual_fps
                    start_time = current_time
                    frame_count = 0
                
                # Try to put the frame in the queue, but don't block if it's full
                try:
                    if self.frame_queue.full():
                        # If queue is full, get an item to make space
                        try:
                            # Remove the oldest frame from the queue
                            self.frame_queue.get_nowait()
                            # Log that we're dropping frames only occasionally (not every frame)
                            if frame_count % 30 == 0:  # Log once every 30 frames approximately
                                logger.warning(f"Camera {self.camera_id} queue is full - dropping oldest frame")
                        except queue.Empty:
                            # Queue was full but now is empty - should not happen but handle anyway
                            pass
                    
                    # Put the current frame in the queue
                    self.frame_queue.put_nowait((frame, current_time))
                except Exception as e:
                    # Log more details about the failure
                    if frame_count % 30 == 0:  # Limit logging to avoid spamming
                        logger.warning(f"Failed to put frame in queue for camera {self.camera_id}: {str(e)}")
                        logger.debug(f"Queue state: size={self.frame_queue.qsize()}, full={self.frame_queue.full()}")
                
                # Calculate time to sleep to maintain target FPS
                elapsed_capture = time.time() - start_capture
                
                # Adaptive sleep based on queue fullness
                queue_fullness = self.frame_queue.qsize() / self.max_queue_size
                
                # Base sleep time to maintain FPS
                base_sleep_time = max(0, frame_delay - elapsed_capture)
                
                # Add additional sleep if queue is getting full (over 50% capacity)
                if queue_fullness > 0.5:
                    # Progressively sleep longer as queue fills up
                    adaptive_sleep = min(0.1, base_sleep_time * queue_fullness)
                    sleep_time = base_sleep_time + adaptive_sleep
                    # Periodically log when we're slowing down
                    if frame_count % 60 == 0:
                        logger.debug(f"Camera {self.camera_id} slowing down: queue {queue_fullness:.1%} full, "+
                                    f"added {adaptive_sleep:.3f}s sleep")
                else:
                    sleep_time = base_sleep_time
                
                if sleep_time > 0:
                    time.sleep(sleep_time)
            
            # Clean up
            cap.release()
            self.shared_state['status'] = 'stopped'
            logger.info(f"Camera worker process for camera {self.camera_id} stopped cleanly")
            
        except Exception as e:
            self.shared_state['status'] = f'error: {str(e)}'
            logger.exception(f"Error in camera worker process for camera {self.camera_id}: {e}")
    
    def get_frame(self) -> Optional[Tuple[np.ndarray, float]]:
        """
        Get the latest frame from the queue
        
        Returns:
            Tuple of (frame, timestamp) or None if no frames are available
        """
        if not self._started:
            logger.warning(f"Trying to get frame from camera {self.camera_id} but worker is not started")
            return None
        
        try:
            # Non-blocking get to avoid hanging the application
            return self.frame_queue.get_nowait()
        except queue.Empty:
            # No frames available
            return None
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the status of the camera worker
        
        Returns:
            Dictionary with status information
        """
        # Make a copy of the status to avoid issues with concurrent access
        status_copy = dict(self.shared_state) if hasattr(self, 'shared_state') else {}
        
        return {
            'camera_id': self.camera_id,
            'status': status_copy.get('status', 'unknown'),
            'fps': status_copy.get('fps', 0),
            'last_frame_time': status_copy.get('last_frame_time', 0),
            'frame_count': status_copy.get('frame_count', 0),
            'queue_size': self.frame_queue.qsize() if self._started else 0,
            'running': self._started and not self.stop_event.is_set()
        }


class CameraManager:
    """
    Manages all camera instances and provides an interface to access camera frames
    """
    
    def __init__(self):
        """
        Initialize the camera manager
        """
        # Dictionary to store camera instances
        self.cameras: Dict[int, CameraWorker] = {}
        
        # Dictionary to track which cameras have detection workers
        self.detection_enabled: Dict[int, bool] = {}
        
        # Lock for thread safety
        self.lock = threading.RLock()
    
    def get_camera(self, camera_id: int, source_path: str, enable_detection: bool = False) -> CameraWorker:
        """
        Get or create a camera instance and start it
        
        Args:
            camera_id: ID of the camera
            source_path: Path or URL to the camera source
            enable_detection: Whether to enable detection for this camera
            
        Returns:
            CameraWorker instance
        """
        with self.lock:
            # Check if camera already exists
            if camera_id in self.cameras:
                logger.info(f"Using existing camera worker for camera {camera_id}")
                camera = self.cameras[camera_id]
            else:
                # Create a new camera worker with only picklable parameters
                logger.info(f"Creating new camera worker for camera {camera_id}")
                camera = CameraWorker(
                    camera_id=camera_id, 
                    source_path=source_path
                )
                
                # Store the camera before starting it
                self.cameras[camera_id] = camera
                
                # Start the camera process
                try:
                    camera.start()
                except Exception as e:
                    logger.error(f"Failed to start camera worker for camera {camera_id}: {e}")
                    # Remove from dict if failed
                    del self.cameras[camera_id]
                    raise
                
                # Initialize detection status
                self.detection_enabled[camera_id] = False
            
            # Start detection worker if requested and not already started
            if enable_detection and not self.detection_enabled.get(camera_id, False):
                self._start_detection(camera_id)
            
            return camera
    
    def _start_detection(self, camera_id: int):
        """
        Start a detection worker for the camera
        
        Args:
            camera_id: ID of the camera
        """
        camera = self.cameras.get(camera_id)
        if not camera:
            logger.error(f"Cannot start detection for camera {camera_id}: camera not found")
            return
        
        # Start a detection worker with the camera's frame queue
        try:
            from app.detection_worker import detection_manager
            detection_manager.start_worker(camera_id, camera.frame_queue)
            self.detection_enabled[camera_id] = True
            logger.info(f"Started detection for camera {camera_id}")
        except Exception as e:
            logger.error(f"Failed to start detection for camera {camera_id}: {e}")
    
    def stop_detection(self, camera_id: int):
        """
        Stop detection for a camera
        
        Args:
            camera_id: ID of the camera
        """
        with self.lock:
            if camera_id in self.cameras and self.detection_enabled.get(camera_id, False):
                try:
                    from app.detection_worker import detection_manager
                    detection_manager.stop_worker(camera_id)
                    self.detection_enabled[camera_id] = False
                    logger.info(f"Stopped detection for camera {camera_id}")
                except Exception as e:
                    logger.error(f"Failed to stop detection for camera {camera_id}: {e}")
    
    def get_frame(self, camera_id: int, source_path: str) -> Optional[np.ndarray]:
        """
        Get a single frame from a camera
        
        Args:
            camera_id: ID of the camera
            source_path: Path or URL to the camera source
            
        Returns:
            Frame as a numpy array, or None if reading failed
        """
        with self.lock:
            camera = self.get_camera(camera_id, source_path)
            result = camera.get_frame()
            
            if result is None:
                # Wait a moment for frames to be available
                time.sleep(0.1)
                result = camera.get_frame()
            
            if result is not None:
                frame, _ = result
                return frame
            
            return None
    
    def get_frame_generator(self, camera_id: int, source_path: str, fps: Optional[float] = None):
        """
        Get a generator that yields frames from the camera at the specified FPS
        
        Args:
            camera_id: ID of the camera
            source_path: Path or URL to the camera source
            fps: Target frame rate for the generator (not the capture)
            
        Returns:
            Generator yielding (frame, timestamp) tuples
        """
        camera = self.get_camera(camera_id, source_path)
        
        # Calculate delay based on fps
        delay = 1.0 / (fps or 30.0)
        
        while True:
            start_time = time.time()
            
            # Get the latest frame
            result = camera.get_frame()
            if result is not None:
                frame, timestamp = result
                yield frame, timestamp
            
            # Sleep to maintain target FPS
            elapsed = time.time() - start_time
            sleep_time = max(0, delay - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    def release_camera(self, camera_id: int):
        """
        Release a camera by ID and all associated resources
        
        Args:
            camera_id: ID of the camera to release
        """
        with self.lock:
            try:
                logger.info(f"Releasing camera {camera_id} and associated resources")
                
                # First stop detection if enabled
                detection_was_enabled = self.detection_enabled.get(camera_id, False)
                if detection_was_enabled:
                    logger.info(f"Stopping detection worker for camera {camera_id}")
                    self.stop_detection(camera_id)
                
                # Then stop the camera worker
                if camera_id in self.cameras:
                    logger.info(f"Stopping camera worker {camera_id}")
                    camera_worker = self.cameras[camera_id]
                    
                    # Set stop event and wait briefly
                    camera_worker.stop_event.set()
                    
                    # Try to drain the queue to prevent deadlocks
                    try:
                        while not camera_worker.frame_queue.empty():
                            camera_worker.frame_queue.get_nowait()
                    except Exception as e:
                        logger.warning(f"Error draining frame queue for camera {camera_id}: {e}")
                    
                    # Stop the camera worker process
                    camera_worker.stop()
                    
                    # If process is still alive after stop(), terminate it
                    if camera_worker.is_alive():
                        logger.warning(f"Camera worker {camera_id} did not stop gracefully, terminating")
                        camera_worker.terminate()
                        
                        # Wait a moment for process to terminate
                        camera_worker.join(timeout=1.0)
                        
                        # If still alive after terminate, something is wrong
                        if camera_worker.is_alive():
                            logger.error(f"Camera worker {camera_id} could not be terminated!")
                    
                    # Remove from dictionaries
                    del self.cameras[camera_id]
                    if camera_id in self.detection_enabled:
                        del self.detection_enabled[camera_id]
                    
                    logger.info(f"Camera {camera_id} released successfully")
            except Exception as e:
                logger.exception(f"Error releasing camera {camera_id}: {e}")

    def release_all(self):
        """
        Release all cameras and associated resources
        """
        logger.info("Releasing all cameras and associated resources")
        with self.lock:
            # Get a copy of the keys to avoid modification during iteration
            camera_ids = list(self.cameras.keys())
            for camera_id in camera_ids:
                self.release_camera(camera_id)
            
            # Verify all cameras were released
            remaining = list(self.cameras.keys())
            if remaining:
                logger.warning(f"Some cameras could not be released: {remaining}")
            else:
                logger.info("All cameras released successfully")
            
            # Clear any remaining dictionaries
            self.cameras.clear()
            self.detection_enabled.clear()
    
    def get_camera_status(self, camera_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the status of a camera
        
        Args:
            camera_id: ID of the camera
            
        Returns:
            Dictionary with status information or None if camera not found
        """
        with self.lock:
            if camera_id not in self.cameras:
                return None
            
            status = self.cameras[camera_id].get_status()
            
            # Add detection status if available
            try:
                from app.detection_worker import detection_manager
                detection_status = detection_manager.get_worker_status(camera_id)
                if detection_status:
                    status['detection'] = detection_status
                status['detection_enabled'] = self.detection_enabled.get(camera_id, False)
            except Exception as e:
                logger.warning(f"Failed to get detection status for camera {camera_id}: {e}")
            
            return status
    
    def get_all_cameras_status(self) -> Dict[int, Dict[str, Any]]:
        """
        Get the status of all cameras
        
        Returns:
            Dictionary mapping camera_id to status information
        """
        with self.lock:
            return {camera_id: self.get_camera_status(camera_id) for camera_id in self.cameras}

    def enable_detection(self, camera_id: int) -> bool:
        """
        Enable detection for a camera
        
        Args:
            camera_id: ID of the camera
            
        Returns:
            True if successful, False otherwise
        """
        with self.lock:
            if camera_id not in self.cameras:
                logger.error(f"Cannot enable detection for camera {camera_id}: camera not found")
                return False
            
            # Check if detection is already enabled
            if self.detection_enabled.get(camera_id, False):
                logger.info(f"Detection already enabled for camera {camera_id}")
                return True
            
            # Start detection worker
            try:
                self._start_detection(camera_id)
                return True
            except Exception as e:
                logger.error(f"Failed to enable detection for camera {camera_id}: {e}")
                return False

    def disable_detection(self, camera_id: int) -> bool:
        """
        Disable detection for a camera
        
        Args:
            camera_id: ID of the camera
            
        Returns:
            True if successful, False otherwise
        """
        with self.lock:
            if camera_id not in self.cameras:
                logger.error(f"Cannot disable detection for camera {camera_id}: camera not found")
                return False
            
            # Check if detection is already disabled
            if not self.detection_enabled.get(camera_id, False):
                logger.info(f"Detection already disabled for camera {camera_id}")
                return True
            
            # Stop detection worker
            try:
                self.stop_detection(camera_id)
                return True
            except Exception as e:
                logger.error(f"Failed to disable detection for camera {camera_id}: {e}")
                return False


# Create a singleton instance of the CameraManager
camera_manager = CameraManager() 