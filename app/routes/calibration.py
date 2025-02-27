from fastapi import APIRouter, HTTPException
from typing import List, Tuple
from pydantic import BaseModel
from app.database.calibration import store_calibration

router = APIRouter()

class LineConfig(BaseModel):
    start: Tuple[float, float]
    end: Tuple[float, float]

class CalibrationData(BaseModel):
    camera_id: str  # string from the front end, we'll convert to int
    lines: List[LineConfig]

@router.get("/calibrate")
def get_calibrate():
    """
    Placeholder: retrieve or display current calibration data if needed.
    """
    return {"message": "Placeholder for GET /calibrate."}

@router.post("/calibrate")
def set_calibration(data: CalibrationData):
    """
    Create/update calibration data for a specific camera.

    Example:
    {
      "camera_id": "1",
      "lines": [
        {"start": [100, 200], "end": [300, 400]}
      ]
    }
    """
    # Convert camera_id to integer
    try:
        cam_id = int(data.camera_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid camera_id (must be integer).")

    if not data.lines:
        raise HTTPException(status_code=400, detail="No lines provided.")

    line = data.lines[0]
    x1, y1 = line.start
    x2, y2 = line.end

    # Store in DB
    store_calibration(cam_id, x1, y1, x2, y2)

    return {
        "message": "Calibration saved successfully",
        "camera_id": cam_id,
        "lines": data.lines
    }
