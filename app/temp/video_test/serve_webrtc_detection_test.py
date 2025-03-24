#!/usr/bin/env python3
"""
HTTP server for WebRTC + Detection test.
"""

import http.server
import socketserver
import os
import sys
import socket
import argparse

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

# Parse command line arguments
parser = argparse.ArgumentParser(description='Serve WebRTC + Detection test page')
parser.add_argument('--port', type=int, default=8081, help='Port to listen on')
parser.add_argument('--dir', type=str, default=os.path.dirname(os.path.abspath(__file__)),
                    help='Directory to serve files from')
args = parser.parse_args()

# Set the directory to serve files from
os.chdir(args.dir)

# Import JSON for API responses
import json
import time
from urllib.parse import parse_qs, urlparse

# Mock detection state
mock_detection_sessions = {}

# Mock detection configuration
mock_detection_config = {}

# Custom request handler with CORS support and mock API endpoints
class Handler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler with CORS headers and mock API endpoints."""
    
    def end_headers(self):
        """Add CORS headers."""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        super().end_headers()
    
    def do_OPTIONS(self):
        """Handle preflight requests."""
        self.send_response(200)
        self.end_headers()
    
    def do_POST(self):
        """Handle POST requests for API endpoints."""
        url_parts = urlparse(self.path)
        path = url_parts.path
        print(f"DEBUG: Received POST request to path: {path}")
        
        # Normalize path to handle double /api/ prefix if present
        if path.startswith('/api/api/'):
            path = path.replace('/api/api/', '/api/', 1)
            print(f"DEBUG: Normalized path to: {path}")
        
        # Handle standard detection config endpoint
        if path == '/api/detection/config':
            try:
                # Read request body
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                # Extract parameters from request body - ensure types match FastAPI model
                camera_id = data.get('camera_id')
                if not isinstance(camera_id, int):
                    # Return 422 Unprocessable Entity
                    self.send_response(422)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    
                    response = {'detail': [{'loc': ['body', 'camera_id'], 'msg': 'value is not a valid integer', 'type': 'type_error.integer'}]}
                    self.wfile.write(json.dumps(response).encode('utf-8'))
                    return
                    
                enabled = data.get('enabled', False) 
                interval_seconds = data.get('interval_seconds', 10)
                
                # Make sure interval_seconds is an integer
                if not isinstance(interval_seconds, int):
                    # Return 422 Unprocessable Entity
                    self.send_response(422)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    
                    response = {'detail': [{'loc': ['body', 'interval_seconds'], 'msg': 'value is not a valid integer', 'type': 'type_error.integer'}]}
                    self.wfile.write(json.dumps(response).encode('utf-8'))
                    return
                
                # Update detection configuration
                mock_detection_config[camera_id] = {
                    'enabled': enabled,
                    'interval_seconds': interval_seconds,
                    'last_update': time.time()
                }
                
                # If enabled, create/update a detection session
                if enabled:
                    frame_rate = 1.0 / interval_seconds if interval_seconds > 0 else 1.0
                    mock_detection_sessions[camera_id] = {
                        'active': True,
                        'start_time': time.time(),
                        'frame_rate': frame_rate
                    }
                else:
                    # If disabled, mark session as inactive
                    if camera_id in mock_detection_sessions:
                        mock_detection_sessions[camera_id]['active'] = False
                
                # Send success response
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                response = {
                    'camera_id': camera_id,
                    'enabled': enabled,
                    'interval_seconds': interval_seconds,
                    'status': 'updated'
                }
                self.wfile.write(json.dumps(response).encode('utf-8'))
                action = "Started" if enabled else "Stopped"
                print(f"{action} mock detection for camera {camera_id} at {1.0/interval_seconds if interval_seconds > 0 else 0} FPS")
                return
                
            except Exception as e:
                # Send error response
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                response = {'detail': f'Failed to start detection: {str(e)}'}
                self.wfile.write(json.dumps(response).encode('utf-8'))
                return
        
        # Handle direct detection endpoint
        elif path.startswith('/api/detect'):
            try:
                # Extract camera ID from query params or body
                camera_id = None
                
                # Check for query parameters
                query_params = {}
                if '?' in self.path:
                    query_string = self.path.split('?', 1)[1]
                    query_params = {k: v for k, v in [param.split('=') for param in query_string.split('&')]}
                    
                # Get camera_id from query params
                if 'camera_id' in query_params:
                    camera_id = query_params.get('camera_id')
                    print(f"DEBUG: Got camera_id={camera_id} from query params")
                    
                # If not in query params, check request body
                if not camera_id and int(self.headers.get('Content-Length', 0)) > 0:
                    content_length = int(self.headers['Content-Length'])
                    post_data = self.rfile.read(content_length)
                    try:
                        data = json.loads(post_data.decode('utf-8'))
                        camera_id = data.get('camera_id')
                        print(f"DEBUG: Got camera_id={camera_id} from request body")
                    except json.JSONDecodeError:
                        pass
                
                if not camera_id:
                    # Send bad request response
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    
                    response = {'detail': 'camera_id is required as either a query parameter or in the request body.'}
                    self.wfile.write(json.dumps(response).encode('utf-8'))
                    return
                    
                # Make sure camera_id is a string (as required by the API)
                if not isinstance(camera_id, str):
                    camera_id = str(camera_id)
                    
                # Try to convert to int for internal processing
                try:
                    camera_id_int = int(camera_id)
                except ValueError:
                    # Send bad request response
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    
                    response = {'detail': 'Invalid camera_id (must be convertible to an integer).'}
                    self.wfile.write(json.dumps(response).encode('utf-8'))
                    return
                
                # Generate mock detections (1-3 random person detections)
                detections = []
                num_detections = min(3, max(1, int(time.time()) % 4))
                
                for _ in range(num_detections):
                    # Create a random detection box (similar to what YOLO would return)
                    x1 = int(100 + 200 * (time.time() % 0.3))
                    y1 = int(100 + 200 * (time.time() % 0.5))
                    width = int(100 + 100 * (time.time() % 0.2))
                    height = int(200 + 100 * (time.time() % 0.3))
                    
                    detections.append({
                        'class_id': 0,
                        'class_name': 'person',
                        'confidence': 0.8 + 0.2 * (time.time() % 0.1),
                        'bbox': [x1, y1, x1 + width, y1 + height]
                    })
                
                # Send response with mock detections
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                response = {
                    'camera_id': camera_id,
                    'timestamp': time.time(),
                    'detections': detections
                }
                
                self.wfile.write(json.dumps(response).encode('utf-8'))
                print(f"Sent {len(detections)} mock detections for camera {camera_id}")
                return
                
            except Exception as e:
                # Send error response
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                response = {'detail': f'Failed to stop detection: {str(e)}'}
                self.wfile.write(json.dumps(response).encode('utf-8'))
                return
        
        # If not an API endpoint, serve static files
        return http.server.SimpleHTTPRequestHandler.do_POST(self)
    
    def do_GET(self):
        """Handle GET requests for API endpoints."""
        url_parts = urlparse(self.path)
        path = url_parts.path
        
        # Normalize path to handle double /api/ prefix if present
        if path.startswith('/api/api/'):
            path = path.replace('/api/api/', '/api/', 1)
            print(f"DEBUG: Normalized path to: {path}")
            
        # Handle detection status endpoint
        if path.startswith('/api/detection-webrtc/webrtc/') and path.endswith('/detect/status'):
            try:
                # Parse camera ID from URL
                parts = path.split('/')
                camera_id = int(parts[4])
                
                # Check if detection is active for this camera
                if camera_id in mock_detection_sessions:
                    session = mock_detection_sessions[camera_id]
                    active = session.get('active', False)
                    
                    # Generate mock detections if active
                    latest_detections = []
                    latest_detection_time = None
                    
                    if active:
                        # Generate 1-3 random detections
                        num_detections = min(3, max(1, int(time.time()) % 4))
                        latest_detection_time = time.time()
                        
                        for _ in range(num_detections):
                            # Create a random detection box
                            x1 = int(100 + 200 * (time.time() % 0.3))
                            y1 = int(100 + 200 * (time.time() % 0.5))
                            width = int(100 + 100 * (time.time() % 0.2))
                            height = int(200 + 100 * (time.time() % 0.3))
                            
                            latest_detections.append({
                                'class_id': 0,
                                'class_name': 'person',
                                'confidence': 0.8 + 0.2 * (time.time() % 0.1),
                                'bbox': [x1, y1, x1 + width, y1 + height]
                            })
                    
                    # Send response
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    
                    response = {
                        'camera_id': camera_id,
                        'active': active,
                        'latest_detections': latest_detections,
                        'latest_detection_time': latest_detection_time,
                        'frame_rate': session.get('frame_rate', 5)
                    }
                    
                    self.wfile.write(json.dumps(response).encode('utf-8'))
                    print(f"Sent mock detection status for camera {camera_id}")
                    return
                else:
                    # Send not found response
                    self.send_response(404)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    
                    response = {'detail': f'No detection session found for camera {camera_id}'}
                    self.wfile.write(json.dumps(response).encode('utf-8'))
                    return
                
            except Exception as e:
                # Send error response
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                response = {'detail': f'Failed to get detection status: {str(e)}'}
                self.wfile.write(json.dumps(response).encode('utf-8'))
                return
        
        # If not an API endpoint, serve static files
        return http.server.SimpleHTTPRequestHandler.do_GET(self)
    
    def log_message(self, format, *args):
        """Custom log message format."""
        client_addr = self.client_address[0]
        sys.stderr.write(f"{client_addr} - {format % args}\n")

# Get local IP address for user convenience
def get_local_ip():
    """Get local IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

# Print server banner
local_ip = get_local_ip()
port = args.port
print(f"""
┌───────────────────────────────────────────────┐
│        ZVision WebRTC + Detection Test        │
├───────────────────────────────────────────────┤
│ Server running at:                            │
│                                               │
│   http://{local_ip}:{port}/                     
│   http://localhost:{port}/                      
│                                               │
│ WebRTC Detection Test page:                   │
│                                               │
│   http://{local_ip}:{port}/webrtc_detection_test.html     
│   http://localhost:{port}/webrtc_detection_test.html      
│                                               │
│ Press Ctrl+C to stop the server               │
└───────────────────────────────────────────────┘
""")

# Start the server
with socketserver.TCPServer(("", port), Handler) as httpd:
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
