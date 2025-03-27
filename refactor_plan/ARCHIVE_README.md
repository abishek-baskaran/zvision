# ZVision Archive Documentation

## Overview
This document outlines the archiving process undertaken as part of the ZVision refactoring project. As the system architecture evolved through multiple phases, certain files became obsolete and were moved to an organized archive structure to maintain a clean codebase while preserving historical implementation for reference.

## Archive Structure
The archived files have been organized into the following directory structure:

```
app/archive/
├── inference/      # Old inference pipeline & detection files
├── services/       # Legacy service implementations
├── webrtc/         # Original WebRTC implementation files
├── routes/         # Previous API route handlers
├── tests/          # Outdated test scripts
├── temp/           # Temporary development and test files
└── main/           # Core application files from previous architecture
```

## Archived Files

### Inference Files
- **detection.py**: Original detection implementation using direct YOLO interface
- **pipeline.py**: Previous inference pipeline for frame processing

### WebRTC Files
- **mock_camera.py**: Simulated camera implementation used for testing
- **frame_extractor.py.original**: Original frame extraction logic before CameraManager integration

### Routes Files
- **camera.py.original**: Previous camera endpoint implementations
- **detection.py.original**: Legacy detection API routes

### Temporary Files
All files from `app/temp/` directory were archived, including:
- Various test HTML pages for WebRTC and WebSocket testing
- Test scripts for different API endpoints
- Utility scripts for testing authentication and camera calibration

## Refactoring Summary
The archiving process was a part of Phase 5 cleanup following the major architectural changes:

1. **Phase 1**: Introduced new module structure and files (camera_manager.py, detection_worker.py, analytics.py)
2. **Phase 2**: Moved camera capture to separate processes
3. **Phase 3**: Implemented detection in parallel processes
4. **Phase 4**: Added metrics and analytics
5. **Phase 5**: Optimized resource usage and cleaned up codebase

The current implementation now uses the new architecture with improved multiprocessing, shared memory for frame access, and dedicated detection workers for better performance and responsiveness.

## Accessing Archived Code
The archived code is maintained for reference purposes. Developers can examine these files to understand previous implementation approaches or to extract specific logic that might be needed in future development.

## Notes on Migration
The migration to the new architecture focused on:
- Separating camera capture and detection into independent processes
- Implementing efficient frame sharing through multiprocessing queues
- Improving error handling and recovery
- Enhancing metrics collection and monitoring
- Standardizing API responses and error reporting

This archive serves as documentation of the evolution of the ZVision system architecture. 