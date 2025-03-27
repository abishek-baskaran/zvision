"""
Detection Worker Module for ZVision

This module is responsible for running object detection in a separate process,
allowing the main application to continue serving video frames without blocking.
"""

import time
import logging
from typing import Dict, List, Tuple, Optional, Any
import cv2
import numpy as np
import threading
from multiprocessing import Process, Queue, Event, Manager
import queue
import os
import torch

logger = logging.getLogger(__name__)

# Import the YOLO detection function from the original module
from app.inference.detection import run_yolo_inference

class DetectionResult:
    """Class to store detection results in a structured way"""
    
    def __init__(self, camera_id: int, boxes: List[List[int]], scores: List[float], 
                labels: List[int], timestamp: float):
        """
        Initialize a detection result
        
        Args:
            camera_id: ID of the camera
            boxes: List of bounding boxes, each [x1, y1, x2, y2]
            scores: List of confidence scores
            labels: List of class labels
            timestamp: Time when the detection was performed
        """
        self.camera_id = camera_id
        self.boxes = boxes
        self.scores = scores
        self.labels = labels
        self.timestamp = timestamp
        self.processed_time = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        return {
            "camera_id": self.camera_id,
            "boxes": self.boxes,
            "scores": self.scores,
            "labels": self.labels,
            "timestamp": self.timestamp,
            "processed_time": self.processed_time,
            "latency": self.processed_time - self.timestamp if self.timestamp else 0
        }
    
    def get_filtered_boxes(self, confidence_threshold: float = 0.5) -> List[List[int]]:
        """
        Get boxes filtered by confidence threshold
        
        Args:
            confidence_threshold: Minimum confidence score
            
        Returns:
            List of bounding boxes with confidence above the threshold
        """
        filtered_boxes = []
        for i, box in enumerate(self.boxes):
            if self.scores[i] >= confidence_threshold:
                filtered_boxes.append(box)
        return filtered_boxes
    
    def count_detections(self, confidence_threshold: float = 0.5) -> int:
        """
        Count detections above confidence threshold
        
        Args:
            confidence_threshold: Minimum confidence score
            
        Returns:
            Number of detections
        """
        return len(self.get_filtered_boxes(confidence_threshold))


