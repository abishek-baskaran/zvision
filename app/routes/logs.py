from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict
from datetime import datetime

from app.database.events import get_events_for_store
from app.database.cameras import get_cameras_for_store

router = APIRouter()

@router.get("/logs")
def fetch_logs(
    store_id: int,
    camera_id: Optional[int] = Query(None, description="Filter logs by camera ID"),
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    event_type: Optional[str] = Query(None, description="Filter by event type, e.g., 'entry'/'exit'"),
    limit: Optional[int] = Query(None, description="Limit number of logs returned")
):
    """
    Fetches logs (entry_exit_events) for a given store_id.
    Optional filters:
      - camera_id: Filter logs for a specific camera
      - start_date / end_date in 'YYYY-MM-DD' format
      - event_type
      - limit
    """

    # 1. Fetch all events for the given store from the DB
    try:
        events = get_events_for_store(store_id)
    except RuntimeError as db_err:
        raise HTTPException(status_code=500, detail=str(db_err))
        
    # 2. Fetch camera information to include camera names in the response
    try:
        cameras = get_cameras_for_store(store_id)
        camera_map = {cam["camera_id"]: cam for cam in cameras}
    except RuntimeError as db_err:
        # Don't fail the request if camera info can't be fetched
        camera_map = {}

    # 3. Convert each event timestamp (stored as string) to a Python datetime
    #    Assuming the stored format is "YYYY-MM-DD HH:MM:SS", e.g. "2025-02-20 12:00:00"
    def to_datetime(ts_str: str) -> datetime:
        return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")

    # 4. Apply camera_id filtering if specified
    if camera_id is not None:
        events = [e for e in events if e.get("camera_id") == camera_id]

    # 5. Apply date-range filtering if start_date or end_date are specified
    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        events = [
            e for e in events
            if to_datetime(e["timestamp"]) >= start_dt
        ]

    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        events = [
            e for e in events
            if to_datetime(e["timestamp"]) <= end_dt
        ]

    # 6. Filter by event_type if provided
    if event_type:
        events = [e for e in events if e["event_type"] == event_type]

    # 7. Enrich events with camera names if available
    enriched_events = []
    for event in events:
        # Create a new event object with all original fields
        enriched_event = dict(event)
        
        # Add camera_name if camera_id exists and can be found in camera_map
        if event.get("camera_id") and event["camera_id"] in camera_map:
            enriched_event["camera_name"] = camera_map[event["camera_id"]]["camera_name"]
        else:
            enriched_event["camera_name"] = "Unknown Camera"
            
        # Format timestamp in ISO format for frontend consistency
        if "timestamp" in enriched_event:
            try:
                dt = to_datetime(enriched_event["timestamp"])
                enriched_event["timestamp_iso"] = dt.isoformat()
            except ValueError:
                # Keep the original timestamp if parsing fails
                enriched_event["timestamp_iso"] = enriched_event["timestamp"]
            
        enriched_events.append(enriched_event)

    # 8. Apply optional limit
    if limit and limit > 0:
        enriched_events = enriched_events[:limit]

    return {
        "store_id": store_id,
        "camera_id": camera_id,  # Include camera_id in response if filtered
        "total_events": len(enriched_events),
        "events": enriched_events
    }

@router.get("/cameras/{camera_id}/logs")
def fetch_camera_logs(
    camera_id: int,
    store_id: Optional[int] = Query(None, description="Store ID, optional if camera_id is unique"),
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    event_type: Optional[str] = Query(None, description="Filter by event type, e.g., 'entry'/'exit'"),
    limit: Optional[int] = Query(None, description="Limit number of logs returned")
):
    """
    Fetches logs specifically for a camera.
    This is a convenience endpoint that delegates to the main logs endpoint with camera_id filter.
    """
    from app.database.cameras import get_camera_by_id
    
    # If store_id not provided, get it from the camera
    if store_id is None:
        camera = get_camera_by_id(camera_id)
        if not camera:
            raise HTTPException(status_code=404, detail=f"Camera with ID {camera_id} not found")
        store_id = camera.get("store_id")
    
    # Delegate to the main logs endpoint
    return fetch_logs(
        store_id=store_id,
        camera_id=camera_id,
        start_date=start_date,
        end_date=end_date,
        event_type=event_type,
        limit=limit
    )
