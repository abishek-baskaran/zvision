# ZVision Frontend Authentication Guide

## Understanding the 401 Unauthorized Error with Protected Endpoints

When accessing protected endpoints like `/api/stores`, you need to include the JWT token in your request's Authorization header.

## Authentication Flow

1. After successful login, the backend returns a JWT token as `access_token` in the response
2. This token must be included in the Authorization header for all subsequent requests to protected endpoints
3. Without the token, you'll receive a 401 Unauthorized error

## How to Include the JWT Token

The header should use the Bearer authentication scheme:
```
Authorization: Bearer your_jwt_token_here
```

### Fetch Example

```javascript
// First, login and get the token
const loginResponse = await fetch('http://your-raspberrypi-ip:8000/api/auth/login', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    username: 'username',
    password: 'password'
  })
});

const { access_token } = await loginResponse.json();

// Store the token (localStorage, state management, etc.)
localStorage.setItem('token', access_token);

// Then, include it in subsequent requests
const storesResponse = await fetch('http://your-raspberrypi-ip:8000/api/stores', {
  headers: {
    'Authorization': `Bearer ${localStorage.getItem('token')}`
  }
});

const stores = await storesResponse.json();
```

### Axios Example

```javascript
// Login and get token
const loginResponse = await axios.post('http://your-raspberrypi-ip:8000/api/auth/login', {
  username: 'username',
  password: 'password'
});

const token = loginResponse.data.access_token;

// Store the token
localStorage.setItem('token', token);

// Use token in subsequent requests
const storesResponse = await axios.get('http://your-raspberrypi-ip:8000/api/stores', {
  headers: {
    'Authorization': `Bearer ${localStorage.getItem('token')}`
  }
});

const stores = storesResponse.data;
```

## Best Practices

1. **Store the token securely** - Consider using secure storage mechanisms like httpOnly cookies when possible
2. **Include token refresh logic** - JWTs expire (yours is set to expire in 30 minutes)
3. **Handle expired tokens** - Redirect to login when a token expires
4. **Set up interceptors** - If using axios, set up an interceptor to automatically include the token on every request:

```javascript
// Axios interceptor
axios.interceptors.request.use(config => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
```

## Debugging Authentication Issues

If you're still getting 401 Unauthorized errors:

1. Check the browser console to see the exact response
2. Verify the token is correctly stored and accessible
3. Confirm the token format in the header is exactly `Bearer your_token_here` (with a space after "Bearer")
4. Ensure your token hasn't expired (default is 30 minutes)

# Camera API Requirements for Frontend

## Issue
The frontend is currently sending only two fields when adding a camera:
- camera_name
- IP address

This is causing a 422 Unprocessable Entity error because the API requires three fields.

## API Requirements
The POST `/api/cameras` endpoint requires the following JSON body:

```json
{
  "store_id": 1,  // Required: The ID of the store this camera belongs to
  "camera_name": "Front Door Camera",  // Required: The name of the camera
  "source": "rtsp://192.168.1.100:554/stream1"  // Required: The IP address/URL of the camera
}
```

## Frontend Implementation
Here's how the frontend should structure the camera creation request:

```javascript
// Frontend code example
const addCamera = async (cameraData) => {
  const response = await fetch('/api/cameras', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      store_id: currentStoreId,  // Get this from the current store context
      camera_name: cameraData.name,
      source: cameraData.ipAddress  // Use the IP address as the source
    })
  });
  return response.json();
};
```

### Required Changes
1. Get the current store ID from wherever it's managing store state
2. Send the camera name as is
3. Use the IP address as the source field
4. Include all three fields in the request body

### Example Usage
```javascript
// Example of how to use the addCamera function
const handleAddCamera = async () => {
  try {
    const cameraData = {
      name: "Front Door Camera",
      ipAddress: "rtsp://192.168.1.100:554/stream1"
    };
    
    const result = await addCamera(cameraData);
    console.log('Camera added:', result);
  } catch (error) {
    console.error('Error adding camera:', error);
  }
};
```

### Response Format
The API will return a response in this format:
```json
{
  "camera_id": 1,
  "store_id": 1,
  "camera_name": "Front Door Camera",
  "source": "rtsp://192.168.1.100:554/stream1",
  "status": "online"
}
```

## Notes
- Make sure to include the JWT token in the Authorization header
- The store_id must be a valid store ID that exists in the database
- The source field should be a valid RTSP URL or local file path
- All fields are required and must be of the correct type (store_id: integer, camera_name: string, source: string)

## GET Camera Requests

### List Cameras for a Store
There are two ways to get cameras for a store:

1. Using path parameter (recommended):
```javascript
const getCamerasForStore = async (storeId) => {
  const response = await fetch(`/api/stores/${storeId}/cameras`, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  return response.json();
};
```

2. Using query parameter:
```javascript
const getCamerasForStore = async (storeId) => {
  const response = await fetch(`/api/cameras?store_id=${storeId}`, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  return response.json();
};
```

### Get Single Camera
To get details of a specific camera:
```javascript
const getCameraById = async (cameraId) => {
  const response = await fetch(`/api/cameras/${cameraId}`, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  return response.json();
};
```

### Response Format
Both endpoints will return an array of cameras in this format:
```json
[
  {
    "camera_id": 1,
    "store_id": 1,
    "camera_name": "Front Door Camera",
    "source": "rtsp://192.168.1.100:554/stream1",
    "status": "online"
  }
]
```

### Important Notes
1. The GET `/api/cameras` endpoint without a store_id parameter will return a 400 Bad Request error
2. Always include the store_id parameter when listing cameras
3. Make sure to include the JWT token in the Authorization header
4. The store_id must be a valid store ID that exists in the database

### Example Usage
```javascript
// Example of how to use the camera listing functions
const handleListCameras = async (storeId) => {
  try {
    // Using path parameter (recommended)
    const cameras = await getCamerasForStore(storeId);
    console.log('Cameras for store:', cameras);
    
    // Or using query parameter
    const camerasAlt = await getCamerasForStore(storeId);
    console.log('Cameras for store (alternative):', camerasAlt);
    
    // Get a specific camera
    if (cameras.length > 0) {
      const cameraDetails = await getCameraById(cameras[0].camera_id);
      console.log('Camera details:', cameraDetails);
    }
  } catch (error) {
    console.error('Error fetching cameras:', error);
  }
};
```

# Store API Requirements for Frontend

## List Stores
To fetch the list of stores, make a GET request to `/api/stores`:

```javascript
const getStores = async () => {
  const response = await fetch('/api/stores', {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  return response.json();
};
```

### Response Format
The API will return an array of stores in this format:
```json
[
  {
    "store_id": 1,
    "store_name": "Store Name",
    "location": "Store Location",
    "status": "active",
    "createdAt": "2024-03-20T12:00:00Z"
  }
]
```

### Example Usage
```javascript
const handleListStores = async () => {
  try {
    const stores = await getStores();
    console.log('Stores:', stores);
    // Use the stores data in your component
  } catch (error) {
    console.error('Error fetching stores:', error);
  }
};
```

