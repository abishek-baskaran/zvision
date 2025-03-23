from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, status
from typing import Dict, List, Optional, Any
import json
import asyncio
import cv2
import base64
from datetime import datetime
from jose import JWTError, jwt
from pydantic import BaseModel
import time
import statistics  # Add statistics module for calculating averages

from app.config import SECRET_KEY, ALGORITHM
from app.services.detection_service import detect_person_crossing
from app.database.cameras import get_camera_by_id
from app.routes.camera import _resize_frame, _fetch_camera_source_by_id
from app.database.calibration import fetch_calibration_for_camera

router = APIRouter()

# Store active connections
active_connections: Dict[int, List[WebSocket]] = {}

# Model for WebSocket responses
class DetectionWSResponse(BaseModel):
    camera_id: int
    timestamp: str
    frame: str  # Base64 encoded image frame
    detections: List[Dict[str, Any]]
    event: Optional[str] = None
    status: str = "no_motion"
    crossing_detected: bool = False
    actual_fps: Optional[float] = None
    target_fps: Optional[float] = None
    hardware_limited: Optional[bool] = None

# Verify token similar to get_current_user but for WebSockets
async def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        is_admin: bool = payload.get("admin", False)
        
        if username is None:
            return None
            
        return {"username": username, "is_admin": is_admin}
    except JWTError:
        return None

