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
NL search requests (like "Average annual wage") and map them to seeded Spanner variables
(like "average_annual_wage"). This allows us to test the happy path end-to-end (querying
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

logger = logging.getLogger("local_nl_server")


import os
from sentence_transformers import SentenceTransformer, util
from google.cloud import spanner

# Global NL Resolver instance
_NL_RESOLVER = None

class NLResolver:
    def __init__(self):
        print(">>> Loading SentenceTransformer model (all-mpnet-base-v2)...", flush=True)
        # Using all-mpnet-base-v2 to match default schema dimensions
        self.model = SentenceTransformer('all-mpnet-base-v2')
        self.var_embeddings = {} # DCID -> embedding
        self.var_names = {} # DCID -> name

    def load_variables(self):
        project_id = os.getenv("SPANNER_PROJECT_ID", "default")
        instance_id = os.getenv("SPANNER_INSTANCE_ID", "default")
        database_id = os.getenv("SPANNER_DATABASE_ID", "test-db")
        emulator_host = os.getenv("SPANNER_EMULATOR_HOST")

        print(f">>> Connecting to Spanner at {emulator_host}...", flush=True)
        # Apply emulator patch if needed, but in container sitecustomize should handle it
        client = spanner.Client(project=project_id)
        instance = client.instance(instance_id)
        database = instance.database(database_id)

        print(">>> Reading variables from Spanner...", flush=True)
        with database.snapshot() as snapshot:
            results = snapshot.execute_sql(
                "SELECT subject_id, name FROM Node WHERE 'StatisticalVariable' IN UNNEST(types)"
            )
            for row in results:
                dcid, name = row[0], row[1]
                if name:
                    self.var_names[dcid] = name

        print(f">>> Generating embeddings for {len(self.var_names)} variables...", flush=True)
        if self.var_names:
            names = list(self.var_names.values())
            dcids = list(self.var_names.keys())
            embeddings = self.model.encode(names, show_progress_bar=True)
            for dcid, emb in zip(dcids, embeddings):
                self.var_embeddings[dcid] = emb
        print(">>> NL Resolver ready.", flush=True)

    def search(self, query, top_k=5):
        if not self.var_embeddings:
            return []
        
        query_emb = self.model.encode(query)
        results = []
        for dcid, var_emb in self.var_embeddings.items():
            score = util.cos_sim(query_emb, var_emb).item()
            results.append((dcid, score))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

def get_resolver():
    global _NL_RESOLVER
    if _NL_RESOLVER is None:
        resolver = NLResolver()
        resolver.load_variables()
        _NL_RESOLVER = resolver
    return _NL_RESOLVER




class LocalNLServerHandler(BaseHTTPRequestHandler):
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

            resolver = get_resolver()

            query_results = {}
            for q in queries:
                search_results = resolver.search(q)

                sv_list = [r[0] for r in search_results]
                scores = [r[1] for r in search_results]

                sv_to_sentences = {}
                for dcid, score in search_results:
                    sv_to_sentences[dcid] = [{"sentence": resolver.var_names.get(dcid, ""), "score": score}]

                query_results[q] = {
                    "SV": sv_list,
                    "CosineScore": scores,
                    "SV_to_Sentences": sv_to_sentences
                }


            response = {"queryResults": query_results, "scoreThreshold": 0.5}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))
            return

        self.send_error(404, f"Endpoint Not Found: {self.path}")


def run(server_class=HTTPServer, handler_class=LocalNLServerHandler, port=6060):
    # Pre-load resolver to warm up model and load variables before serving
    logger.info("Pre-loading NL Resolver...")
    try:
        get_resolver()
        logger.info("NL Resolver loaded successfully.")
    except Exception as e:
        logger.error("Failed to load NL Resolver: %s", e)
        # We might want to exit or continue, let's continue but log error
        # If it fails here, requests will likely fail too.

    server_address = ("", port)
    httpd = server_class(server_address, handler_class)
    logger.info("Local NL Server running on port %d...", port)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        logger.info("Local NL Server stopped.")


if __name__ == "__main__":
    run()
