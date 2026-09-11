# Data Commons Platform Architecture and Data Flows

## Overview

The Data Commons Platform (DCP) enables organizations to deploy, manage, and serve private statistical knowledge graphs alongside the public Google Data Commons graph. DCP pairs a scalable batch ingestion pipeline with a low-latency serving layer deployed on Google Cloud Platform (GCP).

This document outlines the system topology across the four core repositories, maps container artifacts to GCP compute targets, and traces end-to-end data flows for ingestion and serving.

---

## 1. Multi-Repository Topology

The architecture organizes responsibilities hierarchically across four repositories:
* **Orchestration Layer (`datacommons`)**: Deploys declarative cloud infrastructure and coordinates migrations.
* **Serving Layer (`mixer` and `website`)**: Mixer queries backend storage and Base Data Commons; Website serves the frontend UI and proxies requests.
* **Ingestion Layer (`import`)**: Transforms, validates, and commits batch graph mutations into Cloud Spanner.

### 1. [datacommonsorg/datacommons](../../)
The platform hub and orchestration repository.
* **[infra/dcp/](../../infra/dcp)**: Declarative Terraform configurations and reusable modules for Cloud Spanner, Cloud Run, Google Cloud Storage (GCS), Cloud Workflows, Secret Manager, and VPC networking.
* **[packages/datacommons-cli/](../../packages/datacommons-cli)**: Lightweight entrypoint wrapper for the `datacommons` CLI distribution.
* **[packages/datacommons-admin/](../../packages/datacommons-admin)**: Python administration package implementing deployment scaffolding, Spanner database schema migrations, and ingestion trigger commands.
* **[packages/datacommons-db/](../../packages/datacommons-db)**: Database access layer containing SQLAlchemy models, Cloud Spanner clients, and versioned schema migration DDL scripts.
* **[tests/integration/](../../tests/integration)**: Hermetic integration test suite using Docker Compose to emulate Spanner, Cloud Storage, and serving containers.

### 2. [datacommonsorg/mixer](https://github.com/datacommonsorg/mixer)
The high-performance data serving backend written in Go.
* **`proto/`**: Protocol Buffer definitions (`v1/`, `v2/`, `v3/`) specifying gRPC and REST APIs for observation queries, entity resolution, and node navigation.
* **`internal/server/dispatcher/`**: Middleware layer managing request routing, caching, entity expansion, and formula evaluation.
* **`internal/server/datasources/`**: Query facade executing concurrent scatter-gather queries across local Cloud Spanner databases, Redis caches, and remote base Data Commons endpoints.
* **`internal/server/spanner/`**: Spanner SQL and Graph Query Language (GQL) generators implementing read staleness guarantees tied to ingestion timestamps.

### 3. [datacommonsorg/website](https://github.com/datacommonsorg/website)
The web application and serving entrypoint.
* **`server/`**: Python Flask controllers routing web requests, managing natural language explore endpoints (`/api/explore/detect-and-fulfill`), and proxying API traffic.
* **`static/`**: React and TypeScript browser interface containing data visualizers, map renderers, and statistical charting components.
* **`build/cdc_services/`**: Container packaging files (`Dockerfile`, `run.sh`, `nginx.conf`) combining Envoy, Mixer, and Website into a unified serving artifact (`datacommons-services`).
* **`build/cdc_data/`**: Container build files packaging the data preprocessor into `datacommons-data`.

### 4. [datacommonsorg/import](https://github.com/datacommonsorg/import)
The data transformation and batch ingestion engine.
* **`simple/`**: Python data preprocessor (`import/simple`), packaged into `datacommons-data` and executed with `--mode=dcpbridge`.
* **`pipeline/ingestion/`**: Apache Beam Java Dataflow pipeline (`GraphIngestionPipeline`) that validates graph entities, computes FarmHash facet IDs, and commits mutations to Cloud Spanner.
* **`pipeline/workflow/aggregation-helper/`**: Postprocessing Cloud Run job executing BigQuery federated SQL queries to aggregate statistical hierarchies and edge relationships.
* **`pipeline/workflow/ingestion-helper/`**: FastAPI Cloud Run microservice managing database concurrency locks, ingestion status updates, and Vertex AI text embeddings.

---

## 2. Container Images and GCP Compute Topology

DCP packages services into container images hosted on Google Cloud Artifact Registry or Container Registry (`gcr.io/datcom-ci/`).

| Image Name | Source Repository | Compute Target | Role in Platform |
| :--- | :--- | :--- | :--- |
| **`datacommons-services`** | `website` (submodules `mixer`) | Cloud Run Service | Unified serving container. Hosts Nginx/Envoy, the Go Mixer gRPC server, and the Flask/React frontend. |
| **`datacommons-data`** | `website` + `import/simple` | Cloud Run Job | Data preprocessor. Runs `stats.main --mode=dcpbridge` to parse CSV and MCF files into JSON-LD chunks. |
| **`ingestion-flex`** | `import/pipeline/ingestion` | Cloud Dataflow | Apache Beam Java Flex Template (`GraphIngestionPipeline`). Ingests graph nodes and observations into Cloud Spanner. |
| **`datacommons-aggregation-helper`** | `import/pipeline/workflow` | Cloud Run Job | Postprocessing engine. Uses BigQuery federated queries to materialize `STAT_VAR_GROUPS`, `LINKED_EDGES`, and summary tables. |
| **`datacommons-ingestion-helper`** | `import/pipeline/workflow` | Cloud Run Service | Operational coordinator. Provides REST endpoints for Spanner table locks, metadata history, and Vertex AI embeddings. |

