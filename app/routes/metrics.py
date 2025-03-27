"""
Metrics API endpoints for ZVision.

This module provides endpoints for retrieving system metrics and analytics.
"""

import logging
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Dict, List, Any, Optional

# Import auth for JWT validation
from app.routes.auth import get_current_user, get_optional_user

# Import analytics
from app.analytics import analytics

# Import managers to get status
from app.camera_manager import camera_manager
from app.detection_worker import detection_manager

router = APIRouter()

# Configure logging
logger = logging.getLogger(__name__)

@router.get("/metrics", response_model=Dict[str, Any])
def get_all_metrics(current_user: dict = Depends(get_optional_user)):
    """
    Get metrics for all cameras
    
    Returns a dictionary with system-wide metrics and per-camera metrics.
    """
    try:
        # Get camera metrics
        camera_metrics = analytics.get_all_metrics()
        
        # Get camera status
        camera_status = camera_manager.get_all_cameras_status()
        
        # Get detection worker status
        detection_status = detection_manager.get_all_workers_status()
        
        # Combine everything into a single response
        response = {
            "version": "1.0",
            "timestamp": analytics.last_log_time,
            "cameras": camera_metrics,
            "camera_status": camera_status,
            "detection_status": detection_status
        }
        
        return response
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching metrics: {str(e)}")

@router.get("/metrics/stats")
def get_metrics_no_auth():
    """
    Get metrics for all cameras without authentication for testing purposes.
    
    Returns a dictionary with system-wide metrics and per-camera metrics.
    """
    try:
        # Get camera metrics
        camera_metrics = analytics.get_all_metrics()
        
        # Get camera status
        camera_status = camera_manager.get_all_cameras_status()
        
        # Get detection worker status
        detection_status = detection_manager.get_all_workers_status()
        
        # Add information about data availability
        data_available = bool(camera_metrics) or bool(camera_status) or bool(detection_status)
        
        # Combine everything into a single response
        response = {
            "version": "1.0",
            "timestamp": analytics.last_log_time,
            "cameras": camera_metrics,
            "camera_status": camera_status,
            "detection_status": detection_status,
            "has_data": data_available,
            "message": "Metrics retrieved successfully" if data_available else 
                      "No metrics data available yet. Add a camera and run some detections to generate metrics."
        }
        
        return response
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching metrics: {str(e)}")

@router.get("/metrics/{camera_id}", response_model=Dict[str, Any])
def get_camera_metrics(
    camera_id: int,
    time_window: Optional[int] = Query(None, description="Time window in seconds for metrics"),
    current_user: dict = Depends(get_optional_user)
):
    """
    Get metrics for a specific camera
    
    Args:
        camera_id: ID of the camera
        time_window: Optional time window in seconds (if None, returns all-time metrics)
    
    Returns:
        Dictionary with metrics for the specified camera
    """
    try:
        # Get camera metrics
        metrics = analytics.get_metrics(camera_id)
        
        # Get camera status
        status = camera_manager.get_camera_status(camera_id)
        
        # Get detection worker status
        detection_status = detection_manager.get_worker_status(camera_id)
        
        # If time window is specified, get class detection counts for that window
        if time_window is not None:
            metrics["detection_counts"]["window"] = analytics.get_detections_by_class(camera_id, time_window)
        
        # Combine everything into a single response
        response = {
            "camera_id": camera_id,
            "timestamp": analytics.last_log_time,
            "metrics": metrics,
            "status": status,
            "detection_status": detection_status
        }
        
        return response
    except Exception as e:
        logger.error(f"Error getting metrics for camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching metrics: {str(e)}")

@router.get("/metrics/detections/{camera_id}", response_model=Dict[str, Any])
def get_detection_metrics(
    camera_id: int,
    time_window: Optional[int] = Query(None, description="Time window in seconds for metrics"),
    current_user: dict = Depends(get_optional_user)
):
    """
    Get detection metrics for a specific camera
    
    Args:
        camera_id: ID of the camera
        time_window: Optional time window in seconds (if None, returns all-time metrics)
    
    Returns:
        Dictionary with detection counts by class
    """
    try:
        # Get latest detection result
        latest_detection = detection_manager.get_latest_detection(camera_id)
        
        # Get detection counts
        if time_window is not None:
            class_counts = analytics.get_detections_by_class(camera_id, time_window)
        else:
            class_counts = analytics.get_detections_by_class(camera_id)
        
        # Get detection worker status
        detection_status = detection_manager.get_worker_status(camera_id)
        
        # Prepare response
        response = {
            "camera_id": camera_id,
            "timestamp": analytics.last_log_time,
            "detection_counts": class_counts,
            "detection_status": detection_status,
            "latest_detection": latest_detection.to_dict() if latest_detection else None
        }
        
        return response
    except Exception as e:
        logger.error(f"Error getting detection metrics for camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching metrics: {str(e)}")

@router.get("/metrics/resource", response_model=Dict[str, Any])
def get_resource_metrics(current_user: dict = Depends(get_optional_user)):
    """
    Get system resource metrics
    
    Returns:
        Dictionary with system resource metrics
    """
    try:
        # Try to get system-wide resource usage
        system_metrics = {}
        
        try:
            import psutil
            # Get system-wide metrics
            system_metrics = {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": psutil.virtual_memory().percent,
                "memory_available_mb": psutil.virtual_memory().available / (1024 * 1024),
                "disk_percent": psutil.disk_usage('/').percent
            }
        except ImportError:
            system_metrics = {"error": "psutil not available"}
        
        # Get per-camera resource usage from analytics
        camera_resources = {}
        for camera_id in analytics.memory_usage.keys():
            camera_resources[camera_id] = analytics.get_resource_usage(camera_id)
        
        # Combine everything into a response
        response = {
            "timestamp": analytics.last_log_time,
            "system": system_metrics,
            "cameras": camera_resources
        }
        
        return response
    except Exception as e:
        logger.error(f"Error getting resource metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching resource metrics: {str(e)}") 