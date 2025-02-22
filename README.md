## Overview
This repository contains:
- A **FastAPI** server for handling store data, logs, and detection endpoints.
- A **YOLO-based** (or NCNN-based) detection pipeline (in `counter.py`) that processes video files or camera streams.
- A **SQLite** database (in `database.py`) storing events and logs for analytics.
- Various utility scripts for testing, clip FIFO cleanup, etc.

Below are instructions for both the FastAPI server usage and the video annotation pipeline.

---

## 1. Environment Setup

1. Clone or pull this repository to your local machine.
2. Create and activate a Python environment:
   conda create --name zvision python=3.9
   conda activate zvision
3. Install required dependencies (FastAPI, uvicorn, opencv-python, ultralytics, etc.):
   pip install -r requirements.txt
4. Verify your installation:
   python --version
   pip list

---

## 2. Running the FastAPI Server

1. **Navigate** to the project’s root folder (where `app/main.py` is accessible).
2. **Launch the server**:
   uvicorn app.main:app --reload
3. **Test** the health-check endpoint:
   - Open your browser at http://127.0.0.1:8000/ping
   - You should see: {"status": "ok"}

**Endpoints**:
- /detect (placeholder for future YOLO detection)
- /calibrate (placeholder for boundary/line calibration)
- /events (POST event data)
- /logs (GET logs by store_id, date range, etc.)

---

## 3. Annotating Video with YOLO

Our main detection/annotation pipeline lives in `app/counter.py`. It can:
- Process files from `videos/source/`
- Generate annotated videos into `videos/annotated/`
- Prompt you whether to replace or ignore existing files

**Steps**:
1. Place your raw videos in `videos/source`.
2. From the project’s root directory:
   python app/counter.py
3. The script scans `videos/source/`, and for each file:
   - Creates an annotated version in `videos/annotated/<filename>_annotated.mp4`
   - If a file already exists, it asks you to replace or ignore
4. The script logs frames processed, detections, and approximate FPS.

---

## 4. Switching to NCNN (Optional)
- If you have an NCNN YOLO model, use the scripts under `app/counter_ncnn.py` or your own version in `ncnn_model.py`.
- Adapt the code to load your .param / .bin files and handle bounding-box drawing.

---

## 5. Database & Logs
- SQLite DB is in `app/zvision.db`.
- `database.py` includes functions to create tables, insert events, and fetch logs.
- `GET /logs` from the FastAPI server can filter logs by store, date, or event type.

---

## 6. Troubleshooting
- **HTTP 404** when pinging? Ensure your route matches and you’re not mixing /api/ prefixes.
- **Blue screen or crash** during YOLO? Lower resolution or force CPU (`use_cpu=True`) in `counter.py`.
- **Permission errors** when writing to `videos/annotated/`? Check folder permissions or run as admin.

---

## 7. Next Steps
- Implement calibration UI or logic (entry/exit lines) via /calibrate.
- Add advanced analytics (daily/hourly counts) in `database.py`, create new endpoints for them.
- Possibly integrate a **Flutter** or web front-end to visualize real-time footfall analytics.

---

## 8. Contributing
1. Make a new branch for your feature or fix.
2. Commit changes with clear messages.
3. Push to GitHub and create a Pull Request.

For **SSH** key usage: ensure your GitHub remote is set to git@github.com:username/zvision.git and you have an SSH key added to your GitHub account.

---

## 9. License
This project is primarily for demonstration/educational purposes. Check the code for any third-party licenses.