---

## 3. End-to-End Ingestion Flow

Batch ingestion loads raw data from Cloud Storage into Cloud Spanner across a 5-stage pipeline orchestrated by Google Cloud Workflows ([workflow.yaml](../../infra/dcp/modules/ingestion/workflow/workflow.yaml)):

1. **Preprocessing**: Cloud Workflows launches Cloud Run job `datacommons-data`, executing `stats.main --mode=dcpbridge` against `gs://<storage_bucket>/<ingestion_input_path>/<dataset>/`. The job validates CSV headers against `config.json`, outputs partitioned JSON-LD shards, and writes a handshake file (`tempLocation/datacommons/ingestion_records/<workflow_id>.json`).
2. **Locking**: The workflow calls `POST /database/lock/acquire` on `datacommons-ingestion-helper` (retrying on HTTP 503 up to a configurable timeout) and records an `IngestionHistory` entry with status `PENDING`.
3. **Dataflow Ingestion**: Launches the Apache Beam Java pipeline (`GraphIngestionPipeline`) on Dataflow. Dataflow deletes outdated records for replaced imports, computes 64-bit FarmHash facet identifiers, generates search columns, and streams batched mutations into Spanner tables (`Node`, `Edge`, `Observation`, `TimeSeries`).
4. **Parallel Postprocessing & Embeddings**: Executes concurrently:
   * **Aggregation Helper**: Cloud Run job querying Spanner via BigQuery external connections to materialize `STAT_VAR_GROUPS`, `LINKED_EDGES`, and `ProvenanceSummary`.
   * **Vertex AI Embeddings**: `POST /embeddings/ingest` on `ingestion-helper` computes vector representations for new statistical variables and entities, writing them to Spanner for natural language search.
5. **Finalization and Cache Busting**: Updates `IngestionHistory` to `SUCCESS`, releases the Spanner lock (`POST /database/lock/release`), flushes Redis (`POST /cache/clear`), and (if `skip_container_restarts = false`) patches `datacommons-services` with an updated timestamp label to trigger rolling container updates.

#### Failure Handling and Lock Release Guarantee
If Dataflow or postprocessing throws an unhandled exception:
* Cloud Workflows intercepts the error in its global `try/retry/except` block ([workflow.yaml](../../infra/dcp/modules/ingestion/workflow/workflow.yaml)).
* It logs the failure status (`FAILURE` or `RETRY`) into `IngestionHistory`.
* The workflow **always executes `release_lock_step`** (`POST /database/lock/release`) before exiting, ensuring the Spanner lock is never orphaned and subsequent ingestion runs are not blocked.

---

## 4. End-to-End Serving Flow

The serving stack handles incoming data queries from web browsers, REST API clients, SDMX 3.0 consumers, and Model Context Protocol (MCP) agents through a structured four-stage request and response lifecycle:

* **Client Layer**: External clients (browsers, cURL, SDMX clients, or AI agents) submit HTTPS requests to the Cloud Run serving endpoint.
* **Proxy and Routing (Nginx / Envoy)**: Listens on port 8081 inside the `datacommons-services` container, transcodes HTTP/JSON requests into binary gRPC using API definitions, and routes static web requests to Flask.
* **Serving Backend (Go Mixer)**: Evaluates query parameters, checks Redis and in-memory caches, and coordinates scatter-gather lookups across backend data sources.
* **Data Sources (Spanner & Base DC)**: Executes timestamp-pinned reads against the private Cloud Spanner database and falls back to Base Data Commons for public global entities and variables.

### 1. Request Ingestion and Transcoding
* Clients submit HTTP requests to endpoints such as `/core/api/v2/observation`, `/core/api/v2/resolve`, or `/api/explore/detect-and-fulfill`.
* Nginx and Envoy receive incoming traffic on port 8081.
* Using Google API HTTP annotations (`endpoints.yaml`), Envoy transcodes HTTP/JSON request payloads into Protobuf messages and routes them to Mixer via internal gRPC.

### 2. Mixer Dispatcher and Scatter-Gather Facade
* Mixer's dispatcher processes incoming gRPC requests.
* Mixer inspects the in-memory cache and Redis instance for matching query results.
* If cache misses occur, Mixer initiates concurrent lookups through its data sources facade:
  * **Private Graph Query**: Formulates SQL or GQL queries against the private Cloud Spanner database.
  * **Base Data Commons Query**: Formulates remote gRPC calls to `api.datacommons.org` to retrieve public variables or parent geographic entities.

### 3. Spanner Transactional Read Staleness
* To maintain consistency during background data loads, Mixer does not query the Spanner database head directly.
* Instead, Mixer queries `IngestionHistory` to retrieve the completion timestamp of the latest successful ingestion run.
* Mixer executes all Spanner queries using exact timestamp-bound reads pinned to that completion timestamp.
* This read-staleness model guarantees that active user queries never observe partial, uncommitted, or corrupt data while an ingestion pipeline is mutating tables.
* **Fresh Deployment Fallback**: On newly provisioned instances with an empty `IngestionHistory` table, Mixer defaults to bounded staleness (15 seconds) against head until the first ingestion successfully commits.

### 4. Response Composition
* Mixer merges data points from the private Spanner graph with responses from base Data Commons.
* Private data takes precedence: if an entity-variable pair exists locally, Mixer serves the private observation.
* Mixer streams the unified Protobuf response back to Envoy.
* Envoy transcodes the binary Protobuf message into JSON and returns the HTTP response to the caller.
