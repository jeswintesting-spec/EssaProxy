import sys
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer

class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        import time
        # Simulate a slow backend server
        time.sleep(1.0)
        
        server_id = self.server.server_port
        
        # Extract X-Forwarded headers if present
        x_forwarded_for = self.headers.get("X-Forwarded-For", "None")
        x_forwarded_proto = self.headers.get("X-Forwarded-Proto", "None")
        
        response = f"Hello from backend running on port {server_id}\n"
        response += f"Your X-Forwarded-For: {x_forwarded_for}\n"
        response += f"Your X-Forwarded-Proto: {x_forwarded_proto}\n"
        
        self.wfile.write(response.encode("utf-8"))

def run(port: int):
    server_address = ('', port)
    httpd = HTTPServer(server_address, DummyHandler)
    print(f"Starting dummy backend on port {port}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    print(f"Stopping dummy backend on port {port}...")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    run(args.port)
