"""
aiortc-based WebRTC implementation for ZVision.

This module provides proper WebRTC functionality for the ZVision system 
using the aiortc library. It replaces the previous custom SDP manipulation
with standard-compliant WebRTC.
"""

import asyncio
import logging
import uuid
from typing import Dict, Optional, List, Any

try:
    # Import aiortc components - these will be optional for now
    # Full implementation will be in Phase 2
    from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
    from aiortc.contrib.media import MediaPlayer, MediaRelay
    from aiortc.mediastreams import MediaStreamError
    
    AIORTC_AVAILABLE = True
except ImportError:
    logging.warning("aiortc not installed. Using placeholder implementation.")
    AIORTC_AVAILABLE = False

# Import our custom video track implementation
try:
    from app.webrtc.aiortc_streaming import get_camera_track, cleanup_old_captures
except ImportError:
    logging.warning("aiortc_streaming module not available.")

# Import camera source helper
from app.routes.camera import _fetch_camera_source_by_id

# Configure logging
logger = logging.getLogger(__name__)

# Store active peer connections
peer_connections: Dict[str, Any] = {}
stream_relays: Dict[int, Any] = {}

# Store active tracks to prevent garbage collection
active_tracks: Dict[str, Any] = {}

async def create_peer_connection(connection_id: str, camera_id: int) -> Any:
    """
    Create a new RTCPeerConnection for a specific connection.
    """
    if not AIORTC_AVAILABLE:
        logger.warning("aiortc not installed. Cannot create real peer connection.")
        return None
    
    pc = RTCPeerConnection()
    peer_connections[connection_id] = pc
    
    # Store camera ID for reference
    pc.camera_id = camera_id
    
    # Set up connection cleanup
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        logger.info(f"Connection state for {connection_id}: {pc.connectionState}")
        if pc.connectionState == "failed" or pc.connectionState == "closed":
            await cleanup_peer_connection(connection_id)
    
    # Log ICE connection state changes
    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        logger.info(f"ICE connection state for {connection_id}: {pc.iceConnectionState}")
    
    # Log signaling state changes
    @pc.on("signalingstatechange")
    async def on_signalingstatechange():
        logger.info(f"Signaling state for {connection_id}: {pc.signalingState}")
    
    # Add media tracks for the camera
    await add_camera_tracks(pc, connection_id, camera_id)
    
    return pc

async def add_camera_tracks(pc: Any, connection_id: str, camera_id: int) -> bool:
    """
    Add video tracks from the camera to the peer connection.
    
    Args:
        pc: RTCPeerConnection to add tracks to
        connection_id: Unique identifier for this connection
        camera_id: ID of the camera to stream
        
    Returns:
        True if successfully added tracks, False otherwise
    """
    if not AIORTC_AVAILABLE:
        return False
    
    try:
        # Get the camera source path
        source_path = _fetch_camera_source_by_id(camera_id)
        if not source_path:
            logger.warning(f"Camera source not found for camera_id={camera_id}, using mock camera")
            # Use a placeholder source to create a mock camera
            source_path = f"mock:{camera_id}"
        
        # Create video track options
        options = {
            "fps": 30.0,  # Default FPS
            "width": 640,
            "height": 480,
            # If source starts with 'mock:', force using the mock camera
            "use_mock": source_path.startswith("mock:") or not source_path
        }
        
        # Get a video track for this camera
        video_track = get_camera_track(camera_id, source_path, options)
        if not video_track:
            logger.error(f"Failed to create video track for camera {camera_id}")
            return False
        
        # Save track reference to prevent garbage collection
        active_tracks[connection_id] = video_track
        
        # Add track to peer connection
        pc.addTrack(video_track)
        logger.info(f"Added video track for camera {camera_id} to connection {connection_id}")
        
        return True
    except Exception as e:
        logger.error(f"Error adding camera tracks for {camera_id}: {str(e)}")
        return False

async def process_offer(connection_id: str, camera_id: int, offer_sdp: str) -> str:
    """
    Process a WebRTC offer and return an answer.
    
    Args:
        connection_id: Unique identifier for this connection
        camera_id: ID of the camera to stream
        offer_sdp: SDP offer from the client
    
    Returns:
        SDP answer to send to the client
    """
    if not AIORTC_AVAILABLE:
        logger.warning("aiortc not installed. Cannot process offer properly.")
        # Return minimal SDP to indicate this is not functional for media
        return "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n"
    
    # Create peer connection if it doesn't exist
    if connection_id not in peer_connections:
        pc = await create_peer_connection(connection_id, camera_id)
    else:
        pc = peer_connections[connection_id]
    
    if not pc:
        logger.error(f"Failed to create peer connection for {connection_id}")
        return "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n"
    
    # Create session description from offer
    offer = RTCSessionDescription(sdp=offer_sdp, type="offer")
    
    try:
        # Set remote description
        await pc.setRemoteDescription(offer)
        
        # Create answer
        answer = await pc.createAnswer()
        
        # Set local description
        await pc.setLocalDescription(answer)
        
        # Ensure the media sections in the answer match the order in the offer
        corrected_sdp = ensure_sdp_media_order(offer_sdp, pc.localDescription.sdp)
        
        # Log the SDP for debugging
        logger.info(f"Created answer for {connection_id}")
        logger.debug(f"Original answer SDP: {pc.localDescription.sdp[:100]}...")
        logger.debug(f"Corrected answer SDP: {corrected_sdp[:100]}...")
        
        return corrected_sdp
    except Exception as e:
        logger.error(f"Error processing offer for {connection_id}: {str(e)}")
        return "v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n"

