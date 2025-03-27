import cv2
import os
import logging
from fastapi import APIRouter, HTTPException, Response, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

from app.database.cameras import add_camera, get_cameras_for_store, get_camera_by_id
from app.database.stores import get_store_by_id
from app.database.connection import get_connection
from app.routes.auth import get_current_user, get_optional_user
from app.database.calibration import store_calibration, fetch_calibration_for_camera

# Import the new camera manager
from app.camera_manager import camera_manager

router = APIRouter()
# Configure logging
logger = logging.getLogger(__name__)

class CameraCreate(BaseModel):
    store_id: int
    camera_name: str
    source: str  # RTSP link or local file

class CameraResponse(BaseModel):
    camera_id: int
    store_id: int
    camera_name: str
    source: str
    status: str = "online"  # Placeholder status 

class ROI(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float

class Line(BaseModel):
    startX: float
    startY: float
    endX: float
    endY: float

class CalibrationData(BaseModel):
    roi: ROI
    line: Line
    orientation: str = "leftToRight"  # Default value if not provided
    frame_rate: int = 5  # Default value of 5 FPS if not provided

# Direct camera management endpoints (no authentication required)
class CameraAddRequest(BaseModel):
    camera_id: int
    source: str
    enable_detection: bool = False

@router.post("/cameras", response_model=CameraResponse)
def create_camera(cam_data: CameraCreate, current_user: dict = Depends(get_current_user)):
    """
    Create a camera in the DB, referencing a store_id.
    """
    store = get_store_by_id(cam_data.store_id)
    if not store:
        raise HTTPException(status_code=400, detail="Invalid store_id; store not found.")

    camera_id = add_camera(cam_data.store_id, cam_data.camera_name, cam_data.source)
    
    # Return full camera object with the created camera_id
    return CameraResponse(
        camera_id=camera_id,
        store_id=cam_data.store_id,
        camera_name=cam_data.camera_name,
        source=cam_data.source
    )

@router.get("/cameras", response_model=List[CameraResponse])
def list_cameras(store_id: Optional[int] = None, current_user: dict = Depends(get_optional_user)):
    """
    List cameras, optionally filtered by store_id.
    """
    if store_id is None:
        # Optionally, implement a get_all_cameras() if you want to return everything
        # For now, let's enforce store_id param:
        raise HTTPException(status_code=400, detail="You must supply store_id to list cameras for that store.")

    cameras = get_cameras_for_store(store_id)
    camera_list = []
    
    # Convert to CameraResponse objects and add status field
    for camera in cameras:
        # Add status field for frontend compatibility
        camera["status"] = "online"
        camera_list.append(CameraResponse(**camera))
            
    return camera_list

@router.get("/stores/{store_id}/cameras", response_model=List[CameraResponse])
def get_cameras_for_store_endpoint(store_id: int, current_user: dict = Depends(get_current_user)):
    """
    List all cameras for a specific store.
    """
    # First check if store exists
    store = get_store_by_id(store_id)
    if not store:
        raise HTTPException(status_code=404, detail=f"Store with ID {store_id} not found")
    
    cameras = get_cameras_for_store(store_id)
    camera_list = []
    
    # Convert to CameraResponse objects and add status field
    for camera in cameras:
        # Add status field for frontend compatibility
        camera["status"] = "online"
        camera_list.append(CameraResponse(**camera))
            
    return camera_list

@router.get("/cameras/{camera_id}", response_model=CameraResponse)
def get_camera_by_id_endpoint(camera_id: int, current_user: dict = Depends(get_current_user)):
    """
    Get a specific camera by ID.
    """
    camera = get_camera_by_id(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera with ID {camera_id} not found")
    
    # Add status field for frontend compatibility
    camera["status"] = "online"
    return CameraResponse(**camera)

def _resize_frame(frame, max_height=500):
    """
    Resize a frame to exactly the specified height while maintaining aspect ratio.
    
    Args:
        frame: The input frame (numpy array)
        max_height: Target height in pixels (default: 500)
        
    Returns:
        Resized frame
    """
    height, width = frame.shape[:2]
    
    # Always resize to the target height, whether upscaling or downscaling
    aspect_ratio = width / height
    new_height = max_height
    new_width = int(new_height * aspect_ratio)
    return cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)

@router.get("/camera/{camera_id}/snapshot")
def get_camera_snapshot(camera_id: int, current_user: dict = Depends(get_current_user)):
    """
    Returns a single frame (image) from the chosen camera/video source.
    This can be used by the front-end to display a reference snapshot for calibration.
    """
    source_path = _fetch_camera_source_by_id(camera_id)
    if not source_path:
        raise HTTPException(
            status_code=404,
            detail=f"No camera found for camera_id={camera_id} in DB"
        )

    # Use the camera manager to get a frame
    frame = camera_manager.get_frame(camera_id, source_path)
    if frame is None:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read frame from camera/video source '{source_path}'"
        )

    # Resize the frame before encoding
    frame = _resize_frame(frame)

    success, encoded_img = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to encode frame to JPEG."
        )

    return Response(content=encoded_img.tobytes(), media_type="image/jpeg")

