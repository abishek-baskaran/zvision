from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.routes import logs, events, camera, calibration, detection, stores, auth, websockets, webrtc
from app.database import initialize_db
import os
from fastapi.middleware.cors import CORSMiddleware
from app.config import ALLOWED_ORIGINS, HOST, PORT, DEBUG, BUILD_DIR, STATIC_DIR, IS_PRODUCTION
from app.middleware.https import HTTPSRedirectMiddleware
from app.middleware.security import SecurityHeadersMiddleware

initialize_db()

app = FastAPI(
    title="ZVision API",
    description="ZVision Entry/Exit Detection System API",
    version="1.0.0",
    debug=DEBUG
)

# ⚠️ CORS Middleware MUST come first ⚠️
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
)

# Add security middlewares
app.add_middleware(HTTPSRedirectMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# Include routers under "/api"
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(stores.router, prefix="/api", tags=["stores"])
app.include_router(camera.router, prefix="/api", tags=["camera"])
app.include_router(logs.router, prefix="/api", tags=["logs"])
app.include_router(events.router, prefix="/api", tags=["events"])
app.include_router(calibration.router, prefix="/api", tags=["calibration"])
app.include_router(detection.router, prefix="/api", tags=["detection"])
app.include_router(websockets.router, prefix="/api", tags=["websockets"])  # Add /api prefix to match frontend requests
app.include_router(webrtc.router, prefix="/api", tags=["rtc"])  # Add WebRTC router

@app.get("/api/ping")
def read_ping():
    """Basic health-check endpoint."""
    return {"status": "ok"}

# Check if static directory exists
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

# Check if build directory exists
if not os.path.exists(BUILD_DIR):
    os.makedirs(BUILD_DIR)
    # Create a placeholder index.html if not in production
    if not IS_PRODUCTION:
        with open(f"{BUILD_DIR}/index.html", "w") as f:
            f.write("""
            <!DOCTYPE html>
            <html>
            <head>
                <title>ZVision - Placeholder</title>
            </head>
            <body>
                <h1>ZVision Frontend Placeholder</h1>
                <p>Please deploy the React build files to this directory.</p>
            </body>
            </html>
            """)

# Mount static files directory
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Mount React build directory
app.mount("/build", StaticFiles(directory=BUILD_DIR), name="build")

# Serve React app's static files
@app.get("/{full_path:path}")
async def serve_react_app(full_path: str, request: Request):
    index_html_path = f"{BUILD_DIR}/index.html"
    
    # Check if the index.html file exists
    if not os.path.exists(index_html_path):
        raise HTTPException(status_code=404, detail="Frontend not deployed. Please build and deploy the React app.")
    
    # This serves the React app's index.html for client-side routing
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")
    
    # For root path or any frontend route, serve index.html
    return FileResponse(index_html_path)

if __name__ == "__main__":
    import uvicorn # type: ignore
    uvicorn.run("main:app", host=HOST, port=PORT, reload=DEBUG)
