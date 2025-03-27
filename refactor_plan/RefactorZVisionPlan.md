Project: ZVision Backend Refactor (Raspberry Pi 5)

Goal

Refactor ZVision backend to support real-time video streaming + object detection concurrently, add analytics, and improve modularity. Keep all API routes unchanged to maintain React+Vite frontend compatibility.

Hardware Target

Raspberry Pi 5

Backend Tech Constraints

Python + FastAPI

OpenCV + YOLOv8n (Ultralytics)

Maintain existing endpoints (no breaking frontend)

Core Problems

Video streaming blocks during detection (single-threaded)

No true parallelism due to Python GIL

Detection runs every 5th frame, but causes lag

Mixed responsibilities: no modular camera/detection services

No performance monitoring or analytics

Re-architecture Strategy

Use multiprocessing.Process to split:

CameraWorker: Captures frames continuously

DetectionWorker: Detects every ~5th frame

Use inter-process queues to pass frames/results

Maintain latest frame and detection in shared memory

Replace direct camera access in routes with manager calls

Add lightweight analytics (FPS, detection count, inference time)

Modules

camera_manager.py: Manages camera processes

detection_worker.py: YOLO detection in parallel process

analytics.py: Tracks frame stats, detection counts, latencies

routes/: API endpoints call into the above services

Phase Plan (Cursor Prompts)

Phase 1: Setup modular structure and redirect old logic to new services.
Phase 2: Move camera capture into CameraWorker (process/thread) and stream frames via shared queue.
Phase 3: Run DetectionWorker in separate process to handle YOLO inference on selected frames.
Phase 4: Add shared analytics tracking (detection FPS, object count, inference latency).
Phase 5: Test single & multi-stream support, clean up process lifecycle, ensure performance on Pi.

Requirements

Keep /api/* endpoints same

Low memory footprint (bounded queues)

Ensure fast snapshot and streaming

Log or expose detection stats (optional for DB later)

Notes

Use torch.set_num_threads(1) for YOLO on Pi

Consider shared memory or JPEG compression for inter-process efficiency

Avoid duplicate camera capture instances

Use multiprocessing.Manager() or queues to share data safely

