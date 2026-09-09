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

## ⚠️ Features Not Supported in Hermetic Emulated Mode

The emulated stack validates core database schemas, DirectRunner graph ingestion, and serving APIs offline. Certain cloud-managed features require live GCP services and are marked with `@pytest.mark.cloud_only` (skipped automatically when running with `--instance=emulated`):

* **Cloud CLI Ingestion (`TestCLIIngestion`)**: The `datacommons admin ingest start` command invokes GCP Cloud Workflows and monitors Dataflow jobs via Cloud APIs. In emulated mode, data is ingested directly into the Spanner emulator via Beam DirectRunner.
* **SVG Hierarchy Aggregations (`TestSVGHierarchy`)**: Statistical Variable Group (SVG) parent-child specialization generation relies on BigQuery postprocessing aggregations.
* **Vector Embeddings & Semantic Search (`TestEmbeddings`, `TestMCPTools::search_indicators`)**: Generating embeddings and resolving natural language indicator queries requires Vertex AI Vector Search.

---

## 🚀 Running Integration Tests Locally

To run the integration test suite against the local emulated stack for a single dataset (`foobar_wages`):

```bash
uv run pytest tests/integration/suites/ \
  --instance=emulated \
  --test-config=foobar_wages
```

To run **multiple datasets** (e.g., both single-entity `foobar_wages` and multi-entity `health_aid`):

```bash
uv run pytest tests/integration/suites/ \
  --instance=emulated \
  --test-config=foobar_wages,health_aid
```

### ⚡ Fast Developer Loop (`--reuse-data`)

By default, the testing framework starts the container stack, initializes the schema, loads the dataset, and tears down the containers after the test run.

To keep the containers alive and run tests in **~1 second**:

```bash
uv run pytest tests/integration/suites/ \
  --instance=emulated \
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
  --instance=emulated \
  --test-config=foobar_wages
```

> **TODO (Follow-Up)**: Support direct live mounting and substitution of local source code directories (`website/`, `mixer/`, `import/`) without needing pre-built container images.

## ☁️ CI Automation: GitHub Actions vs. Google Cloud Build

The hermetic emulated stack can be executed in CI via two complementary mechanisms:

### 1. GitHub Actions Workflow (`.github/workflows/ci.yaml`)
* **Trigger**: Runs automatically on every Pull Request (`hermetic-integration-test` job).
* **Execution**: Spins up the Docker Compose stack directly on the GitHub-hosted Ubuntu runner (`ubuntu-latest`) and executes `run_e2e_tests.py --instance=emulated --test-config=foobar_wages`.
* **Note on Permissions**: GitHub security policy restricts OAuth applications (including automated bots/agents) from modifying `.github/workflows/*.yaml` unless granted explicit `workflow` token permissions. Updating the dataset list in `.github/workflows/ci.yaml` must be pushed by a human maintainer or via the GitHub UI.

### 2. Google Cloud Build (`cloudbuild_emulated_test.yaml`)
* **Trigger**: On-demand CLI submission or automated release pipelines in GCP.
* **Execution**: Runs on high-CPU GCP Cloud Build workers (`E2_HIGHCPU_8`), pre-pulls all container images in parallel, and executes:
  ```bash
  uv run pytest -s tests/integration/suites/ --instance=local --test-config=foobar_wages,health_aid
  ```

To submit a hermetic run to Cloud Build manually:

```bash
gcloud builds submit \
  --project=datcom-ci \
  --config=tests/integration/emulated/cloudbuild_emulated_test.yaml \
  .
```

To test specific container image tags via Cloud Build substitutions:

```bash
gcloud builds submit \
  --project=datcom-ci \
  --config=tests/integration/emulated/cloudbuild_emulated_test.yaml \
  --substitutions=_SERVICES_IMAGE="gcr.io/datcom-ci/datacommons-services:v1.2.0",_HELPER_IMAGE="gcr.io/datcom-ci/datacommons-ingestion-helper:v1.2.0" \
  .
```

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


