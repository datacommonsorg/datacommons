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
