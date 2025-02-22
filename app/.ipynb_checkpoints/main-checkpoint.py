from fastapi import FastAPI
from app.routes import logs, events

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
