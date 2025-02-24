from fastapi import FastAPI
from app.routes import logs, events
from app.camera_inference import process_camera_stream
import cv2
import time
import os


app = FastAPI()

# Include routers under "/api"
app.include_router(logs.router, prefix="/api", tags=["logs"])
app.include_router(events.router, prefix="/api", tags=["events"])

# Basic health-check endpoint
@app.get("/api/ping")
def read_ping():
    return {"status": "ok"}

# Placeholder for a future `/detect` route
@app.post("/api/detect")
def detect():
    # This will eventually accept image data, run YOLO detection,
    # and return results. For now, just a placeholder.
    return {"message": "Placeholder for detect endpoint."}

# Placeholder for a future `/calibrate` route
@app.get("/api/calibrate")
def calibrate():
    # This endpoint might define line or boundary settings in the future.
    return {"message": "Placeholder for calibrate endpoint."}

if __name__ == "__main__":
    source_folder = "./videos/source"
    annotated_folder = "./videos/annotated"
    os.makedirs(annotated_folder, exist_ok=True)

    for vid in os.listdir(source_folder):
        if not vid.lower().endswith((".mp4", ".avi", ".mkv")):
            continue
        src_path = os.path.join(source_folder, vid)
        out_path = os.path.join(annotated_folder, f"annot_{vid}")
        process_camera_stream(src_path, out_path, 640, 480, 5, "processed")