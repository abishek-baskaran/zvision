import cv2
import os
from fastapi import APIRouter, HTTPException, Response

router = APIRouter()

# For demo: a simple in-memory mapping from camera_id -> video source path
# In a real project, you'd fetch this from a database table.
CAMERA_SOURCES = {
    "1": "videos/source/zvision_test_1.mp4",
    "2": "videos/source/zvision_test_2.mp4"
    # or "rtsp://username:password@camera_ip/stream" for actual RTSP cameras
}

@router.get("/camera/{camera_id}/snapshot")
def get_camera_snapshot(camera_id: str):
    """
    Returns a single frame (image) from the chosen camera/video source.
    This can be used by the front-end to display a reference snapshot for calibration.
    """

    # Look up the source path (local file or RTSP URL)
    source_path = CAMERA_SOURCES.get(camera_id)
    if not source_path:
        raise HTTPException(
            status_code=404,
            detail=f"Camera '{camera_id}' not found in CAMERA_SOURCES"
        )

    # Attempt to open the source with OpenCV
    cap = cv2.VideoCapture(source_path)
    if not cap.isOpened():
        raise HTTPException(
            status_code=500,
            detail=f"Failed to open camera/video source '{source_path}'"
        )

    # Grab a single frame
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        raise HTTPException(
            status_code=500,
            detail="Unable to read a frame from the camera/video."
        )

    # Convert the frame to JPEG image bytes
    success, encoded_img = cv2.imencode(".jpg", frame)
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to encode frame to JPEG."
        )

    # Return the image as a binary response
    return Response(content=encoded_img.tobytes(), media_type="image/jpeg")
