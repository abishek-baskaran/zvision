"""
Analytics Module for ZVision

This module tracks performance metrics for the ZVision system, including:
- Frame processing rate (FPS)
- Detection counts by class
- Inference latency
- Camera uptime
- Processed vs. dropped frames
"""

import time
from typing import Dict, Any, Optional, List, Tuple
import logging
from collections import defaultdict, deque
import threading
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class Analytics:
    """
    Tracks performance metrics for the ZVision system
    """
    
    def __init__(self, max_history: int = 100, log_interval: int = 300):
        """
        Initialize the analytics tracker
        
        Args:
            max_history: Maximum number of data points to keep in history
            log_interval: How often to log metrics to console (in seconds)
        """
        self.max_history = max_history
        self.log_interval = log_interval
        self.lock = threading.RLock()
        
        # Performance metrics
        self.frame_times: Dict[int, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self.inference_times: Dict[int, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self.detection_counts: Dict[int, deque] = defaultdict(lambda: deque(maxlen=max_history))
        
        # Frame processing metrics
        self.processed_frames: Dict[int, int] = defaultdict(int)
        self.dropped_frames: Dict[int, int] = defaultdict(int)
        self.skipped_frames: Dict[int, int] = defaultdict(int)
        
        # Class detection counters
        self.detections_per_class: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.detection_history: Dict[int, List[Tuple[float, Dict[str, int]]]] = defaultdict(list)
        
        # API call metrics
        self.api_call_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self.api_call_results: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        
        # Status metrics
        self.camera_status: Dict[int, str] = {}
        self.last_frame_time: Dict[int, float] = {}
        
        # Resource utilization
        self.memory_usage: Dict[int, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self.cpu_usage: Dict[int, deque] = defaultdict(lambda: deque(maxlen=max_history))
        
        # Last log time
        self.last_log_time = time.time()
        
        # Start logging thread
        self.logging_thread = threading.Thread(target=self._periodic_log, daemon=True)
        self.logging_thread.start()
    
    def record_frame(self, camera_id: int, processing_time: float):
        """
        Record frame processing time
        
        Args:
            camera_id: ID of the camera
            processing_time: Time taken to process the frame in seconds
        """
        with self.lock:
            self.frame_times[camera_id].append(processing_time)
            self.last_frame_time[camera_id] = time.time()
            self.camera_status[camera_id] = "online"
            self.processed_frames[camera_id] += 1
    
    def record_dropped_frame(self, camera_id: int, reason: str = "queue_full"):
        """
        Record a dropped frame (frame that couldn't be processed)
        
        Args:
            camera_id: ID of the camera
            reason: Reason for dropping the frame
        """
        with self.lock:
            self.dropped_frames[camera_id] += 1
            if reason == "queue_full":
                self.skipped_frames[camera_id] += 1
    
    def record_inference(self, camera_id: int, inference_time: float, detection_count: int,
                        detections_by_class: Optional[Dict[str, int]] = None):
        """
        Record inference time, detection count, and class distribution
        
        Args:
            camera_id: ID of the camera
            inference_time: Time taken for inference in seconds
            detection_count: Number of objects detected
            detections_by_class: Dictionary mapping class names to counts
        """
        with self.lock:
            self.inference_times[camera_id].append(inference_time)
            self.detection_counts[camera_id].append(detection_count)
            
            if detections_by_class:
                timestamp = time.time()
                # Update total counts
                for class_name, count in detections_by_class.items():
                    self.detections_per_class[camera_id][class_name] += count
                
                # Add to history (with pruning)
                self.detection_history[camera_id].append((timestamp, detections_by_class.copy()))
                # Keep only the last max_history items
                if len(self.detection_history[camera_id]) > self.max_history:
                    self.detection_history[camera_id] = self.detection_history[camera_id][-self.max_history:]
    
    def record_resource_usage(self, camera_id: int, memory_mb: float, cpu_percent: float):
        """
        Record resource usage for a camera process
        
        Args:
            camera_id: ID of the camera
            memory_mb: Memory usage in MB
            cpu_percent: CPU usage as a percentage
        """
        with self.lock:
            self.memory_usage[camera_id].append(memory_mb)
            self.cpu_usage[camera_id].append(cpu_percent)
    
    def record_call(self, camera_id: int, endpoint: str, result: str, execution_time: float):
        """
        Record API call statistics
        
        Args:
            camera_id: ID of the camera
            endpoint: Name of the API endpoint or function
            result: Result status (success, error, etc.)
            execution_time: Time taken to execute the call in seconds
        """
        with self.lock:
            key = f"{camera_id}:{endpoint}"
            self.api_call_times[key].append(execution_time)
            self.api_call_results[key].append(result)
            
            # Log significant delays
            if execution_time > 0.5:  # More than 500ms
                logger.warning(f"Slow API call: {endpoint} for camera {camera_id} took {execution_time:.3f}s")
    
    def get_camera_fps(self, camera_id: int) -> Optional[float]:
        """
        Calculate the average frames per second for a camera
        
        Args:
            camera_id: ID of the camera
            
        Returns:
            Average FPS or None if no data
        """
        with self.lock:
            if not self.frame_times.get(camera_id):
                return None
            
            times = list(self.frame_times[camera_id])
            if not times:
                return None
            
            avg_time = sum(times) / len(times)
            if avg_time <= 0:
                return 0
            
            return 1.0 / avg_time
    
    def get_camera_status(self, camera_id: int) -> str:
        """
        Get the current status of a camera
        
        Args:
            camera_id: ID of the camera
            
        Returns:
            Status string: "online", "offline", or "unknown"
        """
        with self.lock:
            if camera_id not in self.last_frame_time:
                return "unknown"
            
            # Consider camera offline if no frames for 5 seconds
            if time.time() - self.last_frame_time.get(camera_id, 0) > 5:
                return "offline"
            
            return self.camera_status.get(camera_id, "unknown")
    
    def get_frame_processing_stats(self, camera_id: int) -> Dict[str, Any]:
        """
        Get frame processing statistics for a camera
        
        Args:
            camera_id: ID of the camera
            
        Returns:
            Dictionary with frame processing statistics
        """
        with self.lock:
            total_frames = (self.processed_frames.get(camera_id, 0) + 
                           self.dropped_frames.get(camera_id, 0))
            
            return {
                "processed_frames": self.processed_frames.get(camera_id, 0),
                "dropped_frames": self.dropped_frames.get(camera_id, 0),
                "skipped_frames": self.skipped_frames.get(camera_id, 0),
                "total_frames": total_frames,
                "processed_ratio": (self.processed_frames.get(camera_id, 0) / total_frames 
                                  if total_frames > 0 else 0)
            }
    
    def get_detections_by_class(self, camera_id: int, time_window: Optional[float] = None) -> Dict[str, int]:
        """
        Get detection counts by class for a camera
        
        Args:
            camera_id: ID of the camera
            time_window: Optional time window in seconds (if None, returns all-time counts)
            
        Returns:
            Dictionary mapping class names to counts
        """
        with self.lock:
            if time_window is None:
                # Return all-time counts
                return dict(self.detections_per_class.get(camera_id, {}))
            
            # Calculate counts within the time window
            now = time.time()
            cutoff_time = now - time_window
            
            result = defaultdict(int)
            for timestamp, detections in self.detection_history.get(camera_id, []):
                if timestamp >= cutoff_time:
                    for class_name, count in detections.items():
                        result[class_name] += count
            
            return dict(result)
    
    def get_api_metrics(self, camera_id: int, endpoint: str) -> Dict[str, Any]:
        """
        Get metrics for a specific API endpoint
        
        Args:
            camera_id: ID of the camera
            endpoint: Name of the API endpoint
            
        Returns:
            Dictionary of API metrics
        """
        with self.lock:
            key = f"{camera_id}:{endpoint}"
            
            call_times = list(self.api_call_times.get(key, []))
            results = list(self.api_call_results.get(key, []))
            
            if not call_times:
                return {
                    "camera_id": camera_id,
                    "endpoint": endpoint,
                    "data_available": False
                }
            
            avg_time = sum(call_times) / len(call_times)
            
            # Calculate success rate
            success_count = sum(1 for r in results if r == "success")
            success_rate = (success_count / len(results)) if results else 0
            
            return {
                "camera_id": camera_id,
                "endpoint": endpoint,
                "data_available": True,
                "avg_time": avg_time,
                "min_time": min(call_times) if call_times else None,
                "max_time": max(call_times) if call_times else None, 
                "call_count": len(call_times),
                "success_rate": success_rate
            }
    
    def get_resource_usage(self, camera_id: int) -> Dict[str, Any]:
        """
        Get resource usage metrics for a camera
        
        Args:
            camera_id: ID of the camera
            
        Returns:
            Dictionary with resource usage metrics
        """
        with self.lock:
            memory_values = list(self.memory_usage.get(camera_id, []))
            cpu_values = list(self.cpu_usage.get(camera_id, []))
            
            return {
                "memory_mb": {
                    "current": memory_values[-1] if memory_values else None,
                    "average": sum(memory_values) / len(memory_values) if memory_values else None,
                    "max": max(memory_values) if memory_values else None
                },
                "cpu_percent": {
                    "current": cpu_values[-1] if cpu_values else None,
                    "average": sum(cpu_values) / len(cpu_values) if cpu_values else None,
                    "max": max(cpu_values) if cpu_values else None
                }
            }
    
    def get_metrics(self, camera_id: int) -> Dict[str, Any]:
        """
        Get all metrics for a camera
        
        Args:
            camera_id: ID of the camera
            
        Returns:
            Dictionary of metrics
        """
        with self.lock:
            avg_fps = self.get_camera_fps(camera_id)
            
            avg_inference_time = None
            inference_times = list(self.inference_times.get(camera_id, []))
            if inference_times:
                avg_inference_time = sum(inference_times) / len(inference_times)
            
            avg_detection_count = None
            detection_counts = list(self.detection_counts.get(camera_id, []))
            if detection_counts:
                avg_detection_count = sum(detection_counts) / len(detection_counts)
            
            # Get API metrics for common endpoints
            api_metrics = {
                "detect": self.get_api_metrics(camera_id, "detect_all_people")
            }
            
            # Get frame processing stats
            frame_stats = self.get_frame_processing_stats(camera_id)
            
            # Get detection class distribution
            class_counts = self.get_detections_by_class(camera_id)
            
            # Get recent detection counts (last minute)
            recent_class_counts = self.get_detections_by_class(camera_id, 60)
            
            return {
                "camera_id": camera_id,
                "timestamp": time.time(),
                "status": self.get_camera_status(camera_id),
                "fps": avg_fps,
                "avg_inference_time": avg_inference_time,
                "avg_detection_count": avg_detection_count,
                "sample_count": len(self.frame_times.get(camera_id, [])),
                "frame_stats": frame_stats,
                "detection_counts": {
                    "total": class_counts,
                    "last_minute": recent_class_counts
                },
                "api_metrics": api_metrics,
                "resource_usage": self.get_resource_usage(camera_id)
            }
    
    def get_all_metrics(self) -> Dict[int, Dict[str, Any]]:
        """
        Get metrics for all cameras
        
        Returns:
            Dictionary mapping camera_id to metrics
        """
        with self.lock:
            # Gather all camera IDs from various dictionaries
            camera_ids = set()
            camera_ids.update(self.processed_frames.keys())
            camera_ids.update(self.camera_status.keys())
            camera_ids.update(self.detections_per_class.keys())
            
            return {camera_id: self.get_metrics(camera_id) for camera_id in camera_ids}
    
    def _periodic_log(self):
        """
        Periodically log metrics to the console
        """
        while True:
            try:
                now = time.time()
                if now - self.last_log_time >= self.log_interval:
                    self.last_log_time = now
                    self._log_metrics()
                time.sleep(10)  # Check every 10 seconds
            except Exception as e:
                logger.error(f"Error in periodic metrics logging: {e}")
                time.sleep(30)  # Back off on error
    
    def _log_metrics(self):
        """
        Log current metrics to the console
        """
        with self.lock:
            try:
                cameras = list(self.camera_status.keys())
                if not cameras:
                    return
                
                logger.info("=== ZVision Metrics Summary ===")
                
                for camera_id in cameras:
                    fps = self.get_camera_fps(camera_id)
                    status = self.get_camera_status(camera_id)
                    processed = self.processed_frames.get(camera_id, 0)
                    dropped = self.dropped_frames.get(camera_id, 0)
                    
                    logger.info(f"Camera {camera_id}: Status={status}, FPS={fps:.2f if fps else 0}, "
                               f"Processed frames={processed}, Dropped frames={dropped}")
                    
                    # Log detection counts
                    detections = self.detections_per_class.get(camera_id, {})
                    if detections:
                        detection_str = ", ".join([f"{cls}={count}" for cls, count in detections.items()])
                        logger.info(f"  Detections: {detection_str}")
                    
                    # Log resource usage
                    if camera_id in self.memory_usage and self.memory_usage[camera_id]:
                        mem = list(self.memory_usage[camera_id])
                        cpu = list(self.cpu_usage[camera_id]) if camera_id in self.cpu_usage else []
                        
                        if mem:
                            avg_mem = sum(mem) / len(mem)
                            logger.info(f"  Avg Memory: {avg_mem:.1f} MB")
                        
                        if cpu:
                            avg_cpu = sum(cpu) / len(cpu)
                            logger.info(f"  Avg CPU: {avg_cpu:.1f}%")
            
            except Exception as e:
                logger.error(f"Error logging metrics: {e}")

    def save_metrics_summary(self, filepath: str = "zvision_metrics.json"):
        """
        Save a summary of the metrics to a JSON file
        
        Args:
            filepath: Path to the file to save
        """
        try:
            logger.info(f"Saving metrics summary to {filepath}")
            with self.lock:
                # Create a summary dictionary
                summary = {
                    "timestamp": datetime.now().isoformat(),
                    "cameras": {}
                }
                
                # Add metrics for each camera
                for camera_id in self.camera_status.keys():
                    metrics = self.get_metrics(camera_id)
                    
                    # Add additional summary data
                    if camera_id in self.processed_frames:
                        metrics["total_processed_frames"] = self.processed_frames[camera_id]
                    
                    if camera_id in self.dropped_frames:
                        metrics["total_dropped_frames"] = self.dropped_frames[camera_id]
                    
                    if camera_id in self.detections_per_class:
                        metrics["total_detections_by_class"] = self.detections_per_class[camera_id]
                    
                    # Add to summary
                    summary["cameras"][str(camera_id)] = metrics
                
                # Add system-wide metrics
                summary["system"] = {
                    "total_cameras": len(self.camera_status),
                    "uptime": time.time() - self.last_log_time  # approximate uptime since first log
                }
                
                # Write to file
                with open(filepath, 'w') as f:
                    json.dump(summary, f, indent=2)
                
                logger.info("Metrics summary saved successfully")
                return True
        
        except Exception as e:
            logger.error(f"Error saving metrics summary: {e}")
            return False

# Create a singleton instance of the Analytics class
analytics = Analytics() 