### Important Notes
1. Make sure to include the JWT token in the Authorization header
2. The response includes additional fields (status, createdAt) for frontend compatibility
3. Store the selected store_id when needed for camera operations

## Get Single Store
To fetch details of a specific store:

```javascript
const getStoreById = async (storeId) => {
  const response = await fetch(`/api/stores/${storeId}`, {
    headers: {
      'Authorization': `Bearer ${token}`
    }
  });
  return response.json();
};
```

### Response Format
```json
{
  "store_id": 1,
  "store_name": "Store Name",
  "location": "Store Location",
  "status": "active",
  "createdAt": "2024-03-20T12:00:00Z"
}
```

### Example Usage
```javascript
const handleGetStore = async (storeId) => {
  try {
    const store = await getStoreById(storeId);
    console.log('Store details:', store);
    // Use the store data in your component
  } catch (error) {
    console.error('Error fetching store:', error);
  }
};
```

## Create Store
To create a new store:

```javascript
const createStore = async (storeData) => {
  const response = await fetch('/api/stores', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({
      name: storeData.name,
      location: storeData.location
    })
  });
  return response.json();
};
```

### Request Format
```json
{
  "name": "New Store Name",
  "location": "Store Location"
}
```

### Example Usage
```javascript
const handleCreateStore = async () => {
  try {
    const storeData = {
      name: "New Store",
      location: "123 Main St"
    };
    
    const result = await createStore(storeData);
    console.log('Store created:', result);
  } catch (error) {
    console.error('Error creating store:', error);
  }
};
```

### Important Notes
1. The `name` field is required
2. The `location` field is required
3. The API will automatically set:
   - `store_name` (same as name if not provided)
   - `status` (defaults to "active")
   - `createdAt` (current timestamp)
4. Make sure to include the JWT token in the Authorization header 

## Delete Operations

### Delete Store
To delete a store and all its associated cameras:

