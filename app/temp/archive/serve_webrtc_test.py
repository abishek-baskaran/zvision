#!/usr/bin/env python3
"""
Simple HTTP server for WebRTC test page.
"""

import http.server
import socketserver
import os
import sys
import socket
import argparse

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Parse command line arguments
parser = argparse.ArgumentParser(description='Serve WebRTC test page')
parser.add_argument('--port', type=int, default=8080, help='Port to listen on')
parser.add_argument('--dir', type=str, default=os.path.dirname(os.path.abspath(__file__)),
                    help='Directory to serve files from')
args = parser.parse_args()

# Set the directory to serve files from
os.chdir(args.dir)

# Custom request handler with CORS support
class Handler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler with CORS headers."""
    
    def end_headers(self):
        """Add CORS headers."""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_OPTIONS(self):
        """Handle preflight requests."""
        self.send_response(200)
        self.end_headers()
    
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
│             ZVision WebRTC Test               │
├───────────────────────────────────────────────┤
│ Server running at:                            │
│                                               │
│   http://{local_ip}:{port}/                     
│   http://localhost:{port}/                      
│                                               │
│ WebRTC Test page:                             │
│                                               │
│   http://{local_ip}:{port}/webrtc_test.html     
│   http://localhost:{port}/webrtc_test.html      
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