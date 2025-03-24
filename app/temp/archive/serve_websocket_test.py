#!/usr/bin/env python3
import os
import http.server
import socketserver
import socket
import json
import urllib.request
import urllib.error
import urllib.parse
from urllib.parse import parse_qs, urlparse

# Configuration
PORT = 8100
FALLBACK_PORTS = [8101, 8102, 8103, 8104]  # Alternative ports if primary is in use
HTML_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "websocket_browser_test.html")
MAIN_SERVER = "localhost:8000"  # The main FastAPI server

class TestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Serve the HTML file
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            with open(HTML_FILE, 'rb') as file:
                self.wfile.write(file.read())
        else:
            # Serve other files as normal
            super().do_GET()
    
    def do_POST(self):
        # Handle token proxy requests
        if self.path.startswith('/proxy-token'):
            self._handle_proxy_request()
        else:
            # Not implemented
            self.send_response(501)
            self.end_headers()
            self.wfile.write(b"Not Implemented")
    
    def _handle_proxy_request(self):
        """Proxy token requests to the main server"""
        try:
            # Parse query parameters
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            
            # Get target server (or use default)
            server = query_params.get('server', [MAIN_SERVER])[0]
            
            # Get content length
            content_length = int(self.headers['Content-Length'])
            
            # Read request body
            request_body = self.rfile.read(content_length).decode('utf-8')
            request_data = json.loads(request_body)
            
            username = request_data.get('username', '')
            password = request_data.get('password', '')
            
            # Create form data for the API
            form_data = urllib.parse.urlencode({
                'username': username,
                'password': password
            }).encode('utf-8')
            
            # Create request to forward to the main server
            req = urllib.request.Request(
                f"http://{server}/api/token",
                data=form_data,
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
            )
            
            # Forward the request
            print(f"Forwarding token request to http://{server}/api/token")
            with urllib.request.urlopen(req) as response:
                # Get response data
                response_body = response.read()
                response_status = response.status
                response_headers = response.getheaders()
                
                # Send response back to client
                self.send_response(response_status)
                
                # Add CORS headers to allow cross-origin requests
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                
                # Forward relevant headers
                for header, value in response_headers:
                    if header.lower() not in ('transfer-encoding', 'connection'):
                        self.send_header(header, value)
                
                self.end_headers()
                self.wfile.write(response_body)
                
        except urllib.error.HTTPError as e:
            # Forward the error response
            self.send_response(e.code)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            error_message = json.dumps({
                'detail': f"Authentication failed: {e.reason}"
            })
            self.wfile.write(error_message.encode('utf-8'))
            
        except Exception as e:
            # Handle unexpected errors
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            error_message = json.dumps({
                'detail': f"Internal server error: {str(e)}"
            })
            self.wfile.write(error_message.encode('utf-8'))
    
    def do_OPTIONS(self):
        """Handle preflight CORS requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def log_message(self, format, *args):
        """Override to show detailed logs"""
        print(f"{self.client_address[0]} - {format % args}")

# Custom TCP server that allows address reuse
class ReuseAddressServer(socketserver.TCPServer):
    allow_reuse_address = True

def main():
    # Check if the HTML file exists
    if not os.path.exists(HTML_FILE):
        print(f"Error: HTML file not found at {HTML_FILE}")
        exit(1)
        
    # Get the directory of the HTML file
    os.chdir(os.path.dirname(HTML_FILE))
    
    # Try primary port, then fall back to alternatives
    server_port = PORT
    server = None
    
    # Try each port until one works
    ports_to_try = [PORT] + FALLBACK_PORTS
    for port in ports_to_try:
        try:
            server = ReuseAddressServer(("", port), TestHandler)
            server_port = port
            break
        except socket.error as e:
            print(f"Port {port} is already in use, trying next port...")
    
    if server is None:
        print(f"Error: All ports {ports_to_try} are in use. Please free a port and try again.")
        exit(1)
    
    print(f"Serving WebSocket test page at http://localhost:{server_port}")
    print(f"Connect to main server at {MAIN_SERVER}")
    print(f"Press Ctrl+C to stop the server")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped by user")
        server.server_close()

if __name__ == "__main__":
    main() 