```javascript
async function deleteStore(storeId) {
  try {
    const response = await fetch(`/api/stores/${storeId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error('Failed to delete store');
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error deleting store:', error);
    throw error;
  }
}
```

### Delete Camera
To delete a specific camera:

```javascript
async function deleteCamera(cameraId) {
  try {
    const response = await fetch(`/api/cameras/${cameraId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error('Failed to delete camera');
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error deleting camera:', error);
    throw error;
  }
}
```

### Implementation Guidelines for Delete Buttons

1. **Store Delete Button**:
   - Add a delete button next to each store in the store list
   - Before deletion, show a confirmation dialog to the user
   - Warn the user that deleting a store will also delete all associated cameras
   - Example implementation:

```javascript
function StoreList() {
  const handleDeleteStore = async (storeId) => {
    if (window.confirm('Are you sure you want to delete this store? This will also delete all associated cameras.')) {
      try {
        await deleteStore(storeId);
        // Refresh the store list
        fetchStores();
      } catch (error) {
        // Show error message to user
        alert('Failed to delete store');
      }
    }
  };

  return (
    <div>
      {stores.map(store => (
        <div key={store.store_id}>
          <h3>{store.store_name}</h3>
          <button onClick={() => handleDeleteStore(store.store_id)}>
            Delete Store
          </button>
        </div>
      ))}
    </div>
  );
}
```

2. **Camera Delete Button**:
   - Add a delete button next to each camera in the camera list
   - Show a confirmation dialog before deletion
   - Example implementation:

```javascript
function CameraList() {
  const handleDeleteCamera = async (cameraId) => {
    if (window.confirm('Are you sure you want to delete this camera?')) {
      try {
        await deleteCamera(cameraId);
        // Refresh the camera list
        fetchCameras();
      } catch (error) {
        // Show error message to user
        alert('Failed to delete camera');
      }
    }
  };

  return (
    <div>
      {cameras.map(camera => (
        <div key={camera.camera_id}>
          <h3>{camera.camera_name}</h3>
          <button onClick={() => handleDeleteCamera(camera.camera_id)}>
            Delete Camera
          </button>
        </div>
      ))}
    </div>
  );
}
```

### Important Notes:
1. Always include the JWT token in the Authorization header for all delete requests
2. Implement proper error handling and user feedback
3. Refresh the relevant lists after successful deletion
4. Consider adding loading states during deletion operations
5. For stores, make sure to clearly communicate that associated cameras will also be deleted
6. Consider implementing a more sophisticated confirmation dialog (e.g., using a modal) instead of the basic `window.confirm()` 

## Camera Calibration

### Setting Calibration Data
To set the region of interest (ROI) and line for entry/exit detection:

```javascript
async function setCalibration(cameraId, calibrationData) {
  try {
    const response = await fetch(`/api/cameras/${cameraId}/calibrate`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        roi: {
          x1: 100,
          y1: 100,
          x2: 500,
          y2: 400
        },
        line: {
          startX: 200,
          startY: 300,
          endX: 400,
          endY: 300
        }
      })
    });

    if (!response.ok) {
      throw new Error('Failed to set calibration data');
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error setting calibration:', error);
    throw error;
  }
}
```

### Getting Calibration Data
To retrieve existing calibration data for a camera:

```javascript
async function getCalibration(cameraId) {
  try {
    const response = await fetch(`/api/cameras/${cameraId}/calibrate`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error('Failed to get calibration data');
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error getting calibration:', error);
    throw error;
  }
}
```

### Drawing Calibration on Camera Snapshot
To implement the calibration UI:

1. First, get a snapshot image from `/api/cameras/{camera_id}/snapshot`
2. Display the image in a canvas element
3. If calibration data exists, draw the ROI and line on the canvas
4. Allow the user to draw or modify the ROI and line
5. Save the updated calibration data using the `setCalibration` function

Example implementation:

```javascript
// Drawing ROI and line on canvas
function drawCalibration(canvas, calibration) {
  const ctx = canvas.getContext('2d');
  
  // Draw ROI (Region of Interest)
  if (calibration.roi) {
    const roi = calibration.roi;
    ctx.strokeStyle = 'blue';
    ctx.lineWidth = 2;
    ctx.strokeRect(
      roi.x1, 
      roi.y1, 
      roi.x2 - roi.x1, 
      roi.y2 - roi.y1
    );
  }
  
  // Draw line for entry/exit detection
  if (calibration.line) {
    const line = calibration.line;
    ctx.strokeStyle = 'red';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(line.startX, line.startY);
    ctx.lineTo(line.endX, line.endY);
    ctx.stroke();
  }
}
```

### Notes for Implementation
1. Always include the JWT token in the Authorization header
2. The ROI (x1, y1, x2, y2) represents the top-left and bottom-right corners of the rectangle
3. The line (startX, startY, endX, endY) represents the start and end points of the entry/exit line
4. When no calibration exists yet, the GET endpoint returns null values for roi and line
5. The calibration data is essential for proper processing of entry/exit counts 

## Camera Calibration Orientation

### Line Orientation for Entry/Exit Detection

We've added an "orientation" field to the calibration data to specify which direction is considered an entry vs exit. The calibration endpoint now accepts:

```json
{
  "roi": { "x1": 100, "y1": 100, "x2": 500, "y2": 400 },
  "line": {
    "startX": 200,
    "startY": 300,
    "endX": 400,
    "endY": 300
  },
  "orientation": "leftToRight"  // or "rightToLeft"
}
```

If not provided, the orientation defaults to "leftToRight".

### How the Detection Interprets Orientation

- **leftToRight**: Objects crossing from right to left are counted as "entries"
- **rightToLeft**: Objects crossing from left to right are counted as "entries"
- The reverse direction in each case is counted as an "exit"

### Frontend Implementation

Please add a control in the calibration UI that allows users to specify the orientation. This could be:

1. A toggle switch:
   - "Entry direction: Left to Right" / "Entry direction: Right to Left"

2. A dropdown:
   ```html
   <select>
     <option value="leftToRight">Entry: Right to Left</option>
     <option value="rightToLeft">Entry: Left to Right</option>
   </select>
   ```

3. An arrow visualization:
   - Draw an arrow next to the line indicating the entry direction
   - Allow the user to flip the arrow to change direction

When you POST calibration data to `/api/cameras/{camera_id}/calibrate`, include the orientation field with the selected value.

### Example JavaScript

```javascript
async function setCalibrationWithOrientation(cameraId, calibrationData) {
  try {
    const response = await fetch(`/api/cameras/${cameraId}/calibrate`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        roi: calibrationData.roi,
        line: calibrationData.line,
        orientation: calibrationData.orientation || "leftToRight"
      })
    });

    if (!response.ok) {
      throw new Error('Failed to set calibration data');
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error setting calibration:', error);
    throw error;
  }
}
```

## Frame Rate in Calibration

We've added a new "frame_rate" field to the calibration data. This controls how many frames per second are processed by the detection system, allowing users to balance detection accuracy with performance.

### API Changes

- `GET /api/cameras/{camera_id}/calibrate` now returns:
  ```json
  {
    "camera_id": 1,
    "roi": { "x1": 100, "y1": 100, "x2": 500, "y2": 400 },
    "line": {
      "startX": 200,
      "startY": 300,
      "endX": 400,
      "endY": 300
    },
    "orientation": "leftToRight",
    "frame_rate": 5
  }
  ```

- `POST /api/cameras/{camera_id}/calibrate` can include "frame_rate" in request body:
  ```json
  {
    "roi": { "x1": 100, "y1": 100, "x2": 500, "y2": 400 },
    "line": {
      "startX": 200,
      "startY": 300,
      "endX": 400,
      "endY": 300
    },
    "orientation": "leftToRight",
    "frame_rate": 5
  }
  ```

### Frontend Implementation

Please add a frame rate input to the calibration UI. This could be:

1. A slider:
   ```html
   <div class="form-group">
     <label for="frame-rate-slider">
       Detection Frame Rate: <span id="frame-rate-value">5</span> FPS
     </label>
     <input 
       type="range" 
       id="frame-rate-slider" 
       min="1" 
       max="30" 
       value="5" 
       class="form-control-range"
       oninput="updateFrameRateValue(this.value)"
     >
     <small class="form-text text-muted">
       Lower values (1-5 FPS) reduce CPU usage but may miss quick movements.<br>
       Higher values (15-30 FPS) provide more responsive detection but increase CPU usage.
     </small>
   </div>
   ```

2. A numeric input:
   ```html
   <div class="form-group">
     <label for="frame-rate">Detection Frame Rate (FPS)</label>
     <input type="number" id="frame-rate" min="1" max="30" value="5" class="form-control">
   </div>
   ```

3. Preset options:
   ```html
   <div class="form-group">
     <label for="frame-rate">Detection Frame Rate</label>
     <select id="frame-rate" class="form-control">
       <option value="1">1 FPS (Lowest CPU usage)</option>
       <option value="3">3 FPS (Low CPU usage)</option>
       <option value="5" selected>5 FPS (Recommended)</option>
       <option value="10">10 FPS (Higher accuracy)</option>
       <option value="30">30 FPS (Maximum accuracy)</option>
     </select>
   </div>
   ```

### Example JavaScript

```javascript
async function setCalibrationWithFrameRate(cameraId, calibrationData) {
  try {
    const response = await fetch(`/api/cameras/${cameraId}/calibrate`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        roi: calibrationData.roi,
        line: calibrationData.line,
        orientation: calibrationData.orientation || "leftToRight",
        frame_rate: calibrationData.frame_rate || 5
      })
    });

    if (!response.ok) {
      throw new Error('Failed to set calibration data');
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error setting calibration:', error);
    throw error;
  }
}
```

### Important Notes

- The `frame_rate` is specified in frames per second (FPS)
- Valid values are integers greater than 0
- If not specified, a default of 5 FPS will be used
- If a value higher than the camera's actual FPS is specified, all frames will be processed
- Lower values (1-3 FPS) significantly reduce CPU usage but may miss quick movements
- Higher values (10-30 FPS) improve detection accuracy but increase CPU usage
- Recommended range: 3-10 FPS depending on scenario 

## Entry/Exit Detection API Requirements for Frontend

### 1. On-Demand Detection

#### Trigger Detection (POST /api/detect)

You can trigger detection on-demand for a specific camera, which will analyze the current frame for entries and exits.

**Authentication Required**: Yes (JWT token in Authorization header)

**Option 1 - Query Parameter**:
```javascript
// Example using fetch:
async function triggerDetection(cameraId) {
  const response = await fetch(`${API_BASE}/api/detect?camera_id=${cameraId}`, {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer ' + jwtToken
    }
  });
  
  if (!response.ok) {
    throw new Error(`Failed to trigger detection: ${response.status}`);
  }
  
  return await response.json();
}
```

**Option 2 - JSON Body**:
```javascript
// Example using fetch:
async function triggerDetection(cameraId) {
  const response = await fetch(`${API_BASE}/api/detect`, {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer ' + jwtToken,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ camera_id: cameraId.toString() })
  });
  
  if (!response.ok) {
    throw new Error(`Failed to trigger detection: ${response.status}`);
  }
  
  return await response.json();
}
```

**Response**:
```json
{
  "status": "entry_detected",  // or "exit_detected" or "no_motion"
  "bounding_boxes": [[x1, y1, x2, y2], ...],  // detected objects coordinates
  "crossing_detected": true,  // boolean indicating if a crossing was detected
  "event_id": 123,  // present only if crossing_detected is true
  "timestamp": "2024-03-21 14:30:45"  // timestamp when the event was detected
}
```

### 2. Continuous Detection Configuration

You can configure continuous detection for a camera, though this is a placeholder for a more robust implementation.

#### Configure Detection (POST /api/detection/config)

**Authentication Required**: Yes (JWT token in Authorization header)

```javascript
// Example using fetch:
async function configureDetection(cameraId, intervalSeconds = 10, enabled = true) {
  const response = await fetch(`${API_BASE}/api/detection/config`, {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer ' + jwtToken,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      camera_id: cameraId,
      interval_seconds: intervalSeconds,
      enabled: enabled
    })
  });
  
  if (!response.ok) {
    throw new Error(`Failed to configure detection: ${response.status}`);
  }
  
  return await response.json();
}
```

**Response**:
```json
{
  "status": "configured",
  "message": "Detection configured for camera 1 at 10s intervals",
  "config": {
    "camera_id": 1,
    "interval_seconds": 10,
    "enabled": true
  }
}
```

### 3. Retrieving Detection Logs

#### Get All Logs (GET /api/logs)

Retrieve entry/exit events for a specific store with optional filtering.

**Authentication Required**: Yes (JWT token in Authorization header)

```javascript
// Example using fetch:
async function getLogs(storeId, options = {}) {
  // Build query parameters
  const params = new URLSearchParams({ store_id: storeId });
  
  // Add optional filters
  if (options.cameraId) params.append('camera_id', options.cameraId);
  if (options.startDate) params.append('start_date', options.startDate);
  if (options.endDate) params.append('end_date', options.endDate);
  if (options.eventType) params.append('event_type', options.eventType);
  if (options.limit) params.append('limit', options.limit);
  
  const response = await fetch(`${API_BASE}/api/logs?${params.toString()}`, {
    headers: {
      'Authorization': 'Bearer ' + jwtToken
    }
  });
  
  if (!response.ok) {
    throw new Error(`Failed to retrieve logs: ${response.status}`);
  }
  
  return await response.json();
}
```

**Response**:
```json
{
  "store_id": 1,
  "camera_id": 2,  // Only included if filtered by camera_id
  "total_events": 25,
  "events": [
    {
      "event_id": 123,
      "store_id": 1,
      "camera_id": 2,
      "camera_name": "Front Door",
      "event_type": "entry",
      "timestamp": "2024-03-21 14:30:45",
      "timestamp_iso": "2024-03-21T14:30:45",
      "clip_path": "/recordings/camera_2_entry_2024-03-21_14_30_45.mp4"
    },
    // More events...
  ]
}
```

#### Get Camera-Specific Logs (GET /api/cameras/{camera_id}/logs)

A convenience endpoint to retrieve logs for a specific camera.

**Authentication Required**: Yes (JWT token in Authorization header)

```javascript
// Example using fetch:
async function getCameraLogs(cameraId, options = {}) {
  // Build query parameters
  const params = new URLSearchParams();
  
  // Add optional filters
  if (options.storeId) params.append('store_id', options.storeId);
  if (options.startDate) params.append('start_date', options.startDate);
  if (options.endDate) params.append('end_date', options.endDate);
  if (options.eventType) params.append('event_type', options.eventType);
  if (options.limit) params.append('limit', options.limit);
  
  const queryString = params.toString() ? `?${params.toString()}` : '';
  
  const response = await fetch(`${API_BASE}/api/cameras/${cameraId}/logs${queryString}`, {
    headers: {
      'Authorization': 'Bearer ' + jwtToken
    }
  });
  
  if (!response.ok) {
    throw new Error(`Failed to retrieve camera logs: ${response.status}`);
  }
  
  return await response.json();
}
```

**Response**: Same format as the general logs endpoint.

### Important Notes

1. All detection and logs endpoints require authentication via JWT token.
2. On-demand detection is synchronous and may take a moment to complete, depending on the camera feed.
3. Detection results include bounding boxes with coordinates relative to the camera frame.
4. The timestamp in logs is stored in "YYYY-MM-DD HH:MM:SS" format, but an ISO-formatted version is also provided for convenience.
5. For filtering logs by date, use the "YYYY-MM-DD" format (e.g., "2024-03-21"). 

## WebSocket-Based Live Detection

Instead of polling the `/api/detect` endpoint for real-time detection results, we've added a WebSocket-based solution that provides continuous video streaming with real-time detection results.

### Connection

Connect to one of the WebSocket endpoints:

1. **Single Camera**:
   ```javascript
   const cameraId = 1; // Example camera ID
   const token = localStorage.getItem('token');
   const socket = new WebSocket(`ws://${API_HOST}/api/ws/live-detections/${cameraId}?token=${token}`);
   ```

2. **Multiple Cameras**:
   ```javascript
   const cameraIds = "1,2,3"; // Comma-separated camera IDs
   const token = localStorage.getItem('token');
   const socket = new WebSocket(`ws://${API_HOST}/api/ws/detections?camera_ids=${cameraIds}&token=${token}`);
   ```

### Authentication

- The JWT token must be passed as a query parameter named `token`
- If the token is invalid or missing, the connection will be closed
- The same token you use for REST API authentication works here

### WebSocket Events

```javascript
// Initialize connection
socket.onopen = (event) => {
  console.log('WebSocket connection established');
};

// Handle incoming messages
socket.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  // Check if it's the initial connection message
  if (data.status === 'connected') {
    console.log(data.message);
    return;
  }
  
  // Process video frame and detection results
  if (data.frame) {
    // Update video display with the new frame
    updateVideoFrame(data.camera_id, data.frame);
    
    // Draw bounding boxes if there are any detections
    if (data.detections && data.detections.length > 0) {
      console.log(`Received ${data.detections.length} detections`);
      drawBoundingBoxes(data.camera_id, data.detections);
    }
    
    // If there was an entry/exit event
    if (data.crossing_detected && data.event) {
      console.log(`${data.event} detected at ${data.timestamp}`);
      updateCounter(data.event);
    }
  }
};

// Handle errors
socket.onerror = (error) => {
  console.error('WebSocket error:', error);
};

// Handle connection close
socket.onclose = (event) => {
  console.log(`WebSocket connection closed: ${event.code}`);
  
  // Reconnect logic
  if (event.code !== 1000) { // Not a normal closure
    console.log('Attempting to reconnect...');
    setTimeout(() => {
      // Reconnect logic here
    }, 3000);
  }
};
```

### Message Format

Each update message has this format:

```json
{
  "camera_id": 1,
  "timestamp": "2024-03-22T14:30:45",
  "frame": "base64-encoded-jpeg-image-data",
  "detections": [
    {
      "label": "person",
      "confidence": 0.9,
      "bbox": [100, 150, 200, 300]
    }
  ],
  "event": "entry",
  "status": "entry_detected",
  "crossing_detected": true
}
```

- `camera_id`: The ID of the camera being processed
- `timestamp`: ISO-formatted timestamp
- `frame`: Base64-encoded JPEG image of the current video frame
- `detections`: Array of detection objects with:
  - `label`: Object class label (currently "person")
  - `confidence`: Detection confidence score (0-1)
  - `bbox`: Bounding box coordinates [x1, y1, x2, y2]
- `event`: Type of crossing event detected ("entry", "exit", or null)
- `status`: Detection status string
- `crossing_detected`: Boolean indicating if a line crossing occurred

### Example Implementation

Here's a complete example showing how to display the video stream with bounding boxes:

```javascript
function setupLiveVideoDetection(cameraId) {
  const token = localStorage.getItem('token');
  const socket = new WebSocket(`ws://${API_HOST}/api/ws/live-detections/${cameraId}?token=${token}`);
  
  // Elements for display
  const videoImg = document.getElementById('video-display');
  const canvas = document.getElementById('detection-overlay');
  const ctx = canvas.getContext('2d');
  
  // Set up the overlay canvas on top of the video display
  function setupCanvas() {
    // Position the canvas on top of the image with the same dimensions
    const rect = videoImg.getBoundingClientRect();
    canvas.width = videoImg.width;
    canvas.height = videoImg.height;
    canvas.style.position = 'absolute';
    canvas.style.left = rect.left + 'px';
    canvas.style.top = rect.top + 'px';
  }
  
  // Update video frame from base64 data
  function updateVideoFrame(base64Data) {
    // Convert base64 to image src
    videoImg.src = `data:image/jpeg;base64,${base64Data}`;
    
    // When the image loads, make sure the canvas is sized correctly
    videoImg.onload = () => {
      setupCanvas();
    };
  }
  
  // Draw bounding boxes and labels on the canvas
  function drawBoundingBoxes(detections) {
    // Clear previous drawings
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw each detection
    detections.forEach(detection => {
      const [x1, y1, x2, y2] = detection.bbox;
      const width = x2 - x1;
      const height = y2 - y1;
      
      // Draw bounding box
      ctx.strokeStyle = '#00FF00'; // Green for person detection
      ctx.lineWidth = 2;
      ctx.strokeRect(x1, y1, width, height);
      
      // Draw label with confidence
      const label = `${detection.label} ${Math.round(detection.confidence * 100)}%`;
      ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
      ctx.fillRect(x1, y1 - 20, ctx.measureText(label).width + 10, 20);
      ctx.fillStyle = '#FFFFFF';
      ctx.font = '14px Arial';
      ctx.fillText(label, x1 + 5, y1 - 5);
    });
  }
  
  // Display event notifications
  function showEvent(event, timestamp) {
    const eventDiv = document.getElementById('event-display');
    const eventType = event === 'entry' ? 'Entry' : 'Exit';
    const color = event === 'entry' ? '#0000FF' : '#FF0000';
    
    eventDiv.innerHTML = `<span style="color: ${color}; font-weight: bold;">${eventType} detected at ${timestamp}</span>`;
    
    // Clear after 3 seconds
    setTimeout(() => {
      eventDiv.innerHTML = '';
    }, 3000);
  }
  
  // WebSocket message handler
  socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    // Skip connection messages
    if (data.status === 'connected') return;
    
    // If we received a frame, update the video display
    if (data.frame) {
      updateVideoFrame(data.frame);
      
      // If there are detections, draw bounding boxes
      if (data.detections && data.detections.length > 0) {
        drawBoundingBoxes(data.detections);
      }
      
      // If there was a crossing event, show notification
      if (data.crossing_detected && data.event) {
        showEvent(data.event, data.timestamp);
        
        // Also update counters if needed
        const counterSpan = document.getElementById(`${data.event}-counter`);
        if (counterSpan) {
          counterSpan.textContent = parseInt(counterSpan.textContent || '0') + 1;
        }
      }
    }
  };
  
  // Error and close handlers
  socket.onerror = (error) => {
    console.error('WebSocket error:', error);
  };
  
  socket.onclose = () => {
    console.log('WebSocket connection closed');
  };
  
  // Clean up function
  return () => {
    if (socket.readyState === WebSocket.OPEN) {
      socket.close();
    }
  };
}
```

### Performance Considerations

1. **Server-side adaptive processing**: 
   - The server now performs detection at the specified frame rate while streaming video at higher rates
   - This decoupling allows for smooth video with optimized detection

2. **Resource utilization tradeoffs**:
   - 1-3 FPS: Minimal CPU usage, suitable for most scenarios, may miss very quick movements
   - 5-10 FPS: Balanced performance, recommended for general use
   - 15-30 FPS: High CPU usage, recommended only for scenarios requiring maximum responsiveness

3. **Client-side frame limiting**:
   - The client can still implement additional frame skipping if needed for low-end devices
   - The browser test page includes frame rate limiting code you can reference

### Testing the WebSocket

To verify the WebSocket is functioning correctly with your frame rate settings:

1. Set a frame rate in the calibration UI (e.g., 5 FPS)
2. Connect to the WebSocket and observe detection events
3. Change the frame rate setting and reconnect to see the difference in detection frequency

The server logs will output the actual frame rate being used:
```
Camera 1: Using configured frame rate from calibration: 5 FPS (interval: 0.200s)
```

This output confirms the server is honoring your frame rate setting from calibration.

### Troubleshooting

If detections seem delayed or infrequent:
- Check the frame_rate value in the camera's calibration
- Verify the WebSocket is successfully connecting
- Examine server logs for any errors
- Try increasing the frame_rate value for more frequent detection

If the server CPU usage is too high:
- Reduce the frame_rate value in calibration
- Limit the number of simultaneous WebSocket connections
- Consider using the multiple-camera WebSocket for consolidated connections

## WebSocket Performance Considerations

### Hardware Limitations

Our testing shows that the Raspberry Pi hardware has performance limitations that affect the WebSocket video streaming:

1. **Actual Frame Rate vs. Requested Frame Rate**: 
   - While you can request a frame rate up to 30 FPS in the WebSocket URL (`&frame_rate=30`), the actual achievable frame rate on Raspberry Pi is typically around 5 FPS
   - The backend now includes the actual frame rate in each WebSocket response to help you adapt your frontend accordingly

2. **New Response Fields**:
   The WebSocket response now includes additional performance-related fields:
   ```json
   {
     "camera_id": 1,
     "timestamp": "2025-03-22T15:30:45",
     "frame": "base64_encoded_image_data",
     "detections": [...],
     "status": "no_motion",
     "crossing_detected": false,
     "actual_fps": 4.8,              // The actual FPS being achieved
     "target_fps": 30.0,             // The requested frame rate
     "hardware_limited": true        // Indicates if hardware is limiting performance
   }
   ```

3. **Adaptive Quality**:
   - The backend now automatically adjusts image quality based on the requested frame rate
   - Higher frame rates use lower image quality to improve performance
   - Lower frame rates use higher image quality for better image detail

### Implementation Recommendations

1. **Monitor Actual Frame Rate**:
   ```javascript
   socket.onmessage = (event) => {
     const data = JSON.parse(event.data);
     
     // Check if hardware is limiting performance
     if (data.hardware_limited) {
       console.warn(`Camera ${data.camera_id} is hardware limited. 
                     Target: ${data.target_fps} FPS, Actual: ${data.actual_fps} FPS`);
       
       // Optionally adjust UI to show the limitation
       updatePerformanceIndicator(data.actual_fps, data.target_fps);
     }
     
     // Display the video frame
     updateVideoFrame(data.frame, data.detections);
   };
   ```

2. **Optimal Frame Rate Settings**:
   - For Raspberry Pi, request 5-8 FPS for best quality/performance balance
   - If you need smoother motion, you can request higher frame rates (10-30 FPS) but expect lower image quality
   - For multiple cameras, use lower frame rates (1-3 FPS per camera) to avoid overloading the system

3. **Dynamic Frame Rate Adjustment**:
   ```javascript
   function adjustFrameRate(initialRate = 30) {
     let currentRate = initialRate;
     let connectionAttempts = 0;
     
     function connectWebSocket() {
       const socket = new WebSocket(
         `ws://${API_HOST}/api/ws/live-detections/${cameraId}?token=${token}&frame_rate=${currentRate}`
       );
       
       socket.onmessage = (event) => {
         const data = JSON.parse(event.data);
         
         // If hardware limited and frame rate is too high, reduce it on reconnection
         if (data.hardware_limited && connectionAttempts < 3) {
           console.log(`Hardware limited at ${currentRate} FPS, reducing to ${Math.max(5, currentRate/2)} FPS`);
           currentRate = Math.max(5, Math.floor(currentRate/2));
           socket.close();
           connectionAttempts++;
           setTimeout(connectWebSocket, 1000);
         }
       };
       
       return socket;
     }
     
     return connectWebSocket();
   }
   ```

By leveraging these new features, your frontend can adapt to the hardware capabilities of the Raspberry Pi while providing the best possible user experience.

## WebRTC + WebSocket Hybrid Implementation

A new hybrid approach is now available that combines the benefits of WebRTC for video streaming and WebSockets for detection data. This approach can significantly improve performance, especially for higher frame rates.

### How It Works

1. **WebRTC for Video Streaming**:
   - Uses browser's native WebRTC capabilities for efficient video streaming
   - Handles the video transport only, with lower latency than WebSockets
   - Better browser support for video playback optimization

2. **WebSockets for Detection Data**:
   - A separate lightweight WebSocket connection sends only detection data
   - Includes bounding boxes, event information, and detection status
   - Much lower bandwidth requirements than sending frames

### API Endpoints

#### WebRTC Signaling

1. **WebRTC Signaling WebSocket**:
   ```
   ws://${API_HOST}/api/ws/rtc-signaling/{camera_id}?token=${token}
   ```
   This WebSocket handles the WebRTC connection setup (SDP exchange and ICE candidates).

2. **HTTP REST Endpoints** (alternative to WebSocket signaling):
   ```
   POST /api/rtc/offer/{camera_id}?token=${token}
   GET /api/rtc/answer/{connection_id}?token=${token}
   POST /api/rtc/ice-candidate/{connection_id}?token=${token}
   GET /api/rtc/ice-candidates/{connection_id}?token=${token}
   ```

#### Detection Data WebSocket

```
ws://${API_HOST}/api/ws/detection-data/{camera_id}?token=${token}&frame_rate=${frame_rate}
```

This WebSocket provides only detection data, with the same frame_rate control as the original WebSocket implementation.

### Implementation Example

Check out the sample implementation at:
```
/api/temp/webrtc_hybrid_test.html
```

This demonstration page shows how to:
1. Set up the WebRTC connection using the signaling WebSocket
2. Establish a separate detection data WebSocket
3. Draw bounding boxes on top of the WebRTC video stream
4. Handle reconnection and error scenarios

### Benefits

1. **Performance**:
   - Higher achievable frame rates with lower CPU/network usage
   - More efficient video codec handling (H.264) by the browser
   - Reduced server load by separating video and detection processing

2. **Scalability**:
   - Better support for multiple camera views
   - More efficient bandwidth utilization
   - Lower latency for live video

3. **User Experience**:
   - Smoother video playback
   - More responsive detection overlays
   - Better mobile device performance

### Implementation Considerations

When implementing this hybrid approach:

1. **Error Handling**:
   - Implement robust reconnection logic for both WebRTC and WebSocket
   - Handle cases where one connection is working but the other isn't
   - Provide clear status indicators to users

2. **Synchronization**:
   - Ensure detection data and video frames are properly synchronized
   - Account for possible latency differences between connections

3. **Fallback**:
   - Consider implementing a fallback to the original WebSocket-only approach
   - Detect WebRTC support and capabilities before attempting to use it

## WebRTC Connection Setup Guide

### Ensuring Proper WebRTC Media Line Order

We've implemented a fix on the backend to ensure proper handling of WebRTC SDP negotiation, particularly focusing on the order of media lines in the SDP offer and answer. This is crucial for establishing a successful WebRTC connection, especially when adaptive bandwidth features are enabled.

### Frontend Implementation Guidelines

1. **SDP Handling**: When implementing WebRTC on the frontend, ensure you don't modify the SDP in any way before setting it as the remote description.

2. **Connection Setup Example**:

```javascript
// Example WebRTC connection setup
async function setupWebRTCConnection(cameraId) {
  const token = localStorage.getItem('token');
  const connectionId = await getConnectionId(cameraId, token);
  
  // Create peer connection with STUN servers
  const peerConnection = new RTCPeerConnection({
    iceServers: [
      { urls: 'stun:stun.l.google.com:19302' },
      { urls: 'stun:stun1.l.google.com:19302' }
    ]
  });
  
  // Set up event handlers
  peerConnection.ontrack = (event) => {
    if (event.track.kind === 'video') {
      const videoElement = document.getElementById('video-element');
      if (videoElement) {
        videoElement.srcObject = event.streams[0];
      }
    }
  };
  
  peerConnection.onicecandidate = async (event) => {
    if (event.candidate) {
      await sendIceCandidate(connectionId, event.candidate, token);
    }
  };
  
  peerConnection.onconnectionstatechange = () => {
    console.log(`Connection state: ${peerConnection.connectionState}`);
  };
  
  peerConnection.oniceconnectionstatechange = () => {
    console.log(`ICE connection state: ${peerConnection.iceConnectionState}`);
  };
  
  // Create and send offer
  const offer = await peerConnection.createOffer({
    offerToReceiveVideo: true,
    offerToReceiveAudio: false
  });
  
  await peerConnection.setLocalDescription(offer);
  
  // Send offer to server and get answer
  const answer = await sendOffer(connectionId, offer.sdp, token);
  
  // IMPORTANT: Set the remote description with the answer exactly as received
  // Do not modify the SDP answer in any way
  await peerConnection.setRemoteDescription({
    type: 'answer',
    sdp: answer
  });
  
  return peerConnection;
}

// Helper functions
async function getConnectionId(cameraId, token) {
  const response = await fetch(`/api/rtc/connection/${cameraId}`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  const data = await response.json();
  return data.connection_id;
}

async function sendOffer(connectionId, offerSdp, token) {
  const response = await fetch(`/api/rtc/offer/${connectionId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify({ sdp: offerSdp })
  });
  const data = await response.json();
  return data.sdp;
}

async function sendIceCandidate(connectionId, candidate, token) {
  await fetch(`/api/rtc/ice-candidate/${connectionId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify(candidate)
  });
}
```

### Troubleshooting WebRTC Connections

If you encounter connection issues:

1. **Check SDP Handling**: Ensure you're not modifying the SDP in any way before setting it as the remote description.

2. **Verify ICE Candidates**: Make sure ICE candidates are being properly exchanged between the client and server.

3. **Connection State Logging**: Implement detailed logging of connection state changes to help diagnose issues:

```javascript
peerConnection.addEventListener('connectionstatechange', event => {
  console.log(`Connection state changed: ${peerConnection.connectionState}`);
  // Log the full event details for debugging
  console.log('Connection state change event:', event);
});

peerConnection.addEventListener('signalingstatechange', () => {
  console.log(`Signaling state: ${peerConnection.signalingState}`);
});
```

4. **SDP Debugging**: If problems persist, log the SDP offer and answer to compare and identify any discrepancies:

```javascript
console.log('Offer SDP:', offer.sdp);
console.log('Answer SDP:', answerSdp);
```

5. **Network Conditions**: Be aware that WebRTC performance can be affected by network conditions. Implement appropriate error handling and reconnection logic.

### Adaptive Bandwidth Considerations

Our backend now correctly handles adaptive bandwidth features while maintaining proper media line order. When implementing adaptive bandwidth features on the frontend:

1. **Use Standard APIs**: Stick to standard WebRTC APIs for bandwidth adaptation.

2. **Avoid SDP Manipulation**: Don't manually modify SDP parameters related to bandwidth; instead, use the RTCPeerConnection API methods.

3. **Bandwidth Estimation**: If implementing custom bandwidth estimation, ensure it doesn't interfere with the SDP negotiation process.
```

{{ ... }}
```

### ZVision API Endpoints Reference

This section provides a comprehensive list of all available API endpoints in the ZVision backend system. Use this as a reference when implementing frontend functionality.

### Authentication Endpoints

| Endpoint | Method | Description | Request Body | Response |
|----------|--------|-------------|-------------|----------|
| `/api/auth/login` | POST | Authenticate user and get JWT token | `{"username": "string", "password": "string"}` | `{"access_token": "string", "token_type": "bearer"}` |
| `/api/token` | GET | Get a new JWT token (alternative endpoint) | None | JWT token string |

### Store Management

| Endpoint | Method | Description | Request Body | Response |
|----------|--------|-------------|-------------|----------|
| `/api/stores` | GET | Get all stores | None | Array of store objects |
| `/api/stores/{store_id}` | GET | Get store by ID | None | Store object |
| `/api/stores` | POST | Create new store | `{"name": "string", "location": "string"}` | Created store object |
| `/api/stores/{store_id}` | PUT | Update store | `{"name": "string", "location": "string"}` | Updated store object |
| `/api/stores/{store_id}` | DELETE | Delete store | None | `{"success": true}` |

### Camera Management

| Endpoint | Method | Description | Request Body | Response |
|----------|--------|-------------|-------------|----------|
| `/api/cameras` | GET | Get all cameras | None | Array of camera objects |
| `/api/cameras/{camera_id}` | GET | Get camera by ID | None | Camera object |
| `/api/cameras` | POST | Create new camera | Camera object | Created camera object |
| `/api/cameras/{camera_id}` | PUT | Update camera | Camera object | Updated camera object |
| `/api/cameras/{camera_id}` | DELETE | Delete camera | None | `{"success": true}` |
| `/api/cameras/{camera_id}/calibrate` | POST | Set camera calibration | Calibration object | `{"success": true}` |
| `/api/cameras/{camera_id}/feed` | GET | Get camera feed image | None | JPEG image |

### Detection Endpoints

| Endpoint | Method | Description | Request Body | Response |
|----------|--------|-------------|-------------|----------|
| `/api/detect` | POST | Trigger on-demand detection | `{"camera_id": int}` | Detection results |
| `/api/detection/config` | POST | Configure automatic detection | `{"camera_id": int, "interval_seconds": float, "enabled": bool}` | Configuration status |

### Logs and Analytics

| Endpoint | Method | Description | Request Body | Response |
|----------|--------|-------------|-------------|----------|
| `/api/logs` | GET | Get detection logs | Query params: `store_id`, `camera_id`, `start_date`, `end_date`, `event_type`, `limit` | Array of log entries |

### WebSocket Endpoints

| Endpoint | Description | Query Parameters | Message Format |
|----------|-------------|------------------|----------------|
| `/api/ws/rtc-signaling/{camera_id}` | WebRTC signaling | `token` | JSON messages for WebRTC setup |
| `/api/ws/detection-data/{camera_id}` | Detection data stream | `token`, `frame_rate` | JSON detection data |
| `/api/ws/live-detections/{camera_id}` | Live video with detections | `token` | JSON with base64 frames and detections |

### WebRTC Endpoints

| Endpoint | Method | Description | Request Body | Response |
|----------|--------|-------------|-------------|----------|
| `/api/rtc/connection/{camera_id}` | GET | Get a new WebRTC connection ID | None | `{"connection_id": "string"}` |
| `/api/rtc/offer/{connection_id}` | POST | Send WebRTC offer | `{"sdp": "string"}` | `{"sdp": "string"}` |
| `/api/rtc/ice-candidate/{connection_id}` | POST | Send ICE candidate | ICE candidate object | `{"success": true}` |

## Detailed WebRTC Implementation Guide

### Complete WebRTC Connection Flow

Below is a detailed pseudocode implementation for establishing a WebRTC connection with the ZVision backend:

```javascript
/**
 * Complete WebRTC implementation for ZVision
 * This handles the entire connection flow including:
 * - Connection setup
 * - SDP offer/answer exchange
 * - ICE candidate handling
 * - Video track processing
 * - Connection state management
 * - Error handling and reconnection
 */
class ZVisionWebRTC {
  constructor(cameraId, videoElement) {
    // Configuration
    this.cameraId = cameraId;
    this.videoElement = videoElement;
    this.token = localStorage.getItem('token');
    this.apiBase = '/api'; // Adjust based on your API base URL
    
    // State
    this.connectionId = null;
    this.peerConnection = null;
    this.connectionState = 'disconnected';
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    
    // Bind methods
    this.connect = this.connect.bind(this);
    this.disconnect = this.disconnect.bind(this);
    this.handleConnectionStateChange = this.handleConnectionStateChange.bind(this);
    this.handleICECandidate = this.handleICECandidate.bind(this);
    this.handleTrack = this.handleTrack.bind(this);
    this.sendOffer = this.sendOffer.bind(this);
    this.sendIceCandidate = this.sendIceCandidate.bind(this);
  }
  
  /**
   * Initialize and start WebRTC connection
   */
  async connect() {
    try {
      this.connectionState = 'connecting';
      
      // Step 1: Get a connection ID from the server
      const connectionId = await this.getConnectionId();
      this.connectionId = connectionId;
      console.log(`Received connection ID: ${connectionId}`);
      
      // Step 2: Create RTCPeerConnection with STUN servers
      this.createPeerConnection();
      
      // Step 3: Create and send offer to server
      await this.createAndSendOffer();
      
      return true;
    } catch (error) {
      console.error('Failed to establish WebRTC connection:', error);
      this.connectionState = 'failed';
      
      // Attempt reconnection if appropriate
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        console.log(`Reconnection attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
        
        // Exponential backoff
        const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
        setTimeout(() => this.connect(), delay);
      }
      
      return false;
    }
  }
  
  /**
   * Create RTCPeerConnection with appropriate configuration
   */
  createPeerConnection() {
    // Configuration with STUN servers for NAT traversal
    const config = {
      iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' }
      ]
    };
    
    // Create new connection
    this.peerConnection = new RTCPeerConnection(config);
    
    // Set up event handlers
    this.peerConnection.ontrack = this.handleTrack;
    this.peerConnection.onicecandidate = this.handleICECandidate;
    this.peerConnection.onconnectionstatechange = this.handleConnectionStateChange;
    this.peerConnection.oniceconnectionstatechange = (event) => {
      console.log(`ICE connection state: ${this.peerConnection.iceConnectionState}`);
    };
    this.peerConnection.onsignalingstatechange = (event) => {
      console.log(`Signaling state: ${this.peerConnection.signalingState}`);
    };
  }
  
  /**
   * Get a connection ID from the server
   */
  async getConnectionId() {
    const response = await fetch(`${this.apiBase}/rtc/connection/${this.cameraId}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${this.token}`
      }
    });
    
    if (!response.ok) {
      throw new Error(`Failed to get connection ID: ${response.status}`);
    }
    
    const data = await response.json();
    return data.connection_id;
  }
  
  /**
   * Create and send SDP offer to server
   */
  async createAndSendOffer() {
    try {
      // Create offer with video only (no audio)
      const offer = await this.peerConnection.createOffer({
        offerToReceiveVideo: true,
        offerToReceiveAudio: false
      });
      
      // Set as local description
      await this.peerConnection.setLocalDescription(offer);
      console.log('Set local description from offer');
      
      // Send offer to server and get answer
      const answerSdp = await this.sendOffer(offer.sdp);
      
      // CRITICAL: Set remote description with answer
      // Do NOT modify the SDP answer in any way to ensure media line order is preserved
      await this.peerConnection.setRemoteDescription({
        type: 'answer',
        sdp: answerSdp
      });
      
      console.log('Set remote description from server answer');
    } catch (error) {
      console.error('Error creating/sending offer:', error);
      throw error;
    }
  }
  
  /**
   * Send SDP offer to server and get answer
   */
  async sendOffer(offerSdp) {
    try {
      const response = await fetch(`${this.apiBase}/rtc/offer/${this.connectionId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.token}`
        },
        body: JSON.stringify({ sdp: offerSdp })
      });
      
      if (!response.ok) {
        throw new Error(`Server rejected offer: ${response.status}`);
      }
      
      const data = await response.json();
      return data.sdp;
    } catch (error) {
      console.error('Error sending offer to server:', error);
      throw error;
    }
  }
  
  /**
   * Handle ICE candidates and send them to the server
   */
  async handleICECandidate(event) {
    if (event.candidate) {
      try {
        await this.sendIceCandidate(event.candidate);
      } catch (error) {
        console.warn('Failed to send ICE candidate:', error);
      }
    }
  }
  
  /**
   * Send ICE candidate to server
   */
  async sendIceCandidate(candidate) {
    try {
      const response = await fetch(`${this.apiBase}/rtc/ice-candidate/${this.connectionId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.token}`
        },
        body: JSON.stringify(candidate)
      });
      
      if (!response.ok) {
        throw new Error(`Failed to send ICE candidate: ${response.status}`);
      }
    } catch (error) {
      console.error('Error sending ICE candidate:', error);
      throw error;
    }
  }
  
  /**
   * Handle incoming media tracks
   */
  handleTrack(event) {
    if (event.track.kind === 'video') {
      console.log('Received remote video track');
      
      // Connect the track to the video element
      if (this.videoElement && this.videoElement.srcObject !== event.streams[0]) {
        this.videoElement.srcObject = event.streams[0];
        console.log('Connected to camera stream');
      }
    }
  }
  
  /**
   * Handle connection state changes
   */
  handleConnectionStateChange() {
    const state = this.peerConnection.connectionState;
    console.log(`Connection state changed to: ${state}`);
    
    this.connectionState = state;
    
    switch (state) {
      case 'connected':
        // Connection established successfully
        this.reconnectAttempts = 0; // Reset reconnect counter
        break;
        
      case 'disconnected':
      case 'failed':
        // Handle connection failure
        console.warn(`WebRTC connection ${state}`);
        
        // Attempt reconnection
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++;
          console.log(`Reconnection attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
          
          // Exponential backoff
          const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
          setTimeout(() => this.connect(), delay);
        }
        break;
        
      case 'closed':
        // Connection closed normally
        console.log('WebRTC connection closed');
        break;
    }
  }
  
  /**
   * Disconnect and clean up resources
   */
  disconnect() {
    if (this.peerConnection) {
      // Remove all event listeners
      this.peerConnection.ontrack = null;
      this.peerConnection.onicecandidate = null;
      this.peerConnection.onconnectionstatechange = null;
      this.peerConnection.oniceconnectionstatechange = null;
      this.peerConnection.onsignalingstatechange = null;
      
      // Close the connection
      this.peerConnection.close();
      this.peerConnection = null;
      
      // Clean up video element
      if (this.videoElement && this.videoElement.srcObject) {
        const tracks = this.videoElement.srcObject.getTracks();
        tracks.forEach(track => track.stop());
        this.videoElement.srcObject = null;
      }
      
      this.connectionState = 'disconnected';
      console.log('WebRTC connection resources cleaned up');
    }
  }
}

/**
 * Usage example:
 * 
 * // In a React component
 * useEffect(() => {
 *   const videoElement = document.getElementById('camera-video');
 *   const webrtc = new ZVisionWebRTC(1, videoElement);
 *   
 *   webrtc.connect();
 *   
 *   // Clean up on unmount
 *   return () => {
 *     webrtc.disconnect();
 *   };
 * }, []);
 */
```

### React Component Implementation Example

Here's how you can implement the WebRTC connection in a React component:

```jsx
import React from 'react';
import CameraStream from './CameraStream';

const MultiCameraView = ({ cameraIds }) => {
  return (
    <div className="multi-camera-container">
      {cameraIds.map(cameraId => (
        <div key={cameraId} className="camera-cell">
          <h3>Camera {cameraId}</h3>
          <CameraStream cameraId={cameraId} />
        </div>
      ))}
    </div>
  );
};

export default MultiCameraView;
```

### CSS Styling Example

```css
.camera-stream {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  background-color: #000;
  margin-bottom: 20px;
}

.video-display {
  width: 100%;
  display: block;
}

.connection-status {
  position: absolute;
  top: 10px;
  right: 10px;
  background-color: rgba(0, 0, 0, 0.7);
  color: white;
  padding: 5px 10px;
  border-radius: 4px;
  font-size: 12px;
  z-index: 10;
}

.loading-indicator {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: white;
}

.spinner {
  border: 4px solid rgba(255, 255, 255, 0.3);
  border-radius: 50%;
  border-top: 4px solid white;
  width: 40px;
  height: 40px;
  margin: 0 auto 10px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.multi-camera-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
}

.camera-cell {
  background-color: #f5f5f5;
  border-radius: 8px;
  padding: 10px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}
```

This comprehensive implementation provides a robust WebRTC connection to the ZVision backend with proper error handling, reconnection logic, and user feedback.