def ensure_sdp_media_order(offer_sdp: str, answer_sdp: str) -> str:
    """
    Ensure that the media sections in the answer SDP match the order in the offer SDP.
    
    This is critical for WebRTC compatibility, especially with browser clients.
    The issue occurs when adaptive bandwidth features add additional m-lines or reorder existing ones.
    
    Args:
        offer_sdp: The SDP offer from the client
        answer_sdp: The SDP answer generated by aiortc
        
    Returns:
        Modified answer SDP with media sections in the same order as the offer
    """
    # Split SDPs into lines
    offer_lines = offer_sdp.split('\r\n')
    answer_lines = answer_sdp.split('\r\n')
    
    # Find all media sections in offer and answer
    offer_media_indices = [i for i, line in enumerate(offer_lines) if line.startswith('m=')]
    answer_media_indices = [i for i, line in enumerate(answer_lines) if line.startswith('m=')]
    
    # If there's a mismatch in the number of media sections, we can't fix it
    # Just return the original answer and log a warning
    if len(offer_media_indices) != len(answer_media_indices):
        logger.warning(f"Offer has {len(offer_media_indices)} media sections, but answer has {len(answer_media_indices)}. Cannot ensure order.")
        return answer_sdp
    
    # If there's only one media section, no reordering needed
    if len(offer_media_indices) <= 1:
        return answer_sdp
    
    # Extract media types from offer and answer
    offer_media_types = []
    for idx in offer_media_indices:
        media_line = offer_lines[idx]
        media_type = media_line.split(' ')[0].split('=')[1]  # Extract 'audio', 'video', etc.
        offer_media_types.append(media_type)
    
    answer_media_types = []
    answer_media_sections = []
    
    # Extract each media section from the answer
    for i in range(len(answer_media_indices)):
        start_idx = answer_media_indices[i]
        end_idx = answer_media_indices[i+1] if i+1 < len(answer_media_indices) else len(answer_lines)
        
        media_line = answer_lines[start_idx]
        media_type = media_line.split(' ')[0].split('=')[1]
        answer_media_types.append(media_type)
        
        # Store the entire media section
        media_section = answer_lines[start_idx:end_idx]
        answer_media_sections.append(media_section)
    
    # If media types don't match between offer and answer, we can't reorder
    if set(offer_media_types) != set(answer_media_types):
        logger.warning(f"Media types in offer {offer_media_types} don't match answer {answer_media_types}. Cannot ensure order.")
        return answer_sdp
    
    # Reorder answer media sections to match offer order
    reordered_answer = []
    
    # Add everything before the first media section
    reordered_answer.extend(answer_lines[:answer_media_indices[0]])
    
    # Add media sections in the order they appear in the offer
    for media_type in offer_media_types:
        idx = answer_media_types.index(media_type)
        reordered_answer.extend(answer_media_sections[idx])
    
    # Join back into SDP format
    return '\r\n'.join(reordered_answer)

async def add_ice_candidate(connection_id: str, candidate: dict) -> bool:
    """
    Add an ICE candidate to a peer connection.
    
    Args:
        connection_id: ID of the connection
        candidate: ICE candidate from the client
    
    Returns:
        True if successful, False otherwise
    """
    if not AIORTC_AVAILABLE:
        logger.warning("aiortc not installed. Cannot add ICE candidate.")
        return False
    
    if connection_id not in peer_connections:
        logger.error(f"Cannot add ICE candidate: connection {connection_id} not found")
        return False
    
    pc = peer_connections[connection_id]
    try:
        await pc.addIceCandidate(candidate)
        logger.debug(f"Added ICE candidate for {connection_id}")
        return True
    except Exception as e:
        logger.error(f"Error adding ICE candidate for {connection_id}: {str(e)}")
        return False

async def cleanup_peer_connection(connection_id: str) -> None:
    """
    Clean up a peer connection when it's no longer needed.
    """
    if not AIORTC_AVAILABLE:
        return
    
    if connection_id in peer_connections:
        pc = peer_connections[connection_id]
        
        try:
            # Close the peer connection
            await pc.close()
            
            # Remove from dictionary
            del peer_connections[connection_id]
            
            # Stop and remove any active tracks
            if connection_id in active_tracks:
                track = active_tracks[connection_id]
                if hasattr(track, 'stop'):
                    track.stop()
                del active_tracks[connection_id]
            
            logger.info(f"Cleaned up peer connection {connection_id}")
            
            # Run cleanup of old captures
            cleanup_old_captures()
        except Exception as e:
            logger.error(f"Error cleaning up peer connection {connection_id}: {str(e)}")

async def cleanup_camera_connections(camera_id: int) -> None:
    """
    Clean up all connections for a specific camera.
    """
    if not AIORTC_AVAILABLE:
        return
    
    # Filter connections for this camera
    camera_connections = [
        conn_id for conn_id, pc in peer_connections.items() 
        if getattr(pc, "camera_id", None) == camera_id
    ]
    
    for connection_id in camera_connections:
        await cleanup_peer_connection(connection_id)
    
    # Clean up any media relay
    if camera_id in stream_relays:
        # No specific cleanup needed for MediaRelay
        del stream_relays[camera_id]
        logger.info(f"Cleaned up media relay for camera {camera_id}") 