@router.websocket("/ws/live-detections/{camera_id}")
async def live_detections(
    websocket: WebSocket, 
    camera_id: int, 
    token: Optional[str] = Query(None),
    frame_rate: Optional[int] = Query(None)  # Add explicit frame_rate parameter
):
    """
    WebSocket endpoint for real-time video streaming with detection results
    Requires a valid JWT token as a query parameter
    """
    # Verify the token
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing authentication token")
        return
        
    user = await verify_token(token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid authentication token")
        return
    
    # Verify the camera exists
    camera = get_camera_by_id(camera_id)
    if not camera:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=f"Camera with ID {camera_id} not found")
        return
    
    # Accept the connection
    await websocket.accept()
    
    # Add to active connections
    if camera_id not in active_connections:
        active_connections[camera_id] = []
    active_connections[camera_id].append(websocket)
    
    # Get camera source
    source_path = _fetch_camera_source_by_id(camera_id)
    if not source_path:
        await websocket.send_json({
            "status": "error",
            "message": f"Camera source not found for camera_id={camera_id}"
        })
        if camera_id in active_connections and websocket in active_connections[camera_id]:
            active_connections[camera_id].remove(websocket)
        return

    # Open video capture once at the beginning
    cap = cv2.VideoCapture(source_path)
    if not cap.isOpened():
        await websocket.send_json({
            "status": "error",
            "message": f"Failed to open camera/video source '{source_path}'"
        })
        if camera_id in active_connections and websocket in active_connections[camera_id]:
            active_connections[camera_id].remove(websocket)
        return
    
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "status": "connected",
            "message": f"Connected to live video stream for camera {camera_id}"
        })
        
        # Get calibration data to determine frame rate
        calib_data = fetch_calibration_for_camera(camera_id)
        
        # Detection state
        detection_result = None
        last_detection_time = 0
        
        # Use frame_rate parameter from query if provided, otherwise from calibration
        if frame_rate is not None:
            # URL parameter takes precedence
            configured_frame_rate = frame_rate
        elif calib_data and "frame_rate" in calib_data:
            configured_frame_rate = calib_data.get("frame_rate", 5)  # Default to 5 FPS
        else:
            configured_frame_rate = 5  # Default if no other source available
            
        # Ensure frame_rate is valid
        if configured_frame_rate <= 0:
            configured_frame_rate = 5  # Fallback to 5 FPS
            
        # Convert frame_rate to detection interval (seconds between detections)
        detection_interval = 1.0 / configured_frame_rate
        log_message = f"Using configured frame rate: {configured_frame_rate} FPS (interval: {detection_interval:.3f}s)"
        
        print(f"Camera {camera_id}: {log_message}")
        
        # Add performance tracking variables
        frame_count = 0
        start_time = time.time()
        last_frame_time = start_time
        frame_times = []
        processing_times = []
        send_times = []
        
        # Log initial connection details
        print(f"Camera {camera_id}: WebSocket connection established, target FPS: {configured_frame_rate:.1f} for detection, ~20 FPS for streaming")
        
        # Set quality based on frame rate
        if configured_frame_rate > 15:
            # Use lower quality for high frame rates
            jpeg_quality = 40
            max_height = 160
        elif configured_frame_rate > 8:
            # Medium quality for medium frame rates
            jpeg_quality = 50
            max_height = 180
        else:
            # Better quality for low frame rates
            jpeg_quality = 60
            max_height = 180
            
        # Main streaming loop
        while True:
            try:
                loop_start = time.time()
                
                # Read frame
                ret, frame = cap.read()
                
                if not ret or frame is None:
                    # If we're at the end of a video file, try to reopen it
                    cap.release()
                    cap = cv2.VideoCapture(source_path)
                    if not cap.isOpened():
                        await websocket.send_json({
                            "status": "error",
                            "message": f"Failed to reopen video source '{source_path}'"
                        })
                        break
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        await websocket.send_json({
                            "status": "error",
                            "message": "Unable to read a frame from the camera/video"
                        })
                        break
                
                # Make a copy for streaming
                display_frame = frame.copy()
                
                # Resize the frame to a smaller size for WebSocket streaming
                display_frame = _resize_frame(display_frame, max_height=max_height)
                
                # Track time for frame processing
                processing_start = time.time()
                
                # Only run detection periodically to improve performance
                current_time = time.time()
                if current_time - last_detection_time >= detection_interval:
                    # Run detection in background (non-blocking)
                    detection_task = asyncio.create_task(asyncio.to_thread(detect_person_crossing, camera_id))
                    try:
                        # Wait with a timeout to avoid blocking the stream
                        detection_result = await asyncio.wait_for(detection_task, timeout=0.2)
                        last_detection_time = current_time
                    except asyncio.TimeoutError:
                        # Detection is taking too long, continue with the stream
                        pass
                
                # Encode frame to JPEG and then base64 with quality based on frame rate
                encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]
                success, encoded_img = cv2.imencode(".jpg", display_frame, encode_params)
                if not success:
                    await websocket.send_json({
                        "status": "error",
                        "message": "Failed to encode frame to JPEG"
                    })
                    continue
                    
                frame_base64 = base64.b64encode(encoded_img.tobytes()).decode('utf-8')
                
                # Record processing time
                processing_end = time.time()
                processing_time = processing_end - processing_start
                processing_times.append(processing_time)
                
                # Format the response
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if detection_result:
                    timestamp = detection_result.get("timestamp", timestamp)
                timestamp_iso = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").isoformat()
                
                # Format detection results
                detections = []
                event = None
                status = "no_motion"
                crossing_detected = False
                
                if detection_result:
                    # Format bounding boxes
                    for bbox in detection_result.get("bounding_boxes", []):
                        detections.append({
                            "label": "person",  # Currently only detecting people
                            "confidence": 0.9,  # Placeholder, real confidence scores would be better
                            "bbox": bbox
                        })
                    
                    # Check if an event was detected
                    if "status" in detection_result:
                        status = detection_result["status"]
                        if status == "entry_detected":
                            event = "entry"
                        elif status == "exit_detected":
                            event = "exit"
                        
                    crossing_detected = detection_result.get("crossing_detected", False)
                
                # Calculate current actual FPS
                current_time = time.time()
                elapsed = current_time - start_time
                actual_fps = frame_count / elapsed if elapsed > 0 else 0
                
                # Determine if hardware is limiting the frame rate
                hardware_limited = (configured_frame_rate > 6.0 and actual_fps < configured_frame_rate * 0.7)
                
                # Create response
                response = DetectionWSResponse(
                    camera_id=camera_id,
                    timestamp=timestamp_iso,
                    frame=frame_base64,
                    detections=detections,
                    event=event,
                    status=status,
                    crossing_detected=crossing_detected,
                    actual_fps=round(actual_fps, 1),
                    target_fps=configured_frame_rate,
                    hardware_limited=hardware_limited
                )
                
                # Track send time
                send_start = time.time()
                
                # Send update to client
                await websocket.send_json(response.dict())
                
                # Record send completion time
                send_end = time.time()
                send_time = send_end - send_start
                send_times.append(send_time)
                
                # Increment frame counter and calculate FPS
                frame_count += 1
                current_time = time.time()
                time_since_last_frame = current_time - last_frame_time
                frame_times.append(time_since_last_frame)
                last_frame_time = current_time
                
                # Log performance metrics every 30 frames
                if frame_count % 30 == 0:
                    elapsed = current_time - start_time
                    actual_fps = frame_count / elapsed
                    
                    # Calculate average times
                    avg_frame_time = sum(frame_times) / len(frame_times) if frame_times else 0
                    avg_processing = sum(processing_times) / len(processing_times) if processing_times else 0
                    avg_send = sum(send_times) / len(send_times) if send_times else 0
                    
                    # Calculate standard deviation to show consistency
                    frame_time_std = statistics.stdev(frame_times) if len(frame_times) > 1 else 0
                    
                    print(f"Camera {camera_id} WebSocket metrics:")
                    print(f"  - Frames sent: {frame_count}, Average FPS: {actual_fps:.2f} (target: {configured_frame_rate})")
                    print(f"  - Average frame interval: {avg_frame_time:.4f}s (±{frame_time_std:.4f}s)")
                    print(f"  - Processing time: {avg_processing:.4f}s, Send time: {avg_send:.4f}s")
                    print(f"  - Frame size: {len(frame_base64) / 1024:.1f} KB, Quality: {jpeg_quality}%")
                    print(f"  - Hardware limited: {hardware_limited}")
                    
                    # Reset for next window
                    if len(frame_times) > 100:  # Limit the array size
                        frame_times = frame_times[-100:]
                        processing_times = processing_times[-100:]
                        send_times = send_times[-100:]
                
                # Adaptive sleep to maintain consistent frame rate
                elapsed = time.time() - loop_start
                
                # Try to achieve at least 10 FPS for reasonable smoothness, regardless of target
                # But don't exceed target frame rate
                min_fps = min(10.0, configured_frame_rate)
                max_wait = 1.0 / min_fps
                target_wait = 1.0 / configured_frame_rate if configured_frame_rate > 0 else 0.1
                
                sleep_time = max(0, min(max_wait, target_wait - elapsed))
                await asyncio.sleep(sleep_time)
                
            except WebSocketDisconnect:
                print(f"WebSocket disconnected for camera {camera_id}")
                break
            except Exception as e:
                print(f"Error in streaming: {str(e)}")
                await asyncio.sleep(1.0)  # Wait before retrying
    
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for camera {camera_id}")
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
    finally:
        # Log final statistics
        end_time = time.time()
        total_duration = end_time - start_time
        if frame_count > 0:
            final_fps = frame_count / total_duration
            print(f"Camera {camera_id} WebSocket connection closed:")
            print(f"  - Total frames: {frame_count}, Duration: {total_duration:.2f}s")
            print(f"  - Average FPS: {final_fps:.2f}")
        
        # Always release the camera when done
        if cap and cap.isOpened():
            cap.release()
        # Remove from active connections
        if camera_id in active_connections and websocket in active_connections[camera_id]:
            active_connections[camera_id].remove(websocket)
            if not active_connections[camera_id]:
                del active_connections[camera_id]

