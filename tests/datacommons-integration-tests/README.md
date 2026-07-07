# Data Commons Integration Tests

This package contains the local system integration test suite for the Data Commons Platform (DCP). It verifies compatibility between Spanner database schemas, the ingestion helper service, the website serving backend, and semantic query APIs using emulated service containers.

## Prerequisites

- **Docker**: Docker must be running on your system to boot the emulated containers.
- **Python >= 3.11**

## Running the Integration Tests

To run the integration tests locally against the default `latest` images defined in `docker-compose.test.yml`:
```bash
uv run pytest tests/datacommons-integration-tests/run_local_integration_test.py
```

To test against other image tags (e.g. `stable` or specific version tags), set the `HELPER_IMAGE` and `SERVICES_IMAGE` environment variables:
```bash
HELPER_IMAGE=gcr.io/datcom-ci/datacommons-ingestion-helper:stable \
SERVICES_IMAGE=gcr.io/datcom-ci/datacommons-services:stable \
uv run pytest tests/datacommons-integration-tests/run_local_integration_test.py
```

> [!TIP]
> You can pass the `-s` flag to pytest (e.g., `uv run pytest -s ...`) to stream stdout and stderr directly to your console. This is highly useful for viewing real-time startup/teardown and execution logs from Docker Compose and the individual containers (Ingestion Helper, Website backend, etc.).

### Golden File Contract Testing

The integration tests assert database states and API responses against saved **Golden Files** inside `tests/datacommons-integration-tests/golden/`.

If you make expected changes to the database schema or the web API response structure, you can regenerate these goldens by running:
```bash
uv run pytest tests/datacommons-integration-tests/run_local_integration_test.py --generate-golden
```

### Debugging with Running Containers

By default, the testing script stops the container stack and clears volumes on completion. To keep the containers running for manual inspection (e.g. to connect to the Spanner emulator directly or query the web container ports):
```bash
uv run pytest tests/datacommons-integration-tests/run_local_integration_test.py --keep-containers
```

While running with `--keep-containers`, you can access:
- **Spanner Emulator**: `localhost:9010` (gRPC) / `localhost:9020` (REST)
- **GCS Emulator (fake-gcs-server)**: `localhost:9099`
- **Ingestion Helper**: `localhost:8081`
- **Website Backend**: `localhost:8082`

## Spanner Emulator Local Testing & Limitations

The local Docker Compose stack uses the Spanner Emulator for offline testing.

### Emulator Optimizer Bypass
The emulator is started with `--disable_query_null_filtered_index_check`. Required because the emulator rejects queries on null-filtered indexes (e.g., `NodeEmbeddingIndex`) unless all index keys are explicitly filtered for non-null values.

### Key Drawbacks & Gaps
* **No Real Vector Similarity (NL Search):** The emulator cannot run semantic vector searches (returns empty results). Also, public/production NLP API endpoints do not index custom locally-seeded variables, and the emulator gateway fails to pass `--disable_query_null_filtered_index_check` to the C++ gRPC engine on port `9010`. Local queries must bypass vector search by appending `disable_feature=use_v2_resolve_for_nl_search_vars` to use the text matcher.
* **Local UDF Routing only:** The `--remote_functions_host_port` flag can route `ML.PREDICT` to a local mock container on `localhost`, but connections are restricted to localhost.
* **Performance:** Runs in-memory and does not replicate multi-node Spanner scale or latency.
* **Heuristic Bypass Limitation:** Appending `disable_feature=use_v2_resolve_for_nl_search_vars` disables database-level vector index queries to bypass the emulator limits. **IMPORTANT:** This is a test-only workaround. To ensure that the actual production database index lookup and vector resolving code paths are verified before release, you must run the GCP sandbox integration tests (`run_gcp_integration_test.py`), which cover the active production vector path against a real GCP Spanner instance.

### Manual Verification of Local NL Search
1. **Boot containers:**
   ```bash
   docker compose -f tests/datacommons-integration-tests/docker-compose.test.yml up -d spanner gcs
   ```
2. **Seed Spanner and boot remaining services:**
   ```bash
   uv run pytest tests/datacommons-integration-tests/run_local_integration_test.py --keep-containers
   ```
3. **Query using the heuristic bypass:**
   ```bash
   curl -s -X POST "http://localhost:8082/api/explore/detect-and-fulfill?q=Number+of+frogs+in+United+States+of+America&disable_feature=use_v2_resolve_for_nl_search_vars" \
     -H "Content-Type: application/json" \
     -d '{"contextHistory": []}'
   ```

### Testing Custom NLP Models & Vertex AI

* **Option A: Custom NLP Service URL:** Point the `NL_SERVICE_ROOT_URL` environment variable of the `website` container to your custom model container port or external model API endpoint (and supply any required API keys in the container env).
* **Option B: Local Real NLP Service Container (CPU/MiniLM):** Run the official model server container locally on CPU using the HuggingFace `all-MiniLM-L6-v2` model:
  1. Enable the override configuration:
     ```bash
     cp tests/datacommons-integration-tests/docker-compose.override.yml.example tests/datacommons-integration-tests/docker-compose.override.yml
     ```
  2. Set your GCP project ID in `docker-compose.override.yml`:
     ```yaml
     GCP_PROJECT_ID: <YOUR_GCP_PROJECT_ID>
     ```
  3. Start the containers using the override:
     ```bash
     docker compose -f tests/datacommons-integration-tests/docker-compose.test.yml -f tests/datacommons-integration-tests/docker-compose.override.yml up -d
     uv run pytest tests/datacommons-integration-tests/run_local_integration_test.py --keep-containers
     ```
     *(Note: the automated pytest asserts will fail due to real vs. mock output differences, but the local stack will remain running and fully operational for custom testing)*.
* **Option C: Spanner UDF Proxy:** To test database-level `ML.PREDICT` calls, run a local proxy container in the Spanner service's network namespace (`network_mode: "service:spanner"`) to forward requests to Vertex AI. Configure the Spanner emulator container with `--remote_functions_host_port=localhost:<proxy_port>`.

---

## GCP Sandbox Integration Tests

This package includes a script to run end-to-end integration tests on real GCP sandbox resources to validate Terraform templates, GCS transfers, Spanner database seeding, and Cloud Run web server APIs.

### Running the GCP Tests
Requires authenticated GCP CLI access:
```bash
python3 tests/datacommons-integration-tests/run_gcp_integration_test.py \
    --project-id <YOUR_GCP_PROJECT_ID> \
    --dc-api-key "YOUR_GOOGLE_DATA_COMMONS_API_KEY"
```

Alternatively, pass the API key via an environment variable:
```bash
DC_API_KEY="YOUR_API_KEY" python3 tests/datacommons-integration-tests/run_gcp_integration_test.py \
    --project-id <YOUR_GCP_PROJECT_ID>
```

### Script Arguments
*   `--project-id`: GCP Project ID (default: `datcom-ci`).
*   `--dc-api-key`: Data Commons API Key.
*   `--region`: GCP region (default: `us-central1`).
*   `--namespace`: Custom resource naming namespace (default: randomized `itest-XXXX`).
*   `--keep-sandbox`: Do not destroy sandbox GCP resources on completion (useful for debugging).
*   `--reuse-sandbox`: Reuse existing sandbox resources (requires passing persistent `--namespace` and having run with `--keep-sandbox` previously).
*   `--tf-git-ref`: Git reference for the Terraform templates repository (default: `main`).
*   `--services-image`, `--preprocessing-image`, `--helper-image`: Override container images deployed during provisioning.



