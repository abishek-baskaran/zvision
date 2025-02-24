from pydantic import BaseModel
from typing import List, Tuple

class LineConfig(BaseModel):
    # A line defined by two points (x1,y1) & (x2,y2)
    start: Tuple[float, float]
    end: Tuple[float, float]

class CalibrationData(BaseModel):
    camera_id: str
    lines: List[LineConfig]