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

"""Mock NL Server for local integration testing.

CAVEAT / DESIGN DECISION:
This mock server is introduced to bypass the requirement of running a heavy
embeddings/vectorization model (SentenceTransformers) or calling the Vertex AI
prediction APIs inside the hermetic/credentials-free docker integration test stack.

- Running Vertex AI requires GCP credentials which cannot be checked into CI.
- Running a local SentenceTransformer model requires downloading ~100MB of model
  weights at test runtime which introduces flakiness and violates offline-hermeticity.

Thus, we spin up this lightweight 0-dependency mock server in python to intercept
NL search requests (like "Number of frogs") and map them to seeded Spanner variables
(like "number_of_frogs"). This allows us to test the happy path end-to-end (querying
spanner and asserting observation charts) without real model serving infrastructure.

TODO: Remove this mock server and use a proper local SentenceTransformers
model configuration once the test environment supports hermetic caching of HuggingFace
models in the website container image.
"""

import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger("mock_nl_server")


# Default query mappings
DEFAULT_MAPPINGS = {
    "average annual wage in united states of america": {
        "SV": ["average_annual_wage"],
        "CosineScore": [0.9],
        "SV_to_Sentences": {
            "average_annual_wage": [{"sentence": "Average annual wage", "score": 0.9}]
        },
    },
    "gender wage gap in united states of america": {
        "SV": ["gender_wage_gap"],
        "CosineScore": [0.9],
        "SV_to_Sentences": {
            "gender_wage_gap": [{"sentence": "Gender wage gap", "score": 0.9}]
        },
    },
}


def load_mappings():
    mappings = dict(DEFAULT_MAPPINGS)
    config_path = Path("/app/mock_queries.json")
    if config_path.exists():
        try:
            with config_path.open() as f:
                custom_mappings = json.load(f)
                for k, v in custom_mappings.items():
                    mappings[k.lower().strip()] = v
            logger.info("Loaded custom query mappings from %s", config_path)
        except Exception as e:  # noqa: BLE001
            logger.error("Failed to load custom query mappings: %s", e)
    return mappings


class MockNLServerHandler(BaseHTTPRequestHandler):
    def log_message(self, log_format: str, *args: any) -> None:
        # Override to log via standard python logging instead of stderr
        logger.info(
            "%s - - [%s] %s",
            self.address_string(),
            self.log_date_time_string(),
            log_format % args,  # noqa: UP031
        )

    def do_GET(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
            return

        if parsed_path.path == "/api/server_config":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            config = {"default_indexes": ["custom_index"]}
            self.wfile.write(json.dumps(config).encode("utf-8"))
            return

        self.send_error(404, f"File Not Found: {self.path}")

    def do_POST(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == "/api/search_vars":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                req_json = json.loads(post_data.decode("utf-8"))
            except ValueError:
                self.send_error(400, "Invalid JSON payload")
                return

            queries = req_json.get("queries", [])
            logger.info("Received search queries: %s", queries)

            mappings = load_mappings()
            query_results = {}
            for q in queries:
                cleaned_q = q.lower().strip().rstrip("?")
                if cleaned_q in mappings:
                    query_results[q] = mappings[cleaned_q]
                elif "wage" in cleaned_q:
                    # Fallback keyword matching for wage queries
                    query_results[q] = mappings.get(
                        "average annual wage in united states of america"
                    )
                else:
                    # Fallback for unrecognized queries
                    query_results[q] = {
                        "SV": [],
                        "CosineScore": [],
                        "SV_to_Sentences": {},
                    }

            response = {"queryResults": query_results, "scoreThreshold": 0.5}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))
            return

        self.send_error(404, f"Endpoint Not Found: {self.path}")


def run(server_class=HTTPServer, handler_class=MockNLServerHandler, port=6060):
    server_address = ("", port)
    httpd = server_class(server_address, handler_class)
    logger.info("Mock NL Server running on port %d...", port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        logger.info("Mock NL Server stopped.")


if __name__ == "__main__":
    run()
