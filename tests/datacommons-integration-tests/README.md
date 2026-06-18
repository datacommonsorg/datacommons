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

Local integration tests run with the Spanner multi-entity schema enabled by default in the Mixer backend. This is controlled by mounting [custom_feature_flags.yaml](file:///usr/local/google/home/yiyuanc/datacommons/tests/datacommons-integration-tests/custom_feature_flags.yaml) inside the `website` container at `/workspace/deploy/featureflags/custom.yaml`.

The container entrypoint detects the environment variable `RESOLVE_WITH_SPANNER_EMBEDDINGS=true` (defined in `docker-compose.test.yml`) and starts Mixer using these flags.

You can modify the flags inside `custom_feature_flags.yaml` if you need to tweak the Mixer server configuration for local debugging.

---

## GCP Sandbox Integration Tests

In addition to local emulated tests, this package includes a script to run automated, end-to-end integration tests on **real GCP sandbox resources**. This validates Terraform scaffolding, GCS transfers, Spanner database seeding, Cloud Workflow executions, and Cloud Run web server APIs.

### Running the GCP Tests

To run the GCP integration test suite (requires authenticated GCP CLI access):
```bash
python3 tests/datacommons-integration-tests/run_gcp_integration_test.py \
    --project-id <YOUR_GCP_PROJECT_ID> \
    --dc-api-key "YOUR_GOOGLE_DATA_COMMONS_API_KEY"
```

Alternatively, you can pass the API key via an environment variable:
```bash
DC_API_KEY="YOUR_API_KEY" python3 tests/datacommons-integration-tests/run_gcp_integration_test.py \
    --project-id <YOUR_GCP_PROJECT_ID>
```

### Script Arguments

*   `--project-id`: The Google Cloud Project ID where the sandbox resources should be provisioned (default: `datcom-ci`).
*   `--dc-api-key`: Google Data Commons API Key needed to authenticate and configure sandbox clients.
*   `--region`: The GCP region to deploy resources (default: `us-central1`).
*   `--namespace`: Custom naming namespace for resources (default: randomized `itest-XXXX`).
*   `--keep-sandbox`: Do not destroy sandbox GCP resources on completion/failure. Useful for debugging active instances.
*   `--reuse-sandbox`: Reuse existing local workspace and GCP sandbox resources if they exist. Requires passing a persistent, custom `--namespace` (e.g. `--namespace itest-9611`) and having run with `--keep-sandbox` in the previous run.
*   `--tf-git-ref`: Git reference branch/tag/commit for the GCP Terraform templates repository (default: `main`).
*   `--services-image`, `--preprocessing-image`, `--helper-image`: Override container image tags deployed during provisioning.


