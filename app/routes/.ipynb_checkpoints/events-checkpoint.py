from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.database import add_event, get_all_stores

router = APIRouter()

class EventCreate(BaseModel):
    store_id: int
    event_type: str
    clip_path: Optional[str] = None
    timestamp: Optional[str] = None  # e.g. "2025-02-20 12:00:00"

@router.post("/events")
def create_event(event: EventCreate):
    """
    Receives new event data (entry/exit, timestamp, clip path) and inserts into DB.
    Returns a success or error message.
    """

    # 1. Validate the store exists
    try:
        stores = get_all_stores()
    except RuntimeError as db_err:
        raise HTTPException(status_code=500, detail=str(db_err))

    valid_store_ids = [s["store_id"] for s in stores]
    if event.store_id not in valid_store_ids:
        raise HTTPException(status_code=400, detail=f"Invalid store_id: {event.store_id}")

    # 2. Validate event_type if you want to restrict it (optional)
    allowed_types = ["entry", "exit"]
    if event.event_type not in allowed_types:
        raise HTTPException(status_code=400, detail="event_type must be 'entry' or 'exit'")

    # 3. If timestamp is None, fill with current time
    if not event.timestamp:
        event.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 4. Insert into DB
    try:
        new_id = add_event(
            store_id=event.store_id,
            event_type=event.event_type,
            clip_path=event.clip_path if event.clip_path else "",
            timestamp=event.timestamp
        )
        return {"status": "success", "event_id": new_id}
    except RuntimeError as e:
        # re-raise as an HTTPException
        raise HTTPException(status_code=500, detail=str(e))
