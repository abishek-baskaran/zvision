#!/usr/bin/env python3
"""
Simple HTTP server to serve the detection API test HTML page.
"""

import http.server
import socketserver
import os
import argparse
from urllib.parse import urlparse, parse_qs

# Default port
DEFAULT_PORT = 8081

class CORSHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP request handler with CORS headers"""
    
    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        super().end_headers()
    
    def do_OPTIONS(self):
        # Handle OPTIONS request for CORS preflight
        self.send_response(200)
        self.end_headers()
    
    def do_GET(self):
        # Redirect root to the test page
        if self.path == '/':
            self.path = '/detect_endpoints_test.html'
        return http.server.SimpleHTTPRequestHandler.do_GET(self)

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Serve the detection API test HTML page')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT,
                        help=f'Port to listen on (default: {DEFAULT_PORT})')
    args = parser.parse_args()
    
    # Change to the directory containing the HTML file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Set up the server
    handler = CORSHTTPRequestHandler
    httpd = socketserver.TCPServer(("", args.port), handler)
    
    print(f"Serving at http://localhost:{args.port}")
    print(f"Test page available at http://localhost:{args.port}/detect_endpoints_test.html")
    print("Press Ctrl+C to stop the server")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        httpd.server_close()

if __name__ == "__main__":
    main() 