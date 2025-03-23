# ZVision: Entry-Exit Detection & Calibration

This repository demonstrates a complete pipeline for detecting entries/exits in a store environment using:

- **FastAPI** for the backend server
- **SQLite** for local data storage (stores, cameras, calibrations, events)
- **YOLO** (Ultralytics) for object detection
- **Flutter** for a simple calibration UI (optional demo)

## Overview

1. **Stores**  
   - Each store is identified by a `store_id`.  
   - The system can handle multiple stores.

2. **Cameras**  
   - Each camera row references a store (`store_id`) and has a unique `camera_id`.  
   - A store can have multiple cameras.  
   - The `camera_name` can be a friendly label or an RTSP link.

3. **Calibrations**  
   - Each `camera_id` can have a unique calibration line (or multiple if you remove the UNIQUE constraint).  
   - A line is defined by `(x1, y1) -> (x2, y2)`, stored in the `calibrations` table.

4. **Events (entry_exit_events)**  
   - Whenever the pipeline detects an object crossing the calibration line, it logs an event with `event_type = "entry"` or `"exit"`.  
   - Each row references the `store_id`, plus optional fields like `clip_path` and `timestamp`.

## Project Structure

- `app/`
  - `main.py`  
    - FastAPI server entry point  
    - Routers for camera, logs, events, and a calibration route
    - Optionally processes local videos before starting the server
  - `database/`  
    - `connection.py`: DB path and `get_connection()`  
    - `stores.py`, `cameras.py`, `calibration.py`, `events.py`: separate files for each table  
      - `initialize_*_table()` functions  
      - CRUD methods (add_store, add_camera, store_calibration, add_event, etc.)  
  - `inference/`  
    - `detection.py`: runs YOLO model inference on frames  
    - `crossing.py`: line-crossing logic (sign test, naive matching)  
    - `pipeline.py`: orchestrates reading frames, calling detection, applying calibration, and logging events  
  - `routes/`  
    - optional separate route files (camera.py, logs.py, events.py, calibration.py)

## Setup Steps

1. **Create & Activate a Python Environment**  
    - `conda create --name zvision python=3.9 conda activate zvision`

2. **Install Dependencies**
    - `pip install fastapi uvicorn opencv-python ultralytics pydantic`
  
3. **Run Database Initialization**  
    - The code calls `initialize_db()` in `main.py`, or you can run a script (e.g., `reset_db.py`) to drop & recreate tables if needed.

4. **Start the Server**
    - `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
    - Check `http://127.0.0.1:8000/api/ping` returns `{"status":"ok"}`.

5. **Flutter Front-End (Optional)**  
- A minimal calibration screen calls `GET /api/camera/{camera_id}/snapshot` for a snapshot.  
- Then posts line coordinates to `POST /api/calibrate`, referencing `camera_id`.

## Workflows

1. **Add a Store**  
- `store_id` auto-increment. Example name: "My First Store."
2. **Add a Camera**  
- referencing store_id. e.g., (store_id=1, camera_name="Front Door Cam").
3. **Calibrate**  
- Post to `/api/calibrate` with `camera_id` (as integer) and line coords.  
- DB updates the `calibrations` table for that camera.
4. **Detection**  
- The pipeline (`process_camera_stream`) fetches line_data from `calibrations`, runs YOLO detection, checks crossing.  
- If crossing is detected, it increments in-memory counters or logs an event (`add_event()`).
5. **Logs & Analytics**  
- `entry_exit_events` can store each crossing with a timestamp and clip_path, so you can do daily/hourly analytics later.

## Future Enhancements

- **Multiple Lines** per camera if needed (remove UNIQUE constraint on `camera_id`).  
- **Object ID Tracking** for more accurate crossing detection.  
- **Offline / FIFO Clip** logic to manage disk usage.  
- **Analytics Endpoints** (daily/hourly grouping, peak times, etc.).  
- **Refined Flutter UI** to show real-time traffic or event logs.

## Conclusion

With this setup, you can:

1. Manage multiple stores, each with multiple cameras.  
2. Store calibration lines in the DB for each camera.  
3. Use a YOLO pipeline to detect bounding boxes, determine line crossings, and log entry/exit events for store analytics.  