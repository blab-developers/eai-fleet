"""Tiny mock backend for interactive frontend verification."""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler

DEVICES = [
    {
        "device_id": "jetson-00",
        "name": "OR-1 Nano",
        "state": "running",
        "fps": 29.5,
        "gpu_utilization": 73,
        "health": "online",
    },
    {
        "device_id": "jetson-01",
        "name": "OR-2 Nano",
        "state": "stopped",
        "fps": 0.0,
        "gpu_utilization": 0,
        "health": "online",
    },
    {
        "device_id": "jetson-02",
        "name": "Lab Nano",
        "state": "stopped",
        "fps": 0.0,
        "gpu_utilization": 0,
        "health": "offline",
    },
]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/api/fleet/devices":
            online = sum(1 for d in DEVICES if d["health"] == "online")
            self._json(200, {"devices": DEVICES, "total": len(DEVICES), "online": online})
        else:
            self._json(404, {"detail": "not found"})

    def do_POST(self):
        if self.path.startswith("/api/fleet/devices/") and self.path.endswith("/inference/image"):
            self._json(
                200,
                {
                    "device_id": "jetson-00",
                    "image": "registry.endoscopeai.com/eai-nano/inference:v0.4.2",
                    "scope": "fleet-wide",
                    "note": "Inference DaemonSet eai-nano/eai-nano-inference patched.",
                },
            )
        else:
            self._json(404, {"detail": "not found"})

    def _json(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 8088), Handler)
    print("Mock backend on http://127.0.0.1:8088")
    server.serve_forever()
