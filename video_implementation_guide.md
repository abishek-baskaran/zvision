# ZVision WebRTC and Object Detection Implementation Guide

This guide provides detailed instructions for frontend developers to implement WebRTC video streaming with real-time object detection using the ZVision backend API. It covers establishing WebRTC connections, handling authentication, managing detection services, and rendering detection results.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Authentication](#authentication)
4. [WebRTC Connection Setup](#webrtc-connection-setup)
5. [Working with Object Detection](#working-with-object-detection)
6. [Rendering Detection Results](#rendering-detection-results)
7. [Error Handling](#error-handling)
8. [Implementation Example](#implementation-example)

## Overview

The ZVision platform provides a WebRTC-based video streaming solution with real-time object detection capabilities. This document explains how to integrate these features into your frontend application.

### System Architecture

- **Backend**: FastAPI application with WebRTC and detection endpoints
- **Frontend**: Any web application capable of WebRTC connections (JS/TS)
- **Communication**: REST API for control, WebRTC for video streaming
- **Detection**: YOLO-based object detection that processes video frames

## Prerequisites

- JavaScript/TypeScript knowledge
- Understanding of WebRTC concepts (peers, ICE candidates, etc.)
- Modern web browser with WebRTC support
- Access credentials for the ZVision API

## Authentication

All API endpoints require JWT authentication:

```javascript
// Authentication example
async function getAuthToken() {
    const response = await fetch('/api/auth/token', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            username: 'user@example.com',
            password: 'yourpassword'
        })
    });
    
    if (!response.ok) {
        throw new Error('Authentication failed');
    }
    
    const data = await response.json();
    return data.access_token;
}

// Use the token in all API requests
const token = await getAuthToken();
```

## WebRTC Connection Setup

### 1. Create RTCPeerConnection

```javascript
// Initialize WebRTC connection
function createPeerConnection() {
    // Create a new RTCPeerConnection
    const peerConnection = new RTCPeerConnection({
        iceServers: [
            { urls: 'stun:stun.l.google.com:19302' }
            // Add TURN servers if needed
        ]
    });
    
    // Add event listeners
    peerConnection.ontrack = handleTrack;
    peerConnection.onicecandidate = handleICECandidate;
    peerConnection.oniceconnectionstatechange = handleICEConnectionStateChange;
    
    return peerConnection;
}
```

### 2. Handle Video Track

```javascript
// Handle incoming video track
function handleTrack(event) {
    if (event.track.kind === 'video') {
        const videoElement = document.getElementById('video-element');
        videoElement.srcObject = event.streams[0];
    }
}
```

### 3. Send Offer to Server

```javascript
// Generate and send offer to server
async function startWebRTC(cameraId, token) {
    const peerConnection = createPeerConnection();
    
    // Create an offer
    const offer = await peerConnection.createOffer({
        offerToReceiveVideo: true,
        offerToReceiveAudio: false
    });
    
    // Set local description
    await peerConnection.setLocalDescription(offer);
    
    // Send offer to server
    const response = await fetch(`/api/webrtc/${cameraId}/offer`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
            sdp: peerConnection.localDescription.sdp,
            type: peerConnection.localDescription.type
        })
    });
    
    // Handle server response with answer
    const answerData = await response.json();
    const remoteDesc = new RTCSessionDescription(answerData);
    await peerConnection.setRemoteDescription(remoteDesc);
    
    return peerConnection;
}
```

### 4. Handle ICE Candidates

```javascript
// Send ICE candidates to server
async function handleICECandidate(event) {
    if (event.candidate) {
        await fetch(`/api/webrtc/${cameraId}/ice`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                candidate: event.candidate.candidate,
                sdpMid: event.candidate.sdpMid,
                sdpMLineIndex: event.candidate.sdpMLineIndex
            })
        });
    }
}
```

### 5. Monitor Connection State

```javascript
// Handle ICE connection state changes
function handleICEConnectionStateChange(event) {
    const state = peerConnection.iceConnectionState;
    
    switch (state) {
        case 'connected':
        case 'completed':
            console.log('WebRTC connection established');
            break;
        case 'failed':
        case 'disconnected':
        case 'closed':
            console.log('WebRTC connection closed or failed');
            // Handle reconnection if needed
            break;
    }
}
```

## Working with Object Detection

### 1. Start Detection

```javascript
// Configure and start detection for a camera
async function startDetection(cameraId, token, frameRateFPS = 5) {
    try {
        // Calculate interval in seconds from FPS
        const intervalSeconds = Math.round(1.0 / frameRateFPS);
        
        // Call the detection configuration endpoint
        const response = await fetch(`/api/detection/config`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                camera_id: parseInt(cameraId, 10),
                interval_seconds: intervalSeconds,
                enabled: true
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(`Failed to start detection: ${errorData.detail || response.statusText}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('Error starting detection:', error);
        throw error;
    }
}
```

### 2. Stop Detection

```javascript
// Stop detection for a camera
async function stopDetection(cameraId, token) {
    try {
        const response = await fetch(`/api/detection/config`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                camera_id: parseInt(cameraId, 10),
                interval_seconds: 10, // Default value
                enabled: false
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(`Failed to stop detection: ${errorData.detail || response.statusText}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('Error stopping detection:', error);
        throw error;
    }
}
```

### 3. Get Detection Results

```javascript
// Get detection results for a camera
async function getDetectionResults(cameraId, token) {
    try {
        // Using query parameter approach
        const response = await fetch(`/api/detect?camera_id=${cameraId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!response.ok) {
            if (response.status === 404) {
                return null; // No detection active
            }
            throw new Error(`Server returned ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('Error getting detection results:', error);
        throw error;
    }
}
```

## Rendering Detection Results

### 1. Setup Canvas Overlay

```html
<!-- HTML Setup for Video and Detection Overlay -->
<div class="video-container">
    <video id="video-element" autoplay playsinline></video>
    <canvas id="detection-canvas"></canvas>
</div>

<style>
.video-container {
    position: relative;
    width: 640px;
    height: 480px;
}

#video-element, #detection-canvas {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
}

#detection-canvas {
    pointer-events: none;
}
</style>
```

### 2. Draw Detection Boxes

```javascript
// Draw detection boxes on canvas
function drawDetectionBoxes(detections, canvasContext, videoElement) {
    // Get canvas dimensions 
    const canvas = canvasContext.canvas;
    const videoWidth = videoElement.videoWidth;
    const videoHeight = videoElement.videoHeight;
    
    // Scale factor for different video/canvas dimensions
    const scaleX = canvas.width / videoWidth;
    const scaleY = canvas.height / videoHeight;
    
    // Clear previous drawings
    canvasContext.clearRect(0, 0, canvas.width, canvas.height);
    
    // No detections to show
    if (!detections || detections.length === 0) {
        return;
    }
    
    // Set drawing styles
    canvasContext.lineWidth = 2;
    canvasContext.font = '14px Arial';
    canvasContext.fillStyle = 'white';
    
    // Draw each detection box
    detections.forEach(detection => {
        const [x1, y1, x2, y2] = detection.bbox;
        const width = x2 - x1;
        const height = y2 - y1;
        
        // Scale coordinates to canvas size
        const scaledX = x1 * scaleX;
        const scaledY = y1 * scaleY;
        const scaledWidth = width * scaleX;
        const scaledHeight = height * scaleY;
        
        // Choose color based on class or confidence
        const confidence = detection.confidence || 0;
        const hue = 120 * confidence; // 0-120 (red to green) based on confidence
        canvasContext.strokeStyle = `hsl(${hue}, 100%, 50%)`;
        
        // Draw rectangle
        canvasContext.strokeRect(scaledX, scaledY, scaledWidth, scaledHeight);
        
        // Draw label
        const label = `${detection.class_name} ${Math.round(confidence * 100)}%`;
        const textWidth = canvasContext.measureText(label).width;
        
        canvasContext.fillStyle = `hsl(${hue}, 100%, 30%)`;
        canvasContext.fillRect(
            scaledX, 
            scaledY - 20, 
            textWidth + 10, 
            20
        );
        
        canvasContext.fillStyle = 'white';
        canvasContext.fillText(
            label, 
            scaledX + 5, 
            scaledY - 5
        );
    });
}
```

### 3. Continuous Detection Loop

```javascript
// Poll for detection results and update the display
function startDetectionLoop(cameraId, token, canvasContext, videoElement) {
    // Set detection state
    const detection = {
        enabled: true,
        interval: null,
        lastDetectionTime: null
    };
    
    // Create polling interval
    detection.interval = setInterval(async () => {
        if (!detection.enabled || !videoElement.srcObject) {
            return;
        }
        
        try {
            // Get latest detection results
            const result = await getDetectionResults(cameraId, token);
            
            if (result && result.detections) {
                // Process and display detections
                drawDetectionBoxes(result.detections, canvasContext, videoElement);
                
                // Update last detection time
                detection.lastDetectionTime = new Date();
            }
        } catch (error) {
            console.error('Error in detection loop:', error);
        }
    }, 200); // Poll for results at 5 FPS (adjust as needed)
    
    return detection;
}
```

## Error Handling

```javascript
// Example error handling for WebRTC connections
function handleWebRTCErrors(error) {
    // Log the error
    console.error('WebRTC Error:', error);
    
    // Categorize errors
    if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
        // Camera not found
        return 'Camera not found or not accessible';
    } else if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
        // Permission denied
        return 'Camera access permission denied';
    } else if (error.name === 'NotReadableError' || error.name === 'TrackStartError') {
        // Hardware or system error
        return 'Camera is in use by another application';
    } else if (error.name === 'InvalidStateError') {
        // WebRTC state error
        return 'WebRTC is in an invalid state';
    } else {
        // Other errors
        return `Connection error: ${error.message}`;
    }
}
```

## Implementation Example

Here's a simple integration example that combines the elements above:

```javascript
// Main implementation function
async function initializeVideoDetection(cameraId) {
    try {
        // Get authentication token
        const token = await getAuthToken();
        
        // Set up video element and canvas
        const videoElement = document.getElementById('video-element');
        const detectionCanvas = document.getElementById('detection-canvas');
        const canvasContext = detectionCanvas.getContext('2d');
        
        // Size canvas to match video container
        const container = document.querySelector('.video-container');
        detectionCanvas.width = container.clientWidth;
        detectionCanvas.height = container.clientHeight;
        
        // Initialize WebRTC
        const peerConnection = await startWebRTC(cameraId, token);
        
        // When video starts playing, set up canvas dimensions
        videoElement.addEventListener('playing', () => {
            // Handle video resize if needed
            if (videoElement.videoWidth) {
                const aspectRatio = videoElement.videoWidth / videoElement.videoHeight;
                if (aspectRatio > 1) {
                    // Landscape
                    detectionCanvas.width = container.clientWidth;
                    detectionCanvas.height = container.clientWidth / aspectRatio;
                } else {
                    // Portrait
                    detectionCanvas.height = container.clientHeight;
                    detectionCanvas.width = container.clientHeight * aspectRatio;
                }
            }
        });
        
        // Start detection
        await startDetection(cameraId, token, 5); // 5 FPS
        
        // Start detection results loop
        const detection = startDetectionLoop(cameraId, token, canvasContext, videoElement);
        
        // Return cleanup function
        return async () => {
            // Stop detection
            if (detection.interval) {
                clearInterval(detection.interval);
            }
            
            // Stop detection on server
            await stopDetection(cameraId, token);
            
            // Close WebRTC connection
            if (peerConnection) {
                peerConnection.close();
            }
        };
    } catch (error) {
        console.error('Failed to initialize video detection:', error);
        throw error;
    }
}

// Usage
document.addEventListener('DOMContentLoaded', async () => {
    try {
        const cameraId = 1; // Example camera ID
        const cleanup = await initializeVideoDetection(cameraId);
        
        // Save cleanup function for later use
        window.stopVideoDetection = cleanup;
        
        // Example: Stop detection when leaving the page
        window.addEventListener('beforeunload', () => {
            if (window.stopVideoDetection) {
                window.stopVideoDetection();
            }
        });
    } catch (error) {
        // Display error to user
        document.getElementById('error-message').textContent = 
            `Failed to start video: ${error.message}`;
    }
});
```

## Summary

This implementation guide covers the essential steps for integrating WebRTC video streaming with real-time object detection into your frontend application. Key points to remember:

1. Always handle authentication properly and send tokens with each request
2. Create and manage WebRTC peer connections carefully
3. Poll for detection results at a reasonable frequency
4. Scale detection boxes properly to match video dimensions
5. Implement proper cleanup functions to stop streams and detection

---

## Appendix: API Endpoints Reference

### WebRTC Endpoints

| Endpoint | Method | Description | Request Body | Response |
|----------|--------|-------------|-------------|----------|
| `/api/webrtc/{camera_id}/offer` | POST | Send WebRTC offer | `{sdp: string, type: string}` | WebRTC answer |
| `/api/webrtc/{camera_id}/ice` | POST | Send ICE candidate | `{candidate: string, sdpMid: string, sdpMLineIndex: number}` | Success status |

### Detection Endpoints

| Endpoint | Method | Description | Request Body | Response |
|----------|--------|-------------|-------------|----------|
| `/api/detect` | POST | Trigger on-demand detection | `{"camera_id": string}` or query param | Detection results |
| `/api/detection/config` | POST | Configure automatic detection | `{"camera_id": int, "interval_seconds": int, "enabled": bool}` | Configuration status |

### Authentication Endpoints

| Endpoint | Method | Description | Request Body | Response |
|----------|--------|-------------|-------------|----------|
| `/api/auth/token` | POST | Get auth token | `{"username": string, "password": string}` | `{"access_token": string, "token_type": string}` |
