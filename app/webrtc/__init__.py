"""
WebRTC handling module for ZVision.

This package contains the aiortc-based WebRTC implementation for the ZVision system.
It handles WebRTC signaling and media streaming, replacing the custom SDP handling.
"""

import logging

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

try:
    # Try to import aiortc to check if it's available
    import aiortc
    logger.info("aiortc is available.")
    AIORTC_AVAILABLE = True
except ImportError:
    logger.warning("aiortc not installed. Using fallback implementation.")
    AIORTC_AVAILABLE = False 