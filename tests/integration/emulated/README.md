# Local Emulated Integration Testing Stack

This directory contains the Docker Compose environment and orchestrator for running hermetic, offline integration tests for the **Data Commons Platform (DCP)**.

It boots emulated service containers to verify compatibility across Spanner database schemas, the ingestion helper service, the website & Mixer serving backend, and semantic query APIs without requiring live Google Cloud resources.

---

## 🏛️ Architecture Overview

The emulated stack runs the following containers in a shared bridge network (`itest-net`):

| Container Service | Image / Port | Description |
| :--- | :--- | :--- |
| **`spanner`** | `gcr.io/cloud-spanner-emulator/emulator` (`9010` gRPC, `9020` REST) | In-memory Google Cloud Spanner emulator. |
| **`gcs`** | `fsouza/fake-gcs-server` (`9099` HTTP) | Local Google Cloud Storage mock emulator. |
| **`ingestion-helper`** | `gcr.io/datcom-ci/datacommons-ingestion-helper:latest` (`8081` HTTP) | Database migrations (`/database/initialize`) & base ontology seeding (`/database/seed`). |
| **`website` (Mixer)** | `gcr.io/datcom-ci/datacommons-services:latest` (`8082` HTTP) | Combined Data Commons Website frontend and Mixer gRPC/REST serving backend. |
| **`mock-nl-server`** | `python:3.11-slim` (`6060` HTTP) | Fast zero-dependency mock embeddings & NL search server. |

---

## 🚀 Running Integration Tests Locally

To run the serving API integration tests against the local emulated stack:

```bash
uv run pytest tests/integration/suites/03_serving_api/ \
  --instance=local \
  --test-config=foobar_wages
```

### ⚡ Fast Developer Loop (`--reuse-data`)

By default, the testing framework starts the container stack, initializes the schema, loads the dataset, and tears down the containers after the test run.

To keep the containers alive and run tests in **~2 seconds**:

```bash
uv run pytest tests/integration/suites/03_serving_api/ \
  --instance=local \
  --test-config=foobar_wages \
  --reuse-data
```

When `--reuse-data` is specified:
1. It checks if the website backend is already healthy at `http://localhost:8082/healthz`.
2. If healthy, it skips Docker Compose bootstrap and database migrations, executing tests immediately.
3. It leaves the stack running for rapid test re-runs.

---

## 🔧 Overriding Container Images

To test against specific release candidate images or pinned version tags:

```bash
HELPER_IMAGE=gcr.io/datcom-ci/datacommons-ingestion-helper:v1.2.0 \
SERVICES_IMAGE=gcr.io/datcom-ci/datacommons-services:v1.2.0 \
uv run pytest tests/integration/suites/03_serving_api/ \
  --instance=local \
  --test-config=foobar_wages
```

---

## 🚩 Feature Flags Configuration

Mixer feature flags are configured declaratively in [`config/feature_flags.yaml`](./config/feature_flags.yaml) and mounted directly into the `website` container at `/workspace/deploy/featureflags/dcp.yaml:ro`.

This ensures multi-entity schema support (`enable_multi_entity_schema: true`) and custom topic resolution are active by default during local test runs.

---

## 🔍 Debugging & Inspecting Services

When running with warm containers (`--reuse-data`), you can inspect services directly on host ports:

* **Website / Mixer Serving API**: `http://localhost:8082/healthz`
* **Ingestion Helper**: `http://localhost:8081/healthz`
* **Spanner Emulator**: `localhost:9010` (gRPC) / `localhost:9020` (REST)
* **GCS Emulator**: `http://localhost:9099/storage/v1/b`
* **Mock NL Server**: `http://localhost:6060/healthz`

To manually stop the emulated container stack:
```bash
docker compose -f tests/integration/emulated/docker-compose.yml down -v
```
