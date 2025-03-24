#!/bin/bash

# Create a directory for the extraction
mkdir -p zvision_extract

# Copy WebRTC implementation
cp app/routes/webrtc.py zvision_extract/
cp app/temp/webrtc_hybrid_test.html zvision_extract/
cp app/temp/test_webrtc.py zvision_extract/
cp app/temp/serve_webrtc_test.py zvision_extract/

# Copy WebSocket implementation
cp app/routes/websockets.py zvision_extract/
cp app/temp/websocket_browser_test.html zvision_extract/
cp app/temp/serve_websocket_test.py zvision_extract/
cp app/temp/test_websocket.py zvision_extract/

# Copy Detection Pipeline
cp app/routes/detection.py zvision_extract/
cp app/inference/pipeline.py zvision_extract/
cp app/inference/detection.py zvision_extract/
cp app/inference/crossing.py zvision_extract/

# Copy Camera Management
cp app/routes/camera.py zvision_extract/
cp app/database/cameras.py zvision_extract/
cp app/database/calibration.py zvision_extract/

# Create a archive
tar -czvf zvision_code.tar.gz zvision_extract/

echo "Extraction complete. Archive created at: zvision_code.tar.gz" 