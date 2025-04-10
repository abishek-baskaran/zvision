import cv2
import os
from fastapi import APIRouter, HTTPException, Response, Depends
from pydantic import BaseModel
from typing import List, Optional

from app.database.cameras import add_camera, get_cameras_for_store, get_camera_by_id
from app.database.stores import get_store_by_id
from app.database.connection import get_connection
from app.routes.auth import get_current_user
from app.database.calibration import store_calibration, fetch_calibration_for_camera

router = APIRouter()

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
def list_cameras(store_id: Optional[int] = None, current_user: dict = Depends(get_current_user)):
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

    cap = cv2.VideoCapture(source_path)
    if not cap.isOpened():
        raise HTTPException(
            status_code=500,
            detail=f"Failed to open camera/video source '{source_path}'"
        )

    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        raise HTTPException(
            status_code=500,
            detail="Unable to read a frame from the camera/video."
        )

    # Resize the frame before encoding
    frame = _resize_frame(frame)

    success, encoded_img = cv2.imencode(".jpg", frame)
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

@router.get("/camera/feed")
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

    cap = cv2.VideoCapture(source_path)
    if not cap.isOpened():
        raise HTTPException(
            status_code=500,
            detail=f"Failed to open camera/video source '{source_path}'"
        )

    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        raise HTTPException(
            status_code=500,
            detail="Unable to read a frame from the camera/video."
        )

    # Resize the frame before encoding
    frame = _resize_frame(frame)

    success, encoded_img = cv2.imencode(".jpg", frame)
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to encode frame to JPEG."
        )

    return Response(content=encoded_img.tobytes(), media_type="image/jpeg")

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

    cap = cv2.VideoCapture(source_path)
    if not cap.isOpened():
        raise HTTPException(
            status_code=500,
            detail=f"Failed to open camera/video source '{source_path}'"
        )

    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        raise HTTPException(
            status_code=500,
            detail="Unable to read a frame from the camera/video."
        )

    # Resize the frame before encoding
    frame = _resize_frame(frame)

    success, encoded_img = cv2.imencode(".jpg", frame)
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to encode frame to JPEG."
        )

    return Response(content=encoded_img.tobytes(), media_type="image/jpeg")

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