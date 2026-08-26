# Local Emulated Integration Testing Stack

This directory contains the Docker Compose environment and orchestrator for running hermetic, offline integration tests for the **Data Commons Platform (DCP)**.

It boots emulated service containers to verify compatibility across Spanner database schemas, the ingestion pipeline, the website & Mixer serving backend, and semantic query APIs without requiring live Google Cloud resources.

---

## 🏛️ Architecture Overview

The emulated stack runs the following containers in a shared bridge network (`itest-net`):

| Service | Image & Port | Description |
| :--- | :--- | :--- |
| **`spanner`** | `us-docker.pkg.dev/spanner-omni/images/spanner-omni:2026.r1-beta.2`<br>`9010` (gRPC), `9020` (REST) | In-memory Google Cloud Spanner emulator with Graph schema support. |
| **`gcs`** | `fsouza/fake-gcs-server:1.47.8`<br>`9099` (HTTP) | Local Google Cloud Storage mock emulator. |
| **`ingestion-helper`** | `gcr.io/datcom-ci/datacommons-ingestion-helper:latest`<br>`8081` (HTTP) | Database migrations (`/database/initialize`) & base ontology seeding (`/database/seed`). |
| **`datacommons-data-processor`** | `gcr.io/datcom-ci/datacommons-data:latest`<br>*(CLI task)* | Statistical MCF/CSV parser converting raw datasets into JSON-LD graph nodes. |
| **`dataflow-ingestion`** | `us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion:latest`<br>*(CLI task)* | Java Apache Beam `GraphIngestionPipeline` loading JSON-LD graph mutations into Spanner. |
| **`website` (Mixer)** | `gcr.io/datcom-ci/datacommons-services:latest`<br>`8082` (HTTP) | Combined Data Commons Website frontend and Mixer serving backend. |

---

## 🚀 Running Integration Tests Locally

To run the complete integration test suite against the local emulated stack:

```bash
uv run pytest tests/integration/suites/ \
  --instance=local \
  --test-config=foobar_wages
```

### ⚡ Fast Developer Loop (`--reuse-data`)

By default, the testing framework starts the container stack, initializes the schema, loads the dataset, and tears down the containers after the test run.

To keep the containers alive and run tests in **~1 second**:

```bash
uv run pytest tests/integration/suites/ \
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

To test against specific release candidate images, pinned version tags, or locally built images:

```bash
DATAFLOW_IMAGE=us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion:v1.2.0 \
PROCESSOR_IMAGE=gcr.io/datcom-ci/datacommons-data:v1.2.0 \
HELPER_IMAGE=gcr.io/datcom-ci/datacommons-ingestion-helper:v1.2.0 \
SERVICES_IMAGE=gcr.io/datcom-ci/datacommons-services:v1.2.0 \
uv run pytest tests/integration/suites/ \
  --instance=local \
  --test-config=foobar_wages
```

> **TODO (Follow-Up)**: Support direct live mounting and substitution of local source code directories (`website/`, `mixer/`, `import/`) without needing pre-built container images (see [Roadmap](#-roadmap--follow-ups-local-code-substitution) below).

---

## 🔍 Debugging & Inspecting Services

When running with warm containers (`--reuse-data`), you can inspect services directly on host ports:

* **Website / Mixer Serving API**: `http://localhost:8082/healthz`
* **Ingestion Helper**: `http://localhost:8081/docs`
* **Spanner Emulator**: `localhost:9010` (gRPC) / `localhost:9020` (REST)
* **GCS Emulator**: `http://localhost:9099/storage/v1/b`

To manually stop the emulated container stack:
```bash
docker compose -f tests/integration/emulated/docker-compose.yml down -v
```

---

## 🔮 Roadmap & Follow-Ups: Local Code Substitution

In an upcoming follow-up, the test runner will support substituting container images with **local repository source trees** for rapid cross-repository development:

| Component | Target Repo | Planned Substitution Mechanism |
| :--- | :--- | :--- |
| **Website & Flask** | `../website` | Live source volume mount into `website` container (`/workspace/server`) |
| **Mixer Serving Backend** | `../mixer` | Local Go binary mount into `website` container (`/workspace/mixer`) |
| **Data Processor** | `../import/simple` | Live source volume mount into `datacommons-data-processor` |
| **Beam Graph Pipeline** | `../import` | Local Java JAR DirectRunner mount into `dataflow-ingestion` |

This will enable testing PR branches across sibling repositories against the end-to-end integration suite without waiting for remote CI container builds.
