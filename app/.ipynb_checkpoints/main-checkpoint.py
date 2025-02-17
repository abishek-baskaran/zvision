from fastapi import FastAPI

app = FastAPI()

# Basic health-check endpoint
@app.get("/ping")
def read_ping():
    return {"status": "ok"}

# Placeholder for a future `/detect` route
@app.post("/detect")
def detect():
    # This will eventually accept image data, run YOLO detection,
    # and return results. For now, just a placeholder.
    return {"message": "Placeholder for detect endpoint."}

# Placeholder for a future `/calibrate` route
@app.get("/calibrate")
def calibrate():
    # This endpoint might define line or boundary settings in the future.
    return {"message": "Placeholder for calibrate endpoint."}