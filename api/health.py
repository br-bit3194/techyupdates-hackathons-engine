"""Vercel Serverless Health Check Endpoint for TechyUpdates Hackathons Engine."""

import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    """Health check HTTP handler."""

    def do_GET(self):
        response_data = {
            "status": "healthy",
            "service": "techyupdates-hackathons-engine",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "2.1.0",
        }
        response_bytes = json.dumps(response_data, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)