# The implementation for multiple cameras would need similar modifications
@router.websocket("/ws/detections")
async def multiple_detections(
    websocket: WebSocket, 
    camera_ids: str = Query(...),  # Comma-separated list of camera IDs
    token: Optional[str] = Query(None),
    frame_rate: Optional[int] = Query(None)  # Add explicit frame_rate parameter
):
    """
    WebSocket endpoint for real-time video streaming from multiple cameras
    Requires a valid JWT token as a query parameter
    """
    # Verify the token
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing authentication token")
        return
        
    user = await verify_token(token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid authentication token")
        return
    
    # Parse camera IDs
    try:
        camera_id_list = [int(cid.strip()) for cid in camera_ids.split(",") if cid.strip()]
    except ValueError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid camera IDs format")
        return
    
    if not camera_id_list:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="No camera IDs provided")
        return
    
    # Verify all cameras exist and prepare camera sources
    camera_sources = {}
    camera_captures = {}
    for cam_id in camera_id_list:
        camera = get_camera_by_id(cam_id)
        if not camera:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=f"Camera with ID {cam_id} not found")
            return
        
        # Get camera source path
        source_path = _fetch_camera_source_by_id(cam_id)
        if not source_path:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=f"Camera source not found for camera_id={cam_id}")
            return
        
        camera_sources[cam_id] = source_path
        
        # Open video capture
        cap = cv2.VideoCapture(source_path)
        if not cap.isOpened():
            # Close any already opened captures
            for opened_cap in camera_captures.values():
                opened_cap.release()
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=f"Failed to open camera/video source '{source_path}'")
            return
        
        camera_captures[cam_id] = cap
    
    # Accept the connection
    await websocket.accept()
    
    # Send initial confirmation
    await websocket.send_json({
        "status": "connected",
        "message": f"Connected to view {len(camera_id_list)} cameras",
        "camera_ids": camera_id_list
    })
    
    # Track camera data and state
    camera_data = {}
    
    # Performance tracking for multiple cameras
    start_time = time.time()
    total_frames = 0
    frames_per_camera = {cam_id: 0 for cam_id in camera_id_list}
    last_metrics_time = start_time
    
    # Initialize camera data with detection intervals from calibration
    for camera_id in camera_id_list:
        # Get calibration data to determine frame rate
        calib_data = fetch_calibration_for_camera(camera_id)
        
        # Calculate detection interval from frame_rate in calibration
        if calib_data and "frame_rate" in calib_data:
            frame_rate = calib_data.get("frame_rate", 5)  # Default to 5 FPS
            # Ensure frame_rate is valid
            if frame_rate <= 0:
                frame_rate = 5  # Fallback to 5 FPS
            # Convert frame_rate to detection interval (seconds between detections)
            detection_interval = 1.0 / frame_rate
            log_message = f"Using configured frame rate from calibration: {frame_rate} FPS (interval: {detection_interval:.3f}s)"
        else:
            # Default values if no calibration data
            frame_rate = 5
            detection_interval = 0.2  # Default 5 FPS
            log_message = f"No frame rate in calibration, using default: {frame_rate} FPS (interval: {detection_interval:.3f}s)"
        
        print(f"Camera {camera_id}: {log_message}")
        
        camera_data[camera_id] = {
            "source_path": _fetch_camera_source_by_id(camera_id),
            "detection_result": None,
            "last_detection_time": 0,
            "detection_interval": detection_interval,
            "last_frame_time": time.time(),
            "processing_times": [],
            "send_times": []
        }
    
    # Main processing loop
    try:
        while True:
            try:
                # Process a single camera at a time in a round-robin fashion
                current_index = 0
                for camera_id in camera_id_list:
                    # Skip cameras with invalid source paths
                    if not camera_data[camera_id]["source_path"]:
                        continue
                        
                    # Get camera source
                    source_path = camera_data[camera_id]["source_path"]
                    
                    # Open video capture
                    cap = cv2.VideoCapture(source_path)
                    if not cap.isOpened():
                        await websocket.send_json({
                            "status": "error",
                            "message": f"Failed to open camera/video source '{source_path}'"
                        })
                        continue
                    
                    loop_start = time.time()
                    
                    # Read frame
                    ret, frame = cap.read()
                    
                    if not ret or frame is None:
                        cap.release()
                        await websocket.send_json({
                            "status": "error",
                            "message": f"Unable to read a frame from camera {camera_id}"
                        })
                        continue
                    
                    # Resize the frame to a smaller size for WebSocket streaming
                    frame = _resize_frame(frame, max_height=180)
                    
                    processing_start = time.time()
                    
                    # Only run detection based on the camera's frame rate/interval
                    current_time = time.time()
                    camera_data_obj = camera_data[camera_id]
                    last_detection_time = camera_data_obj["last_detection_time"]
                    detection_interval = camera_data_obj["detection_interval"]
                    
                    if current_time - last_detection_time >= detection_interval:
                        # Run detection in background (non-blocking)
                        detection_task = asyncio.create_task(asyncio.to_thread(detect_person_crossing, camera_id))
                        try:
                            # Wait with a timeout to avoid blocking the stream
                            detection_result = await asyncio.wait_for(detection_task, timeout=0.2)
                            camera_data_obj["detection_result"] = detection_result
                            camera_data_obj["last_detection_time"] = current_time
                        except asyncio.TimeoutError:
                            # Detection is taking too long, continue with the stream
                            pass
                    else:
                        # Use the cached result
                        detection_result = camera_data_obj["detection_result"]
                    
                    # Record processing time
                    processing_time = time.time() - processing_start
                    camera_data_obj["processing_times"].append(processing_time)
                    
                    # Encode frame to JPEG and then base64
                    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 60]  # 60% quality
                    success, encoded_img = cv2.imencode(".jpg", frame, encode_params)
                    if not success:
                        cap.release()
                        continue
                        
                    frame_base64 = base64.b64encode(encoded_img.tobytes()).decode('utf-8')
                    
                    # Format the response
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if detection_result:
                        timestamp = detection_result.get("timestamp", timestamp)
                    timestamp_iso = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").isoformat()
                    
                    # Format detection results
                    detections = []
                    event = None
                    status = "no_motion"
                    crossing_detected = False
                    
                    if detection_result:
                        # Format bounding boxes
                        for bbox in detection_result.get("bounding_boxes", []):
                            detections.append({
                                "label": "person",  # Currently only detecting people
                                "confidence": 0.9,  # Placeholder, real confidence scores would be better
                                "bbox": bbox
                            })
                        
                        # Check if an event was detected
                        if "status" in detection_result:
                            status = detection_result["status"]
                            if status == "entry_detected":
                                event = "entry"
                            elif status == "exit_detected":
                                event = "exit"
                            
                        crossing_detected = detection_result.get("crossing_detected", False)
                    
                    # Create response
                    response = DetectionWSResponse(
                        camera_id=camera_id,
                        timestamp=timestamp_iso,
                        frame=frame_base64,
                        detections=detections,
                        event=event,
                        status=status,
                        crossing_detected=crossing_detected
                    )
                    
                    # Track send time
                    send_start = time.time()
                    
                    # Send update to client
                    await websocket.send_json(response.dict())
                    
                    # Track send completion
                    send_time = time.time() - send_start
                    camera_data_obj["send_times"].append(send_time)
                    
                    # Track frame time
                    current_time = time.time()
                    frame_interval = current_time - camera_data_obj["last_frame_time"]
                    camera_data_obj["last_frame_time"] = current_time
                    
                    # Update frame counters
                    total_frames += 1
                    frames_per_camera[camera_id] += 1
                    
                    # Close the capture
                    cap.release()
                    
                    # Log performance metrics periodically
                    if current_time - last_metrics_time >= 10.0:  # Every 10 seconds
                        elapsed = current_time - start_time
                        overall_fps = total_frames / elapsed
                        
                        print(f"Multiple camera WebSocket metrics after {elapsed:.1f}s:")
                        print(f"  - Total frames: {total_frames}, Overall FPS: {overall_fps:.2f}")
                        
                        for cam_id in camera_id_list:
                            cam_frames = frames_per_camera[cam_id]
                            cam_fps = cam_frames / elapsed if elapsed > 0 else 0
                            cam_data = camera_data[cam_id]
                            
                            # Calculate averages if we have data
                            avg_proc = sum(cam_data["processing_times"]) / len(cam_data["processing_times"]) if cam_data["processing_times"] else 0
                            avg_send = sum(cam_data["send_times"]) / len(cam_data["send_times"]) if cam_data["send_times"] else 0
                            
                            print(f"  - Camera {cam_id}: {cam_frames} frames, {cam_fps:.2f} FPS")
                            print(f"    Processing: {avg_proc:.4f}s, Send: {avg_send:.4f}s")
                            
                            # Limit array sizes
                            if len(cam_data["processing_times"]) > 100:
                                cam_data["processing_times"] = cam_data["processing_times"][-100:]
                            if len(cam_data["send_times"]) > 100:
                                cam_data["send_times"] = cam_data["send_times"][-100:]
                        
                        last_metrics_time = current_time
                
                # Add a small delay between iterations
                await asyncio.sleep(0.05)
                
            except WebSocketDisconnect:
                print(f"WebSocket disconnected for multiple cameras")
                break
            except Exception as e:
                print(f"Error in multiple camera streaming: {str(e)}")
                # Move to next camera if there's an error with the current one
                current_index = (current_index + 1) % len(camera_id_list)
                await asyncio.sleep(1.0)  # Wait before retrying
            
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for multiple cameras")
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
    finally:
        # Log final statistics
        end_time = time.time()
        total_duration = end_time - start_time
        
        if total_frames > 0:
            overall_fps = total_frames / total_duration
            print(f"Multiple camera WebSocket connection closed:")
            print(f"  - Total duration: {total_duration:.2f}s")
            print(f"  - Total frames: {total_frames}, Overall FPS: {overall_fps:.2f}")
            
            for cam_id in camera_id_list:
                cam_frames = frames_per_camera[cam_id]
                cam_fps = cam_frames / total_duration if total_duration > 0 else 0
                print(f"  - Camera {cam_id}: {cam_frames} frames, {cam_fps:.2f} FPS")
        
        # Release all camera captures
        for cam_id, cap in camera_captures.items():
            if cap and cap.isOpened():
                cap.release()
                
        # Remove from active connections for all cameras
        for cam_id in camera_id_list:
            if cam_id in active_connections and websocket in active_connections[cam_id]:
                active_connections[cam_id].remove(websocket)
                if not active_connections[cam_id]:
                    del active_connections[cam_id] 