@router.get("/cameras/{camera_id}/snapshot")
def get_camera_snapshot_plural(camera_id: int, current_user: dict = Depends(get_current_user)):
    """
    Alias endpoint that matches the plural 'cameras' pattern used in other endpoints.
    Returns a single frame (image) from the chosen camera/video source.
    """
    return get_camera_snapshot(camera_id, current_user)

@router.get("/camera/{camera_id}/feed")
def get_camera_feed(camera_id: int, current_user: dict = Depends(get_current_user)):
    """
    Returns a live feed from the camera as a JPEG stream.
    This matches the API documentation.
    """
    source_path = _fetch_camera_source_by_id(camera_id)
    if not source_path:
        raise HTTPException(
            status_code=404,
            detail=f"No camera found for camera_id={camera_id} in DB"
        )

    # Define a streaming generator using camera_manager
    def generate_frames():
        # Get a frame generator from the camera manager
        # This yields frames at a controlled rate
        frame_gen = camera_manager.get_frame_generator(camera_id, source_path, fps=15)
        
        for frame, _ in frame_gen:
            # Resize each frame before encoding
            frame = _resize_frame(frame)
            
            # Encode to JPEG
            success, encoded_img = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not success:
                continue
            
            # Format for MJPEG streaming
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + encoded_img.tobytes() + b'\r\n')

    # Return a streaming response with the MJPEG generator
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@router.delete("/cameras/{camera_id}")
def delete_camera(camera_id: int, current_user: dict = Depends(get_current_user)):
    """
    Delete a camera by ID.
    """
    # First check if camera exists
    camera = get_camera_by_id(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera with ID {camera_id} not found")
    
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM cameras WHERE camera_id = ?', (camera_id,))
    conn.commit()
    conn.close()
    
    return {"message": f"Camera {camera_id} deleted successfully"}

def _fetch_camera_source_by_id(camera_id: int) -> Optional[str]:
    """
    Helper function to fetch the 'source' field from the cameras table.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT source FROM cameras WHERE camera_id=?', (camera_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0]
    return None

@router.post("/cameras/{camera_id}/calibrate")
def set_camera_calibration(
    camera_id: int, 
    calibration_data: CalibrationData, 
    current_user: dict = Depends(get_current_user)
):
    """
    Set calibration data (ROI and line) for a specific camera.
    
    Example request:
    ```
    POST /api/cameras/1/calibrate
    {
      "roi": { "x1": 100, "y1": 100, "x2": 500, "y2": 400 },
      "line": {
        "startX": 200,
        "startY": 300,
        "endX": 400,
        "endY": 300
      },
      "orientation": "leftToRight",  // or "rightToLeft"
      "frame_rate": 5  // frames per second for detection
    }
    ```
    """
    # First check if camera exists
    camera = get_camera_by_id(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera with ID {camera_id} not found")
    
    # Extract values from the request body
    roi = calibration_data.roi
    line = calibration_data.line
    orientation = calibration_data.orientation
    frame_rate = calibration_data.frame_rate
    
    # Validate orientation
    if orientation not in ["leftToRight", "rightToLeft"]:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid orientation value: {orientation}. Valid values are 'leftToRight' or 'rightToLeft'"
        )
    
    # Validate frame_rate
    if frame_rate <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid frame_rate value: {frame_rate}. Value must be greater than 0."
        )
    
    # Store calibration in database
    store_calibration(
        camera_id, 
        line.startX, line.startY, line.endX, line.endY,
        roi.x1, roi.y1, roi.x2, roi.y2,
        orientation,
        frame_rate
    )
    
    return {
        "message": "Calibration data saved successfully",
        "camera_id": camera_id,
        "roi": {
            "x1": roi.x1,
            "y1": roi.y1,
            "x2": roi.x2,
            "y2": roi.y2
        },
        "line": {
            "startX": line.startX,
            "startY": line.startY,
            "endX": line.endX,
            "endY": line.endY
        },
        "orientation": orientation,
        "frame_rate": frame_rate
    }

@router.get("/cameras/{camera_id}/calibrate")
def get_camera_calibration(
    camera_id: int, 
    current_user: dict = Depends(get_current_user)
):
    """
    Get calibration data (ROI and line) for a specific camera.
    If no calibration exists, return null values.
    
    Example response:
    ```
    {
      "camera_id": 1,
      "roi": { "x1": 100, "y1": 100, "x2": 500, "y2": 400 },
      "line": {
        "startX": 200,
        "startY": 300,
        "endX": 400,
        "endY": 300
      },
      "orientation": "leftToRight",
      "frame_rate": 5
    }
    ```
    
    Or if no calibration exists:
    ```
    {
      "camera_id": 1,
      "roi": null,
      "line": null,
      "orientation": null,
      "frame_rate": null
    }
    ```
    """
    # First check if camera exists
    camera = get_camera_by_id(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera with ID {camera_id} not found")
    
    # Get calibration from database
    calibration_data = fetch_calibration_for_camera(camera_id)
    
    if not calibration_data:
        # Return empty/null calibration if none exists
        return {
            "camera_id": camera_id,
            "roi": None,
            "line": None,
            "orientation": None,
            "frame_rate": None
        }
    
    # Transform the database format to the frontend format
    line_data = calibration_data["line"]
    roi_data = calibration_data["square"]  # Square is used for ROI in the database
    orientation = calibration_data.get("orientation", "leftToRight")  # Default if not in DB
    frame_rate = calibration_data.get("frame_rate", 5)  # Default to 5 if not in DB
    
    return {
        "camera_id": camera_id,
        "roi": {
            "x1": roi_data["crop_x1"],
            "y1": roi_data["crop_y1"],
            "x2": roi_data["crop_x2"],
            "y2": roi_data["crop_y2"]
        },
        "line": {
            "startX": line_data["line_start_x"],
            "startY": line_data["line_start_y"],
            "endX": line_data["line_end_x"],
            "endY": line_data["line_end_y"]
        },
        "orientation": orientation,
        "frame_rate": frame_rate
    }

@router.get("/cameras/{camera_id}/feed")
def get_camera_feed_plural(camera_id: int, current_user: dict = Depends(get_current_user)):
    """
    Alias endpoint that matches the plural 'cameras' pattern used in other endpoints.
    Returns a live feed from the camera as a JPEG stream.
    """
    return get_camera_feed(camera_id, current_user)

@router.get("/cameras/{camera_id}/status")
def get_camera_status(camera_id: int, current_user: dict = Depends(get_current_user)):
    """
    Get the status of a camera including FPS, connection state, and frame queue size.
    
    Returns:
        JSON object with camera status information
    """
    # First check if camera exists in database
    camera = get_camera_by_id(camera_id)
    if not camera:
        raise HTTPException(status_code=404, detail=f"Camera with ID {camera_id} not found")
    
    # Get status from camera manager
    status = camera_manager.get_camera_status(camera_id)
    if not status:
        # Camera exists in DB but not in the manager (not initialized yet)
        return {
            "camera_id": camera_id,
            "status": "not_initialized",
            "fps": 0,
            "queue_size": 0,
            "running": False,
            "source": camera.get("source", "unknown")
        }
    
    # Add camera source info
    status["source"] = camera.get("source", "unknown")
    
    return status

@router.get("/cameras/status")
def get_all_cameras_status(current_user: dict = Depends(get_current_user)):
    """
    Get status information for all active cameras.
    
    Returns:
        List of camera status objects
    """
    # Get all camera statuses from manager
    statuses = camera_manager.get_all_cameras_status()
    
    # Convert to a list
    return list(statuses.values())

@router.get("/camera/list")
def list_active_cameras():
    """
    List all active cameras managed by the camera_manager.
    Does not require authentication for testing.
    """
    cameras = []
    for camera_id, camera in camera_manager.cameras.items():
        cameras.append({
            "camera_id": camera_id,
            "source": camera.source_path,
            "status": camera_manager.get_camera_status(camera_id)
        })
    
    # If no cameras are available, return a more informative response
    if not cameras:
        return {
            "cameras": [],
            "count": 0,
            "message": "No active cameras found. Use the /api/camera/add endpoint to add a camera."
        }
    
    return {
        "cameras": cameras,
        "count": len(cameras),
        "message": "Active cameras retrieved successfully"
    }

@router.post("/camera/add")
def add_camera_direct(camera_data: CameraAddRequest):
    """
    Add a camera directly to the camera_manager.
    Does not require authentication for testing.
    """
    try:
        camera = camera_manager.get_camera(
            camera_data.camera_id, 
            camera_data.source,
            enable_detection=camera_data.enable_detection
        )
        
        # Get the camera status to verify it started properly
        status = camera_manager.get_camera_status(camera_data.camera_id)
        
        return {
            "camera_id": camera_data.camera_id,
            "source": camera_data.source,
            "status": status.get("status", "starting"),
            "detection_enabled": camera_data.enable_detection,
            "message": "Camera added successfully"
        }
        
    except Exception as e:
        # Log the error and return a meaningful response
        logger.error(f"Failed to add camera: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to add camera: {str(e)}"
        )

@router.get("/camera/{camera_id}/status")
def get_camera_status_direct(camera_id: int):
    """
    Get status of a specific camera from the camera_manager.
    Does not require authentication for testing.
    """
    status = camera_manager.get_camera_status(camera_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
    
    return status

@router.get("/camera/{camera_id}/enable_detection")
def enable_camera_detection(camera_id: int):
    """
    Enable detection for a specific camera.
    Does not require authentication for testing.
    """
    # Check if camera exists
    if camera_id not in camera_manager.cameras:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
    
    try:
        success = camera_manager.enable_detection(camera_id)
        if success:
            return {"camera_id": camera_id, "status": "detection_enabled", "message": "Detection enabled successfully"}
        else:
            return {"camera_id": camera_id, "status": "error", "message": "Failed to enable detection"}
    except Exception as e:
        logger.error(f"Failed to enable detection for camera {camera_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to enable detection: {str(e)}")

@router.get("/camera/{camera_id}/disable_detection")
def disable_camera_detection(camera_id: int):
    """
    Disable detection for a specific camera.
    Does not require authentication for testing.
    """
    # Check if camera exists
    if camera_id not in camera_manager.cameras:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
    
    try:
        success = camera_manager.disable_detection(camera_id)
        if success:
            return {"camera_id": camera_id, "status": "detection_disabled", "message": "Detection disabled successfully"}
        else:
            return {"camera_id": camera_id, "status": "error", "message": "Failed to disable detection"}
    except Exception as e:
        logger.error(f"Failed to disable detection for camera {camera_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to disable detection: {str(e)}")

@router.get("/camera/{camera_id}/detection/status")
def get_camera_detection_status(camera_id: int):
    """
    Get detection status for a specific camera.
    Does not require authentication for testing.
    """
    # Check if camera exists
    if camera_id not in camera_manager.cameras:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
    
    try:
        # Get camera status which includes detection information
        status = camera_manager.get_camera_status(camera_id)
        
        # Extract detection-specific information
        detection_enabled = status.get('detection_enabled', False)
        detection_status = status.get('detection', {})
        
        return {
            "camera_id": camera_id,
            "detection_enabled": detection_enabled,
            "detection_status": detection_status
        }
    except Exception as e:
        logger.error(f"Failed to get detection status for camera {camera_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get detection status: {str(e)}")