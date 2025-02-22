from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from datetime import datetime

from app.database import get_events_for_store

router = APIRouter()

@router.get("/logs")
def fetch_logs(
    store_id: int,
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    event_type: Optional[str] = Query(None, description="Filter by event type, e.g., 'entry'/'exit'"),
    limit: Optional[int] = Query(None, description="Limit number of logs returned")
):
    """
    Fetches logs (entry_exit_events) for a given store_id.
    Optional filters:
      - start_date / end_date in 'YYYY-MM-DD' format
      - event_type
      - limit
    """

    # 1. Fetch all events for the given store from the DB
    try:
        events = get_events_for_store(store_id)
    except RuntimeError as db_err:
        raise HTTPException(status_code=500, detail=str(db_err))

    # 2. Convert each event timestamp (stored as string) to a Python datetime
    #    Assuming the stored format is "YYYY-MM-DD HH:MM:SS", e.g. "2025-02-20 12:00:00"
    def to_datetime(ts_str: str) -> datetime:
        return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")

    # 3. Apply date-range filtering if start_date or end_date are specified
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

    # 4. Filter by event_type if provided
    if event_type:
        events = [e for e in events if e["event_type"] == event_type]

    # 5. Apply optional limit
    if limit and limit > 0:
        events = events[:limit]

    return {
        "store_id": store_id,
        "total_events": len(events),
        "events": events
    }
