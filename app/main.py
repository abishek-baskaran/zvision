# app/main.py

from fastapi import FastAPI, HTTPException
from app.routes import logs, events, camera,calibration
from app.camera_inference import process_camera_stream
from app.database import initialize_db
from app.database.calibration import store_calibration
from models.calibration import CalibrationData
import os

initialize_db()

app = FastAPI()

# Include routers under "/api"
app.include_router(camera.router, prefix="/api", tags=["camera"])
app.include_router(logs.router, prefix="/api", tags=["logs"])
app.include_router(events.router, prefix="/api", tags=["events"])
app.include_router(calibration.router, prefix="/api", tags=["calibration"])

@app.get("/api/ping")
def read_ping():
    """Basic health-check endpoint."""
    return {"status": "ok"}

@app.post("/api/detect")
def detect():
    """
    Placeholder for a future detection endpoint.
    For now, returns a dummy message.
    """
    return {"message": "Placeholder for detect endpoint."}


if __name__ == "__main__":
    import uvicorn

    # Optional demonstration: process local videos before starting the server.
    source_folder = "./videos/source"
    annotated_folder = "./videos/annotated"
    os.makedirs(annotated_folder, exist_ok=True)

    for vid in os.listdir(source_folder):
        if not vid.lower().endswith((".mp4", ".avi", ".mkv")):
            continue
        src_path = os.path.join(source_folder, vid)
        out_path = os.path.join(annotated_folder, f"annot_{vid}")
        # Example: skip_frame=5, write_mode="processed"
        process_camera_stream(
            source=src_path,
            output_path=out_path,
            camera_id=None,  # or an integer if you want line crossing
            skip_frame=5,
            write_mode="processed"
        )

    # Finally, launch the FastAPI server:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