class DetectionWorker(Process):
    """
    Worker class for running object detection in a separate process.
    
    This class reads frames from a queue, runs detection on them,
    and puts the results into a results queue.
    """
    
    def __init__(self, camera_id: int, frame_queue: Queue, 
                 results_queue: Queue, target_fps: float = 5.0,
                 model_path: str = "./checkpoints/yolov8n.pt"):
        """
        Initialize the detection worker
        
        Args:
            camera_id: ID of the camera
            frame_queue: Queue to read frames from
            results_queue: Queue to put detection results into
            target_fps: Target frames per second for detection
            model_path: Path to the YOLOv8 model file
        """
        super().__init__(daemon=False)  # Changed to non-daemon to support Manager
        self.camera_id = camera_id
        self.frame_queue = frame_queue
        self.results_queue = results_queue
        self.target_fps = target_fps
        self.model_path = model_path
        
        # Event for signaling process termination
        self.stop_event = Event()
        
        # Initialize with a regular dictionary
        self.shared_state = {
            'status': 'initialized',
            'last_detection_time': 0,
            'detection_count': 0,
            'fps': 0
        }
        
        # Status flag
        self._started = False
    
    def start(self):
        """
        Start the detection worker process
        """
        if not self._started:
            self.shared_state['status'] = 'starting'
            super().start()
            self._started = True
            logger.info(f"Started detection worker process for camera {self.camera_id}")
        return self._started
    
    def stop(self):
        """
        Stop the detection worker process
        """
        if self._started:
            self.shared_state['status'] = 'stopping'
            self.stop_event.set()
            self.join(timeout=3.0)  # Wait up to 3 seconds for process to terminate
            logger.info(f"Stopped detection worker process for camera {self.camera_id}")
            self._started = False
    
    def run(self):
        """
        Main process function that runs detection on frames from the queue
        """
        try:
            # Create Manager in the child process
            manager = Manager()
            self.shared_state = manager.dict({
                'status': 'initializing',
                'last_detection_time': 0,
                'detection_count': 0,
                'fps': 0,
                'skipped_frames': 0
            })
            
            # Import modules inside the process to avoid pickling issues
            # This is important especially for analytics which has threading.RLock objects
            from app.analytics import analytics
            import psutil
            
            # Set number of threads for PyTorch to 1 for Raspberry Pi efficiency
            torch.set_num_threads(1)
            
            # In production, we would load the model here
            # Since run_yolo_inference already manages the model, we don't need to load it here
            
            self.shared_state['status'] = 'running'
            
            # Frame processing stats
            frame_count = 0
            start_time = time.time()
            self.shared_state['last_detection_time'] = start_time
            
            # Track dropped frames
            dropped_frames = 0
            
            # Main detection loop
            while not self.stop_event.is_set():
                loop_start = time.time()
                
                # Calculate time to wait to maintain target FPS
                time_since_last = loop_start - self.shared_state['last_detection_time']
                wait_time = max(0, (1.0 / self.target_fps) - time_since_last)
                
                if wait_time > 0:
                    # Sleep to maintain target FPS
                    time.sleep(wait_time)
                
                # Try to get the latest frame from the queue
                try:
                    # Clear the queue to get the latest frame
                    latest_frame = None
                    latest_timestamp = 0
                    skipped_frames = 0
                    frames_retrieved = 0
                    queue_size_before = 0
                    
                    try:
                        # Check queue size before we start emptying it
                        queue_size_before = self.frame_queue.qsize()
                        
                        # Non-blocking get with timeout - we'll try a few times to drain the queue
                        start_drain = time.time()
                        
                        # Limit how long we spend draining the queue (50ms max)
                        while time.time() - start_drain < 0.05 and frames_retrieved < 10:
                            frame, timestamp = self.frame_queue.get(timeout=0.01)
                            frames_retrieved += 1
                            
                            if latest_frame is not None:
                                # Count frames we skip when draining the queue
                                skipped_frames += 1
                            latest_frame = frame
                            latest_timestamp = timestamp
                    except queue.Empty:
                        # Queue is empty, which is expected
                        pass
                    
                    # Periodically log queue stats to help with debugging
                    if frame_count % 30 == 0 and frame_count > 0:
                        queue_size_after = self.frame_queue.qsize()
                        logger.debug(f"Camera {self.camera_id} queue stats: before={queue_size_before}, " +
                                     f"after={queue_size_after}, retrieved={frames_retrieved}, skipped={skipped_frames}")
                    
                    # Record skipped frames in analytics
                    if skipped_frames > 0:
                        analytics.record_dropped_frame(self.camera_id, reason="skipped_for_latest")
                        self.shared_state['skipped_frames'] = self.shared_state.get('skipped_frames', 0) + skipped_frames
                    
                    # If we didn't get a frame, wait and retry
                    if latest_frame is None:
                        time.sleep(0.1)
                        continue
                    
                    # Start timing inference
                    detection_start = time.time()
                    self.shared_state['last_detection_time'] = detection_start
                    
                    # Run detection
                    boxes, scores, labels = run_yolo_inference(latest_frame)
                    
                    # Calculate inference time
                    inference_time = time.time() - detection_start
                    
                    # Count detections by class
                    detections_by_class = {}
                    for i, label_id in enumerate(labels):
                        if scores[i] >= 0.5:  # Only count confident detections
                            # Convert numeric label to name (could use a class mapping)
                            label_name = f"class_{label_id}"
                            detections_by_class[label_name] = detections_by_class.get(label_name, 0) + 1
                    
                    # Create detection result
                    detection_result = DetectionResult(
                        camera_id=self.camera_id,
                        boxes=boxes,
                        scores=scores,
                        labels=labels,
                        timestamp=latest_timestamp
                    )
                    
                    # Put the result in the results queue
                    # Don't block if queue is full (discard old results)
                    try:
                        if self.results_queue.full():
                            try:
                                # Get an item to make space
                                self.results_queue.get_nowait()
                                dropped_frames += 1
                                self.shared_state['dropped_frames'] = dropped_frames
                                # Record dropped frame in analytics
                                analytics.record_dropped_frame(self.camera_id, reason="queue_full")
                            except queue.Empty:
                                pass
                        self.results_queue.put_nowait(detection_result)
                    except:
                        logger.warning(f"Failed to put detection result in queue for camera {self.camera_id}")
                    
                    # Record analytics with class distribution
                    detection_count = detection_result.count_detections(0.5)
                    analytics.record_inference(
                        self.camera_id, 
                        inference_time, 
                        detection_count,
                        detections_by_class
                    )
                    
                    # Try to record resource usage
                    try:
                        # This is a lightweight way to get process resource usage
                        process = psutil.Process(os.getpid())
                        memory_info = process.memory_info()
                        memory_mb = memory_info.rss / (1024 * 1024)  # RSS in MB
                        cpu_percent = process.cpu_percent(interval=0.1)
                        
                        analytics.record_resource_usage(self.camera_id, memory_mb, cpu_percent)
                        
                        # Update shared state with resource usage
                        self.shared_state['memory_mb'] = memory_mb
                        self.shared_state['cpu_percent'] = cpu_percent
                    except:
                        # Ignore if psutil is not available
                        pass
                    
                    # Update stats
                    frame_count += 1
                    self.shared_state['detection_count'] = frame_count
                    self.shared_state['frames_processed'] = frame_count
                    self.shared_state['frames_dropped'] = dropped_frames
                    
                    # Calculate FPS every second
                    elapsed = time.time() - start_time
                    if elapsed >= 1.0:
                        self.shared_state['fps'] = frame_count / elapsed
                        frame_count = 0
                        start_time = time.time()
                    
                except Exception as e:
                    logger.error(f"Error in detection loop: {e}")
                    time.sleep(0.5)  # Sleep to avoid tight loop on error
            
            # Clean up
            self.shared_state['status'] = 'stopped'
            logger.info(f"Detection worker for camera {self.camera_id} stopped cleanly")
        
        except Exception as e:
            self.shared_state['status'] = f'error: {str(e)}'
            logger.exception(f"Error in detection worker for camera {self.camera_id}: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the status of the detection worker
        
        Returns:
            Dictionary with status information
        """
        return {
            'camera_id': self.camera_id,
            'status': self.shared_state.get('status', 'unknown'),
            'fps': self.shared_state.get('fps', 0),
            'last_detection_time': self.shared_state.get('last_detection_time', 0),
            'detection_count': self.shared_state.get('detection_count', 0),
            'frames_processed': self.shared_state.get('frames_processed', 0),
            'frames_dropped': self.shared_state.get('dropped_frames', 0),
            'frames_skipped': self.shared_state.get('skipped_frames', 0),
            'memory_mb': self.shared_state.get('memory_mb', 0),
            'cpu_percent': self.shared_state.get('cpu_percent', 0),
            'running': self._started and not self.stop_event.is_set()
        }


class DetectionManager:
    """
    Manages object detection processes
    """
    
    def __init__(self, max_queue_size: int = 10, target_fps: float = 5.0):
        """
        Initialize the detection manager
        
        Args:
            max_queue_size: Maximum size of the results queue
            target_fps: Target frames per second for detection
        """
        self.max_queue_size = max_queue_size
        self.target_fps = target_fps
        
        # Dictionary to store detection workers
        self.workers: Dict[int, DetectionWorker] = {}
        
        # Dictionary to store frame queues (shared with CameraWorker)
        self.frame_queues: Dict[int, Queue] = {}
        
        # Dictionary to store results queues
        self.results_queues: Dict[int, Queue] = {}
        
        # Dictionary to store latest detection results
        self.latest_results: Dict[int, DetectionResult] = {}
        
        # Lock for thread safety
        self.lock = threading.RLock()
        
        # Result processor thread
        self.result_processor_thread = None
        self.running = False
    
    def start(self):
        """
        Start the detection manager and result processor thread
        """
        with self.lock:
            if not self.running:
                self.running = True
                self.result_processor_thread = threading.Thread(
                    target=self._process_results,
                    daemon=True
                )
                self.result_processor_thread.start()
                logger.info("Started detection manager")
    
    def stop(self):
        """
        Stop the detection manager and all workers
        """
        logger.info("Stopping detection manager and all workers")
        with self.lock:
            # Signal all threads to stop
            self.running = False
            
            # Stop all workers with a timeout
            for camera_id in list(self.workers.keys()):
                try:
                    logger.info(f"Stopping detection worker for camera {camera_id}")
                    self.stop_worker(camera_id)
                except Exception as e:
                    logger.error(f"Error stopping worker for camera {camera_id}: {e}")
            
            # Wait for result processor thread to finish
            if self.result_processor_thread and self.result_processor_thread.is_alive():
                logger.info("Waiting for result processor thread to finish")
                self.result_processor_thread.join(timeout=2.0)
                if self.result_processor_thread.is_alive():
                    logger.warning("Result processor thread did not terminate cleanly")
                self.result_processor_thread = None
            
            # Clean up any remaining resources
            try:
                # Drain all queues to prevent deadlocks
                for camera_id, queue_obj in list(self.results_queues.items()):
                    try:
                        while not queue_obj.empty():
                            queue_obj.get_nowait()
                    except Exception:
                        pass
                
                # Clear dictionaries
                self.latest_results.clear()
                self.results_queues.clear()
                self.frame_queues.clear()
                
                # Verify all workers are stopped
                if self.workers:
                    logger.warning(f"Some workers could not be stopped: {list(self.workers.keys())}")
                    # Force close any remaining workers
                    for camera_id, worker in list(self.workers.items()):
                        try:
                            if worker.is_alive():
                                logger.warning(f"Forcefully terminating worker for camera {camera_id}")
                                worker.terminate()
                                worker.join(timeout=1.0)
                        except Exception as e:
                            logger.error(f"Error terminating worker for camera {camera_id}: {e}")
                    self.workers.clear()
            except Exception as e:
                logger.exception(f"Error during cleanup: {e}")
            
            logger.info("Detection manager stopped")
    
    def start_worker(self, camera_id: int, frame_queue: Queue) -> DetectionWorker:
        """
        Start a detection worker for a camera
        
        Args:
            camera_id: ID of the camera
            frame_queue: Queue to read frames from
            
        Returns:
            DetectionWorker instance
        """
        with self.lock:
            # First stop any existing worker
            if camera_id in self.workers:
                self.stop_worker(camera_id)
            
            # Create results queue if it doesn't exist
            if camera_id not in self.results_queues:
                self.results_queues[camera_id] = Queue(maxsize=self.max_queue_size)
            
            # Store the frame queue
            self.frame_queues[camera_id] = frame_queue
            
            # Create and start the worker
            worker = DetectionWorker(
                camera_id=camera_id,
                frame_queue=frame_queue,
                results_queue=self.results_queues[camera_id],
                target_fps=self.target_fps
            )
            worker.start()
            self.workers[camera_id] = worker
            
            logger.info(f"Started detection worker for camera {camera_id}")
            return worker
    
    def stop_worker(self, camera_id: int):
        """
        Stop a detection worker and clean up resources
        
        Args:
            camera_id: ID of the camera
        """
        with self.lock:
            if camera_id in self.workers:
                worker = self.workers[camera_id]
                
                try:
                    # Signal the worker to stop
                    logger.info(f"Signaling detection worker {camera_id} to stop")
                    worker.stop_event.set()
                    
                    # Try to drain the results queue to prevent deadlocks
                    if camera_id in self.results_queues:
                        try:
                            results_queue = self.results_queues[camera_id]
                            while not results_queue.empty():
                                results_queue.get_nowait()
                        except Exception as e:
                            logger.warning(f"Error draining results queue for camera {camera_id}: {e}")
                    
                    # Call stop method to join the process with timeout
                    worker.stop()
                    
                    # If process is still alive after stop(), terminate it
                    if worker.is_alive():
                        logger.warning(f"Detection worker {camera_id} did not stop gracefully, terminating")
                        worker.terminate()
                        worker.join(timeout=1.0)
                        
                        if worker.is_alive():
                            logger.error(f"Detection worker {camera_id} could not be terminated!")
                    
                    # Remove from dictionaries
                    del self.workers[camera_id]
                    logger.info(f"Detection worker for camera {camera_id} stopped")
                    
                except Exception as e:
                    logger.exception(f"Error stopping detection worker {camera_id}: {e}")
                    # Try to remove from dictionary even if there was an error
                    if camera_id in self.workers:
                        del self.workers[camera_id]
    
    def _process_results(self):
        """
        Process detection results from all queues
        """
        logger.info("Starting result processor thread")
        
        while self.running:
            try:
                # Check all results queues
                for camera_id, results_queue in self.results_queues.items():
                    try:
                        # Non-blocking get from queue
                        result = results_queue.get_nowait()
                        
                        # Store the latest result
                        with self.lock:
                            self.latest_results[camera_id] = result
                    
                    except queue.Empty:
                        pass
                
                # Sleep to avoid tight loop
                time.sleep(0.01)
            
            except Exception as e:
                logger.error(f"Error processing detection results: {e}")
                time.sleep(0.5)  # Sleep longer on error
    
    def get_latest_detection(self, camera_id: int) -> Optional[DetectionResult]:
        """
        Get the latest detection result for a camera
        
        Args:
            camera_id: ID of the camera
            
        Returns:
            Latest detection result or None if no results available
        """
        with self.lock:
            return self.latest_results.get(camera_id)
    
    def detect_objects(self, frame: np.ndarray) -> Tuple[List, List, List]:
        """
        Detect objects in a frame directly (without using a worker)
        
        This method is maintained for backward compatibility with Phase 1/2.
        
        Args:
            frame: Frame as a numpy array
            
        Returns:
            Tuple of (boxes, scores, labels)
        """
        # Call the original function directly
        return run_yolo_inference(frame)
    
    def get_worker_status(self, camera_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the status of a detection worker
        
        Args:
            camera_id: ID of the camera
            
        Returns:
            Status dictionary or None if worker not found
        """
        with self.lock:
            if camera_id in self.workers:
                return self.workers[camera_id].get_status()
            return None
    
    def get_all_workers_status(self) -> Dict[int, Dict[str, Any]]:
        """
        Get the status of all detection workers
        
        Returns:
            Dictionary mapping camera_id to status
        """
        with self.lock:
            return {camera_id: worker.get_status() for camera_id, worker in self.workers.items()}


# Create a singleton instance of the DetectionManager
detection_manager = DetectionManager()
detection_manager.start() 