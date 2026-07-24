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

## Custom Feature Flags

Local integration tests run with the Spanner multi-entity schema enabled by default in the Mixer backend. This is controlled by mounting [custom_feature_flags.yaml](./custom_feature_flags.yaml) inside the `website` container at `/workspace/deploy/featureflags/custom.yaml`.

The container entrypoint detects the environment variable `RESOLVE_WITH_SPANNER_EMBEDDINGS=true` (defined in `docker-compose.test.yml`) and starts Mixer using these flags.

You can modify the flags inside `custom_feature_flags.yaml` if you need to tweak the Mixer server configuration for local debugging.

---

## GCP Sandbox Integration Tests

In addition to local emulated tests, this package includes a script to run automated, end-to-end integration tests on GCP real resources. This validates Terraform scaffolding, GCS, Spanner database seeding, Cloud Workflow executions, and Cloud Run web server APIs.

### Execution Modes

The GCP integration runner supports two execution modes:

#### 1. Heavy Mode (Full Provisioning & E2E Validation)
Pulls the latest templates, provisions a completely new isolated sandbox stack in GCP via Terraform (Spanner DB, GCS bucket, Cloud Workflows, and Cloud Run service), performs ingestion, runs the tests, and destroys the sandbox on completion (unless `--keep-sandbox` is specified).
* **Usage:**
  ```bash
  uv run python tests/datacommons-integration-tests/gcp_test_runner.py \
      --project-id datcom-ci \
      --dc-api-key "YOUR_API_KEY"
  ```

#### 2. Lightweight Mode (Fast Debugging Loop)
Skips the slow Terraform setup and teardown stages entirely. It reads resource configurations from an existing `/tmp/workspace-<instance-name>` directory, clears the database tables, re-uploads local test data files, triggers the ingestion workflow, and runs `pytest`. This reduces iteration time **from 10+ minutes down to 1-2 minutes**.
* **Usage:**
  1. First, create a persistent sandbox and keep it alive:
     ```bash
     uv run python tests/datacommons-integration-tests/gcp_test_runner.py --instance-name my-debug-sandbox --keep-sandbox
     ```
  2. Run subsequent test runs in lightweight mode:
     ```bash
     uv run python tests/datacommons-integration-tests/gcp_test_runner.py --instance-name my-debug-sandbox --reuse-sandbox
     ```


### Script Arguments
*   `--project-id`: The Google Cloud Project ID where the sandbox resources should be provisioned (default: `datcom-ci`).
*   `--dc-api-key`: Google Data Commons API Key needed to authenticate and configure sandbox clients.
*   `--region`: The GCP region to deploy resources (default: `us-central1`).
*   `--instance-name`: Custom naming instance name for resources (default: randomized `itest-XXXX`).
*   `--keep-sandbox`: Do not destroy sandbox GCP resources on completion/failure. Useful for debugging active instances.
*   `--reuse-sandbox`: Reuse existing local workspace and GCP sandbox resources if they exist. Requires passing a persistent, custom `--instance-name` (e.g. `--instance-name itest-9611`) and having run with `--keep-sandbox` in the previous run.
*   `--tf-git-ref`: Git reference branch/tag/commit for the GCP Terraform templates repository (default: `main`).
*   `--dcp-version`: Override default DCP version (controls all images and templates) (default: `latest`).


### E2E Verification Stages & Philosophy

Once the GCP sandbox stack is up and seeded with dataset MCFs, the script triggers the entire API verification suite concurrently. This validates three core capabilities of the deployed Data Commons Platform backend:

*   **Stage A: V2 Observations & Custom Data Retrieval**
    *   *Philosophy:* Validates E2E query routing and data loading for custom variables. It asserts observations values on custom seeded OECD wages metrics to verify local database mapping, loading, and seeding.
*   **Stage B: V2 Embeddings & Natural Language Resolution**
    *   *Philosophy:* Validates custom search index and embeddings generation. This checks that the Ingestion Helper successfully generated vector coordinates from custom MCFs, loaded them into Spanner, and that the Resolver can map natural language queries (like "wages") back to these custom database entities.



