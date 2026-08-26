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


class MockNLHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/healthz", "/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            req_data = json.loads(body)
        except Exception:
            req_data = {}

        queries = req_data.get("queries", [])
        if isinstance(queries, str):
            queries = [queries]

        if "/api/embedding" in self.path or "/encode" in self.path:
            response = {"embeddings": [DUMMY_VECTOR for _ in queries]}
        else:
            matches = []
            for q in queries:
                q_lower = q.lower()
                matched_vars = []
                for k, v in STATVAR_MAPPING.items():
                    if k in q_lower:
                        matched_vars.extend(v)
                if not matched_vars:
                    matched_vars = ["average_annual_wage"]
                matches.append(list(dict.fromkeys(matched_vars)))

            response = {
                "candidates": matches[0] if matches else [],
                "entities": [{"candidates": [{"dcid": v} for v in matches[0]]}] if matches else [],
                "query": queries[0] if queries else "",
            }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode("utf-8"))

    def log_message(self, format_str, *args):
        pass


def run(port: int = 6060):
    server = HTTPServer(("0.0.0.0", port), MockNLHandler)  # noqa: S104
    print(f"Mock NL Server running on port {port}...", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 6060
    run(port)
