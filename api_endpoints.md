# API Endpoints Documentation

## Base URL
`http://localhost:8000/api`

**CORS Configuration**  
The API implements Cross-Origin Resource Sharing (CORS) with the following settings:
- Allowed origins: 
  - `http://localhost:3000` (React dev server)
  - `http://localhost:5000` (Local production build)
  - `http://localhost:8081` (Optional: FastAPI dev server)
  - Your production domain
- Allowed methods: GET, POST, PUT, DELETE, OPTIONS
- Allowed headers: Content-Type, Authorization, Accept
- Credentials: Allowed

---

## Authentication

### `POST /token`
- **Description**: Get JWT access token for authenticated operations
- **Request Body**:
  ```json
  {
    "username": "string",
    "password": "string"
  }
  ```
- **Response**:
  ```json
  {
    "access_token": "jwt_token_string",
    "token_type": "bearer"
  }
  ```
- **CORS Support**: Full preflight support with OPTIONS method

---

## Stores Management

### `GET /stores`
- **Description**: List all registered stores
- **Authentication**: Bearer Token required
- **Response**:
  ```json
  [
    {
      "store_id": 1,
      "store_name": "Store A"
    }
  ]
  ```

### `POST /stores`
- **Description**: Create new store (Admin only)
- **Authentication**: Bearer Token required
- **Request Body**:
  ```json
  {
    "store_name": "New Store Name"
  }
  ```
- **Response**:
  ```json
  {
    "store_id": 2,
    "store_name": "New Store Name"
  }
  ```

---

## Camera Operations

### `GET /camera/feed`
- **Description**: Get live camera feed as JPEG stream
- **Query Parameters**:
  - `camera_id`: Integer (required)
- **Response**: JPEG image stream (`image/jpeg`)

### `GET /camera/{camera_id}/snapshot`
- **Description**: Get a single snapshot from the camera
- **Path Parameters**:
  - `camera_id`: Integer (required)
- **Response**: JPEG image (`image/jpeg`)

### `GET /cameras`
- **Description**: List cameras for a specific store
- **Query Parameters**:
  - `store_id`: Integer (required)
- **Response**:
  ```json
  {
    "store_id": 1,
    "cameras": [
      {
        "camera_id": 1,
        "camera_name": "Front Door",
        "source": "rtsp://..."
      }
    ]
  }
  ```

### `POST /cameras`
- **Description**: Create a new camera for a store
- **Request Body**:
  ```json
  {
    "store_id": 1,
    "camera_name": "Back Door",
    "source": "rtsp://example.com/stream"
  }
  ```
- **Response**:
  ```json
  {
    "message": "Camera created successfully",
    "camera_id": 3
  }
  ```

---

## Events & Logs

### `GET /logs`
- **Description**: Retrieve entry/exit events with filters
- **Query Parameters**:
  - `store_id`: Integer (required)
  - `start_date`: string (YYYY-MM-DD)
  - `end_date`: string (YYYY-MM-DD)
  - `event_type`: "entry" | "exit"
  - `limit`: integer
- **Response**:
  ```json
  {
    "store_id": 1,
    "total_events": 2,
    "events": [
      {
        "event_id": 1,
        "timestamp": "2024-02-20 12:00:00",
        "event_type": "entry",
        "camera_id": 1,
        "store_id": 1,
        "clip_path": "/clips/20240220-120000.mp4"
      }
    ]
  }
  ```

### `POST /events`
- **Description**: Record new entry/exit event
- **Request Body**:
  ```json
  {
    "event_type": "entry",
    "timestamp": "2024-02-20 12:00:00",
    "camera_id": 1,
    "store_id": 1,
    "clip_path": "/clips/20240220-120000.mp4"
  }
  ```
- **Response**:
  ```json
  {
    "status": "success",
    "event_id": 3
  }
  ```

---

## Calibration

### `POST /calibration` (or `/calibrate`)
- **Description**: Store camera calibration data
- **Request Body**:
  ```json
  {
    "camera_id": "1",
    "line": {
      "start": [0.1, 0.2],
      "end": [0.8, 0.9]
    },
    "square": {
      "top_left": [0.1, 0.1],
      "bottom_right": [0.9, 0.9]
    }
  }
  ```
- **Response**:
  ```json
  {
    "message": "Calibration saved successfully",
    "camera_id": 1,
    "line": {"start": [0.1, 0.2], "end": [0.8, 0.9]}
  }
  ```

### `GET /calibration` (or `/calibrate`)
- **Description**: Retrieve calibration data for a camera
- **Query Parameters**:
  - `camera_id`: String (required)
- **Response**:
  ```json
  {
    "message": "Calibration data retrieved successfully",
    "calibration": {
      "calibration_id": 1,
      "camera_id": 1,
      "line": {
        "start": [0.1, 0.2],
        "end": [0.8, 0.9]
      },
      "square": {
        "top_left": [0.1, 0.1],
        "bottom_right": [0.9, 0.9]
      }
    }
  }
  ```

---

## Detection

### `POST /detect`
- **Description**: Trigger person detection
- **Support for two methods**:
  1. Query Parameter: `/api/detect?camera_id=1`
  2. Request Body: `{"camera_id": "1"}`
- **Response**:
  ```json
  {
    "status": "motion_detected",
    "bounding_boxes": [[x1,y1,x2,y2], ...],
    "crossing_detected": true
  }
  ```

---

## System Health

### `GET /ping`
- **Description**: Basic health check
- **Response**:
  ```json
  {
    "status": "ok"
  }
  ```

---

## Security and Authentication Notes
1. JWT Authentication is implemented for protected endpoints
2. Protected endpoints require `Authorization: Bearer <token>` header
3. Token expiration: 30 minutes by default (configurable)
4. Admin privileges required for store creation
5. JWT tokens use HS256 algorithm for signing
6. OPTIONS preflight requests are properly supported for CORS operations 