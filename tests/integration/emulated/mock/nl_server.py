# Copyright 2026 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Lightweight zero-dependency mock NL and embeddings server for hermetic testing."""

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

DUMMY_VECTOR = [0.01] * 768

STATVAR_MAPPING = {
    "wage": ["average_annual_wage", "gender_wage_gap"],
    "wages": ["average_annual_wage", "gender_wage_gap"],
    "annual wage": ["average_annual_wage"],
    "gender wage": ["gender_wage_gap"],
    "gender wage gap": ["gender_wage_gap"],
}


def _handle_request(path: str, req_data: dict) -> tuple[int, dict]:
    if path in ("/healthz", "/", "/version"):
        return 200, {"status": "ok"}

    queries = req_data.get("queries", [])
    if isinstance(queries, str):
        queries = [queries]
    if not queries and "nodes" in req_data:
        queries = req_data["nodes"]

    if "/api/embedding" in path or "/encode" in path:
        return 200, {"embeddings": [DUMMY_VECTOR for _ in queries]}

    matches = []
    for q in queries:
        q_lower = str(q).lower()
        matched = False
        for key, dcids in STATVAR_MAPPING.items():
            if key in q_lower:
                matches.extend(dcids)
                matched = True
        if not matched:
            matches.append("average_annual_wage")

    resp_data = {
        "entities": [
            {
                "query": q,
                "candidates": [{"dcid": m, "score": 0.99} for m in set(matches)],
            }
            for q in queries
        ]
    }
    return 200, resp_data


def app(environ, start_response):
    """WSGI callable for Gunicorn running inside website container."""
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET")
    req_data = {}
    if method == "POST":
        try:
            length = int(environ.get("CONTENT_LENGTH", 0) or 0)
            body = environ["wsgi.input"].read(length).decode("utf-8") if length > 0 else "{}"
            req_data = json.loads(body)
        except Exception:
            req_data = {}

    status_code, resp_obj = _handle_request(path, req_data)
    status_str = f"{status_code} OK" if status_code == 200 else f"{status_code} Not Found"
    resp_bytes = json.dumps(resp_obj).encode("utf-8")
    start_response(status_str, [("Content-Type", "application/json"), ("Content-Length", str(len(resp_bytes)))])

class MockNLHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        code, resp = _handle_request(self.path, {})
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(resp).encode("utf-8"))

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            req_data = json.loads(body)
        except Exception:
            req_data = {}

        code, resp = _handle_request(self.path, req_data)
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(resp).encode("utf-8"))

    def log_message(self, format_str, *args):
        pass


def run(port: int = 6060):
    server = HTTPServer(("0.0.0.0", port), MockNLHandler)  # noqa: S104
    server.serve_forever()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 6060
    run(port)
