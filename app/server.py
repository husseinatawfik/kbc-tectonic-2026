"""Local demo server for KBC Parallel.

Serves the single-page interface and the simulation API. The page never
calculates projections itself.
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from app.data.synthetic import (
    AS_OF,
    COHORTS,
    GOAL_SEARCH_MONTHS,
    HORIZON_MONTHS,
    MOCK_CAR_APR,
    PROFILES,
)
from app.simulation.engine import SimulationInputError
from app.simulation.scenarios import simulate_from_payload

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
}


def make_server(host: str = "0.0.0.0", port: int = 8080) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), Handler)


def simulate_request(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise SimulationInputError("Request body must be a JSON object.")
    profile_id = str(payload.get("profile") or "alex").lower()
    if profile_id not in PROFILES:
        raise SimulationInputError("Choose Alex or Sam.")
    return simulate_from_payload(
        PROFILES[profile_id],
        COHORTS[profile_id],
        payload,
        as_of=AS_OF,
        annual_interest_rate=MOCK_CAR_APR,
        horizon_months=HORIZON_MONTHS,
        search_months=GOAL_SEARCH_MONTHS,
    )


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            self._json(200, {"ok": True})
            return
        if path in ("/", "/index.html"):
            self._send_file(STATIC / "index.html")
            return
        if path.startswith("/static/"):
            relative = path.removeprefix("/static/")
            candidate = (STATIC / relative).resolve()
            if STATIC.resolve() not in candidate.parents and candidate != STATIC.resolve():
                self._json(404, {"error": "Not found"})
                return
            self._send_file(candidate)
            return
        self._json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/simulate":
            self._json(404, {"error": "Not found"})
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > 20_000:
            self._json(413, {"error": "Request is too large."})
            return
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "Request body must be JSON."})
            return
        try:
            result = simulate_request(payload)
        except SimulationInputError as error:
            self._json(400, {"error": str(error)})
            return
        self._json(200, result)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[kbc-parallel] {self.address_string()} {fmt % args}")

    def _send_file(self, path: Path) -> None:
        if not path.is_file():
            self._json(404, {"error": "Not found"})
            return
        body = path.read_bytes()
        content_type = CONTENT_TYPES.get(path.suffix, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    import os

    port = int(os.environ.get("PORT", "8080"))
    server = make_server(port=port)
    print(f"KBC Parallel running at http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
