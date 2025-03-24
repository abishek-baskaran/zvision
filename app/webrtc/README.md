# ZVision WebRTC Implementation

This module provides proper WebRTC functionality for the ZVision system using the [aiortc](https://github.com/aiortc/aiortc) library. 

## Overview

The implementation replaces the previous custom SDP manipulation with standard-compliant WebRTC.

### Implementation Phases

#### Phase 1: Setup and Signaling (Current)

- Removed custom/fake SDP handling
- Added proper WebRTC signaling with aiortc
- Implemented fallback mechanism for backward compatibility

#### Phase 2: Media Streaming (Upcoming)

- Add media tracks from camera sources
- Implement video streaming through WebRTC
- Optimize for low-latency streaming

## Requirements

Required Python packages:
- aiortc==1.5.0
- aiohttp==3.8.5
- av==9.3.0 (for media processing)
- pyee==9.0.4 (for event handling)

## Usage

The WebRTC implementation is integrated with the FastAPI routes in `app/routes/webrtc.py`. The routes handle signaling while the actual WebRTC functionality is provided by this module.

### Key Components

- `aiortc_handler.py`: Handles WebRTC peer connections, signaling, and ICE candidates
- `__init__.py`: Package initialization and availability checks

## Architecture

The implementation follows a layered architecture:

1. **API Layer** (`app/routes/webrtc.py`): Handles HTTP and WebSocket endpoints
2. **WebRTC Layer** (`app/webrtc/aiortc_handler.py`): Manages WebRTC connections and signaling
3. **Media Layer** (Coming in Phase 2): Will handle camera streams and media transport

## Fallback Mechanism

To ensure backward compatibility, the implementation includes fallback to the old custom SDP handling if aiortc fails or is not available.

## Future Improvements

- Add STUN/TURN server configuration
- Implement bandwidth adaptation
- Add multiple video quality options
- Support secure connections with DTLS 