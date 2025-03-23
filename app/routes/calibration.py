from fastapi import APIRouter, HTTPException, Query
from typing import Tuple, Optional
from pydantic import BaseModel
from app.database.calibration import store_calibration, fetch_calibration_for_camera

router = APIRouter()

class LineConfig(BaseModel):
    start: Tuple[float, float]
    end: Tuple[float, float]

class SquareConfig(BaseModel):
    top_left: Tuple[float, float]
    bottom_right: Tuple[float, float]

class CalibrationData(BaseModel):
    camera_id: str  # string from frontend, converted to int
    line: LineConfig  # Only one line per camera
    square: SquareConfig  # Only one square per camera

@router.get("/calibrate")
def get_calibrate(camera_id: str = Query(..., description="Camera ID to fetch calibration data")):
    """
    Retrieve calibration data for a specific camera.
    Example Request: GET /api/calibrate?camera_id=1
    """
    try:
        cam_id = int(camera_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid camera_id (must be an integer).")

    calibration_data = fetch_calibration_for_camera(cam_id)
    if not calibration_data:
        raise HTTPException(status_code=404, detail="No calibration data found for this camera.")

    # We have calibration_data as:
    # {
    #   "calibration_id": ...,
    #   "camera_id": ...,
    #   "line": { "line_start_x", "line_start_y", "line_end_x", "line_end_y" },
    #   "square": { "crop_x1", "crop_y1", "crop_x2", "crop_y2" }
    # }

    line_vals = calibration_data["line"]
    square_vals = calibration_data["square"]

    resp_line = {
        "start": [line_vals["line_start_x"], line_vals["line_start_y"]],
        "end":   [line_vals["line_end_x"],   line_vals["line_end_y"]]
    }
    resp_square = {
        "top_left":     [square_vals["crop_x1"], square_vals["crop_y1"]],
        "bottom_right": [square_vals["crop_x2"], square_vals["crop_y2"]]
    }

    return {
        "message": "Calibration data retrieved successfully",
        "calibration": {
            "calibration_id": calibration_data["calibration_id"],
            "camera_id": calibration_data["camera_id"],
            "line": resp_line,
            "square": resp_square
        }
    }

# Add alias route for the same functionality
@router.get("/calibration")
def get_calibration(camera_id: str = Query(..., description="Camera ID to fetch calibration data")):
    """
    Alias for /calibrate endpoint to match API documentation.
    """
    return get_calibrate(camera_id)

@router.post("/calibrate")
def set_calibration(data: CalibrationData):
    """
    Create/update calibration data for a specific camera.
    """
    try:
        cam_id = int(data.camera_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid camera_id (must be integer).")

    x1, y1 = data.line.start
    x2, y2 = data.line.end
    crop_x1, crop_y1 = data.square.top_left
    crop_x2, crop_y2 = data.square.bottom_right


    # Store in DB (replaces existing calibration if it exists)
    store_calibration(cam_id, x1, y1, x2, y2, crop_x1, crop_y1, crop_x2, crop_y2)

    return {
        "message": "Calibration saved successfully",
        "camera_id": cam_id,
        "line": data.line
    }

# Add alias route for the same functionality
@router.post("/calibration")
def post_calibration(data: CalibrationData):
    """
    Alias for /calibrate endpoint to match API documentation.
    """
    return set_calibration(data)
