from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from app.routes import camera, detection, metrics, test_direct
from app.database import initialize_db
import os
import multiprocessing
from fastapi.middleware.cors import CORSMiddleware
from app.config import ALLOWED_ORIGINS, HOST, PORT, DEBUG, BUILD_DIR, STATIC_DIR, IS_PRODUCTION
from app.middleware.https import HTTPSRedirectMiddleware
from app.middleware.security import SecurityHeadersMiddleware

# Import core services
from app.camera_manager import camera_manager
from app.detection_worker import detection_manager
from app.analytics import analytics

# Set debug mode for authentication
os.environ["ZVISION_DEBUG"] = str(DEBUG).lower()
print(f"ZVision starting in {'DEBUG' if DEBUG else 'PRODUCTION'} mode")

# Initialize database
initialize_db()

# Define public directory for our basic HTML demo
PUBLIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
if not os.path.exists(PUBLIC_DIR):
    os.makedirs(PUBLIC_DIR)
    print(f"Created public directory at {PUBLIC_DIR}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI application.
    Handles startup and shutdown events.
    """
    # Startup
    print("Starting ZVision services...")
    try:
        # Camera manager and detection manager are initialized on import
        print("✅ All ZVision services started successfully")
        
    except Exception as e:
        print(f"❌ Error during service startup: {e}")
        raise
    
    yield  # Server is running
    
    # Shutdown
    print("Shutting down ZVision services...")
    try:
        # Stop all camera workers first (this also stops associated detection)
        print("Stopping camera workers...")
        camera_manager.release_all()
        
        # Stop detection workers
        print("Stopping detection workers...")
        detection_manager.stop()
        
        # Wait briefly for graceful shutdown
        import time
        time.sleep(1)
        
        # Force cleanup any remaining processes
        import psutil
        current_process = psutil.Process()
        children = current_process.children(recursive=True)
        
        if children:
            print(f"Force terminating {len(children)} remaining processes...")
            for child in children:
                try:
                    child.terminate()
                except Exception as e:
                    print(f"Error terminating process {child.pid}: {e}")
        
        print("✅ ZVision services shut down successfully")
        
    except Exception as e:
        print(f"❌ Error during shutdown: {e}")
        raise

app = FastAPI(
    title="ZVision API",
    description="ZVision Entry/Exit Detection System API",
    version="2.0.0",  # Updated version to reflect refactor
    debug=DEBUG,
    lifespan=lifespan
)

# CORS Middleware (must be first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
)

# Security middlewares
app.add_middleware(HTTPSRedirectMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# Include core API routers
app.include_router(camera.router, prefix="/api", tags=["camera"])
app.include_router(detection.router, prefix="/api", tags=["detection"])
app.include_router(metrics.router, prefix="/api", tags=["metrics"])
app.include_router(test_direct.router, tags=["test"])

@app.get("/api/ping")
def read_ping():
    """Basic health-check endpoint."""
    return {
        "status": "ok",
        "services": {
            "camera_manager": {
                "active_cameras": len(camera_manager.cameras),
                "status": "running"
            },
            "detection_manager": {
                "active_workers": len(detection_manager.workers),
                "status": "running"
            },
            "analytics": {
                "frame_stats": analytics.get_frame_processing_stats(1) if 1 in camera_manager.cameras else {},
                "detections": analytics.get_detections_by_class(1) if 1 in camera_manager.cameras else {}
            }
        }
    }

# Static file handling
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

if not os.path.exists(BUILD_DIR):
    os.makedirs(BUILD_DIR)
    if not IS_PRODUCTION:
        with open(f"{BUILD_DIR}/index.html", "w") as f:
            f.write("""
            <!DOCTYPE html>
            <html>
            <head>
                <title>ZVision - Development</title>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    body { 
                        font-family: system-ui, -apple-system, sans-serif;
                        max-width: 800px;
                        margin: 2rem auto;
                        padding: 0 1rem;
                    }
                    .status { margin: 2rem 0; padding: 1rem; border-radius: 4px; }
                    .dev { background: #f0f0f0; }
                </style>
            </head>
            <body>
                <h1>ZVision Development Environment</h1>
                <div class="status dev">
                    <h2>Frontend Not Deployed</h2>
                    <p>Please build and deploy the React frontend to this directory.</p>
                </div>
            </body>
            </html>
            """)

# Mount static directories
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/build", StaticFiles(directory=BUILD_DIR), name="build")
app.mount("/public", StaticFiles(directory=PUBLIC_DIR), name="public")

# Add a direct route to our basic HTML demo page
@app.get("/demo")
async def serve_basic_demo():
    """Serve the basic HTML demo page"""
    demo_path = f"{PUBLIC_DIR}/index.html"
    if os.path.exists(demo_path):
        return FileResponse(demo_path)
    else:
        raise HTTPException(
            status_code=404,
            detail="Demo page not found. Make sure to create the index.html file in the public directory."
        )

# Add a route for our direct test interface
@app.get("/direct-test")
async def serve_direct_test():
    """Serve the direct test interface"""
    test_path = f"{PUBLIC_DIR}/direct_test.html"
    if os.path.exists(test_path):
        return FileResponse(test_path)
    else:
        raise HTTPException(
            status_code=404,
            detail="Direct test page not found. Make sure direct_test.html exists in the public directory."
        )

@app.get("/{full_path:path}")
async def serve_react_app(full_path: str, request: Request):
    """Serve the React frontend for all non-API routes"""
    index_html_path = f"{BUILD_DIR}/index.html"
    
    if not os.path.exists(index_html_path):
        raise HTTPException(
            status_code=404, 
            detail="Frontend not deployed. Please build and deploy the React app."
        )
    
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")
    
    return FileResponse(index_html_path)

if __name__ == "__main__":
    # Set multiprocessing start method to 'spawn' to fix pickling issues
    multiprocessing.set_start_method("spawn")
    print(f"Multiprocessing start method set to: {multiprocessing.get_start_method()}")
    
    import uvicorn
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        workers=1  # Single worker for proper process management
    )
