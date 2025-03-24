"""
Mock camera implementation for WebRTC testing.

This module provides a mock camera source that generates 
test patterns for WebRTC streaming when a real camera is not available.
"""

import cv2
import numpy as np
import time
import logging
from typing import Tuple, Dict, Any

# Configure logging
logger = logging.getLogger(__name__)

class MockCamera:
    """
    Mock camera that generates test patterns.
    
    This class simulates a camera by generating various test patterns that
    can be used for WebRTC streaming tests without requiring actual camera hardware.
    """
    
    def __init__(self, width=640, height=480, fps=30, pattern="color_bars"):
        """
        Initialize the mock camera.
        
        Args:
            width: Frame width in pixels
            height: Frame height in pixels
            fps: Frames per second
            pattern: Test pattern type ("color_bars", "checkerboard", "noise", "gradient", "moving_dot")
        """
        self.width = width
        self.height = height
        self.fps = fps
        self.pattern = pattern
        self.frame_count = 0
        self.start_time = time.time()
        
        # Initialize test pattern generators
        self.pattern_generators = {
            "color_bars": self._generate_color_bars,
            "checkerboard": self._generate_checkerboard,
            "noise": self._generate_noise,
            "gradient": self._generate_gradient,
            "moving_dot": self._generate_moving_dot
        }
        
        if pattern not in self.pattern_generators:
            logger.warning(f"Unknown pattern '{pattern}', defaulting to 'color_bars'")
            self.pattern = "color_bars"
            
        logger.info(f"Mock camera initialized with {width}x{height} @ {fps}fps, pattern: {pattern}")
    
    def _generate_color_bars(self) -> np.ndarray:
        """Generate color bars test pattern."""
        num_bars = 7
        bar_width = self.width // num_bars
        
        # Create color bars (ROYGBIV)
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        colors = [
            (0, 0, 255),     # Red
            (0, 165, 255),   # Orange
            (0, 255, 255),   # Yellow
            (0, 255, 0),     # Green
            (255, 0, 0),     # Blue
            (130, 0, 75),    # Indigo
            (255, 0, 170)    # Violet
        ]
        
        for i, color in enumerate(colors):
            x_start = i * bar_width
            x_end = (i + 1) * bar_width if i < num_bars - 1 else self.width
            frame[:, x_start:x_end] = color
            
        # Add timestamp
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(frame, timestamp, (10, 30), font, 1, (255, 255, 255), 2, cv2.LINE_AA)
        
        # Add frame counter
        cv2.putText(frame, f"Frame: {self.frame_count}", (10, 70), font, 1, (255, 255, 255), 2, cv2.LINE_AA)
        
        return frame
    
    def _generate_checkerboard(self) -> np.ndarray:
        """Generate checkerboard test pattern."""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        square_size = 40
        num_squares_x = self.width // square_size
        num_squares_y = self.height // square_size
        
        for y in range(num_squares_y):
            for x in range(num_squares_x):
                if (x + y) % 2 == 0:
                    y_start = y * square_size
                    y_end = (y + 1) * square_size
                    x_start = x * square_size
                    x_end = (x + 1) * square_size
                    frame[y_start:y_end, x_start:x_end] = (255, 255, 255)
        
        # Add timestamp
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(frame, timestamp, (10, 30), font, 1, (0, 255, 0), 2, cv2.LINE_AA)
        
        return frame
    
    def _generate_noise(self) -> np.ndarray:
        """Generate random noise test pattern."""
        frame = np.random.randint(0, 256, (self.height, self.width, 3), dtype=np.uint8)
        
        # Add timestamp
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(frame, timestamp, (10, 30), font, 1, (255, 255, 255), 2, cv2.LINE_AA)
        
        return frame
    
    def _generate_gradient(self) -> np.ndarray:
        """Generate gradient test pattern."""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Create horizontal gradient (black to blue)
        for x in range(self.width):
            blue_value = int(255 * x / self.width)
            frame[:, x] = (blue_value, 0, 0)
            
        # Create vertical gradient overlay (black to green)
        for y in range(self.height):
            green_value = int(255 * y / self.height)
            frame[y, :, 1] = green_value
            
        # Add timestamp
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(frame, timestamp, (10, 30), font, 1, (255, 255, 255), 2, cv2.LINE_AA)
        
        return frame
    
    def _generate_moving_dot(self) -> np.ndarray:
        """Generate moving dot test pattern."""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Calculate dot position based on frame count
        radius = 30
        period_x = 200  # frames for one complete cycle
        period_y = 300  # frames for one complete cycle
        
        x = int(self.width / 2 + (self.width / 2 - radius) * np.sin(2 * np.pi * self.frame_count / period_x))
        y = int(self.height / 2 + (self.height / 2 - radius) * np.cos(2 * np.pi * self.frame_count / period_y))
        
        # Draw the dot
        cv2.circle(frame, (x, y), radius, (0, 0, 255), -1)
        
        # Add crosshairs
        cv2.line(frame, (0, self.height // 2), (self.width, self.height // 2), (0, 255, 0), 1)
        cv2.line(frame, (self.width // 2, 0), (self.width // 2, self.height), (0, 255, 0), 1)
        
        # Add timestamp
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(frame, timestamp, (10, 30), font, 1, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(frame, f"Frame: {self.frame_count}", (10, 70), font, 1, (255, 255, 255), 2, cv2.LINE_AA)
        
        return frame
    
    def read(self) -> Tuple[bool, np.ndarray]:
        """
        Read a frame from the mock camera.
        
        Returns:
            (success, frame) tuple similar to cv2.VideoCapture.read()
        """
        # Generate the appropriate test pattern
        frame = self.pattern_generators[self.pattern]()
        
        # Simulate frame rate by calculating appropriate delay
        elapsed = time.time() - self.start_time
        expected_frames = int(elapsed * self.fps)
        if expected_frames <= self.frame_count:
            # We're generating frames too quickly, so we need to wait
            time.sleep((self.frame_count + 1) / self.fps - elapsed)
        
        self.frame_count += 1
        return True, frame
    
    def release(self) -> None:
        """Release the mock camera (no-op)."""
        logger.info("Mock camera released")
        pass
    
    def isOpened(self) -> bool:
        """Check if the mock camera is opened (always True)."""
        return True
    
    def get(self, prop_id):
        """
        Get camera property, similar to cv2.VideoCapture.get().
        
        Only supports basic properties like width, height, and fps.
        """
        if prop_id == cv2.CAP_PROP_FRAME_WIDTH:
            return self.width
        elif prop_id == cv2.CAP_PROP_FRAME_HEIGHT:
            return self.height
        elif prop_id == cv2.CAP_PROP_FPS:
            return self.fps
        else:
            return 0
    
    def set(self, prop_id, value):
        """
        Set camera property, similar to cv2.VideoCapture.set().
        
        Only supports basic properties like width, height, and fps.
        """
        if prop_id == cv2.CAP_PROP_FRAME_WIDTH:
            self.width = int(value)
            return True
        elif prop_id == cv2.CAP_PROP_FRAME_HEIGHT:
            self.height = int(value)
            return True
        elif prop_id == cv2.CAP_PROP_FPS:
            self.fps = value
            return True
        else:
            return False


def create_mock_camera(camera_id: int, options: Dict[str, Any] = None) -> MockCamera:
    """
    Create a mock camera with the given ID and options.
    
    Args:
        camera_id: Camera ID (used to seed different patterns)
        options: Camera options including width, height, fps, and pattern
        
    Returns:
        MockCamera instance
    """
    if options is None:
        options = {}
    
    width = options.get("width", 640)
    height = options.get("height", 480)
    fps = options.get("fps", 30)
    
    # Choose pattern based on camera_id to make different cameras have different patterns
    patterns = ["color_bars", "checkerboard", "gradient", "moving_dot"]
    pattern = patterns[camera_id % len(patterns)]
    
    # Override with provided pattern if specified
    if "pattern" in options:
        pattern = options["pattern"]
    
    return MockCamera(width=width, height=height, fps=fps, pattern=pattern) 