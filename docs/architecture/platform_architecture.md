# Data Commons Platform Architecture and Data Flows

## Overview

The Data Commons Platform (DCP) enables organizations to deploy, manage, and serve private statistical knowledge graphs alongside the public Google Data Commons graph. DCP pairs a scalable batch ingestion pipeline with a low-latency serving layer deployed on Google Cloud Platform (GCP).

This document outlines the system topology across the four core repositories, maps container artifacts to GCP compute targets, and traces the complete end-to-end data flows for ingestion and serving.

---

## 1. Multi-Repository Topology

The Data Commons codebase spans four core GitHub repositories under the `datacommonsorg` organization. Each repository owns a dedicated layer of the platform stack.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        datacommonsorg/datacommons                      │
│   Infrastructure (Terraform), Admin CLI, DB Schemas, Integration Tests │
└──────────────┬─────────────────────────┬───────────────────────────────┘
               │                         │
               ▼                         ▼
┌──────────────────────────────┐  ┌──────────────────────────────────────┐
│     datacommonsorg/mixer     │  │       datacommonsorg/website         │
│ Go gRPC API & Query Engine   │  │ Frontend UI & Flask Transcoding      │
└──────────────┬───────────────┘  └──────┬───────────────────────────────┘
               │                         │
               └───────────┬─────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         datacommonsorg/import                          │
│   Dataflow (Java Beam), Data Preprocessor, Aggregation & Helper Jobs   │
└────────────────────────────────────────────────────────────────────────┘
```

### 1. `datacommons` (`datacommonsorg/datacommons`)
The platform hub and orchestration repository.
* **`infra/dcp/`**: Declarative Terraform configurations and reusable modules for Cloud Spanner, Cloud Run, Google Cloud Storage (GCS), Cloud Workflows, Secret Manager, and VPC networking.
* **`packages/datacommons-cli/`**: Lightweight entrypoint wrapper for the `datacommons` CLI distribution.
* **`packages/datacommons-admin/`**: Python administration package implementing deployment scaffolding, Spanner database schema migrations, and ingestion trigger commands.
* **`packages/datacommons-db/`**: Database access layer containing SQLAlchemy models, Cloud Spanner clients, and versioned schema migration DDL scripts.
* **`tests/integration/`**: Hermetic integration test suite utilizing Docker Compose to emulate Spanner, Cloud Storage, and serving containers.

### 2. `mixer` (`datacommonsorg/mixer`)
The high-performance data serving backend written in Go.
* **`proto/`**: Protocol Buffer definitions (`v1/`, `v2/`, `v3/`) specifying gRPC and REST APIs for observation queries, entity resolution, and node navigation.
* **`internal/server/dispatcher/`**: Middleware layer managing request routing, caching, entity expansion, and formula evaluation.
* **`internal/server/datasources/`**: Query facade executing concurrent scatter-gather queries across local Cloud Spanner databases, Redis caches, and remote base Data Commons endpoints.
* **`internal/server/spanner/`**: Spanner SQL and Graph Query Language (GQL) generators implementing read staleness guarantees tied to ingestion timestamps.

### 3. `website` (`datacommonsorg/website`)
The web application and serving entrypoint.
* **`server/`**: Python Flask controllers routing web requests, managing natural language explore endpoints (`/api/explore/detect-and-fulfill`), and proxying API traffic.
* **`static/`**: React and TypeScript browser interface containing data visualizers, map renderers, and statistical charting components.
* **`build/cdc_services/`**: Container packaging files (`Dockerfile`, `run.sh`, `nginx.conf`) combining Envoy, Mixer, and Website into a unified serving artifact (`datacommons-services`).
* **`build/cdc_data/`**: Container build files packaging the data preprocessor into `datacommons-data`.

### 4. `import` (`datacommonsorg/import`)
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

Batch ingestion loads raw data from GCS into Cloud Spanner. Google Cloud Workflows orchestrates the entire sequence (`infra/dcp/modules/ingestion/workflow/workflow.yaml`).

```
                    ┌───────────────────────────────┐
                    │ Raw CSV / MCF in Cloud Storage│
                    └───────────────┬───────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│ Stage 1: Preprocessing (Cloud Run Job: datacommons-data)              │
│ - Validates schema and column mappings in config.json                  │
│ - Converts inputs to compact JSON-LD shards                           │
│ - Emits ingestion handshake metadata to GCS                           │
└───────────────────────────────────┬───────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│ Stage 2: Ingestion Lock (Cloud Run Service: ingestion-helper)        │
│ - Acquires exclusive Spanner ingestion lock (POST /database/lock)     │
│ - Sets IngestionHistory status to PENDING                             │
└───────────────────────────────────┬───────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│ Stage 3: Dataflow Execution (Apache Beam: GraphIngestionPipeline)     │
│ - Deletes outdated graph elements for registered import namespaces     │
│ - Computes FarmHash facet IDs and resolves generated columns          │
│ - Batches and writes mutations into Cloud Spanner tables              │
└───────────────────────────────────┬───────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│ Stage 4: Parallel Postprocessing & Embeddings                         │
│ ┌──────────────────────────────────┐ ┌──────────────────────────────┐ │
│ │ Aggregation Helper (Cloud Run)   │ │ Ingestion Helper (Cloud Run) │ │
│ │ - BigQuery federated queries     │ │ - Calls Vertex AI API        │ │
│ │ - Generates STAT_VAR_GROUPS      │ │ - Produces vector embeddings │ │
│ │ - Computes LINKED_EDGES          │ │ - Writes to Spanner vectors  │ │
│ └──────────────────────────────────┘ └──────────────────────────────┘ │
└───────────────────────────────────┬───────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│ Stage 5: Promotion, Cache Invalidation, and Restart                   │
│ - Updates IngestionHistory status to SUCCESS                          │
│ - Releases Spanner database lock                                      │
│ - Flushes Redis cache (POST /cache/clear)                             │
│ - Restarts datacommons-services Cloud Run service via label patch     │
└───────────────────────────────────────────────────────────────────────┘
```

### Stage 1: Preprocessing
* Cloud Workflows launches the `datacommons-data` Cloud Run job.
* The preprocessor executes `stats.main --mode=dcpbridge` against raw input files in `gs://<storage_bucket>/<ingestion_input_path>/<dataset>/`.
* The preprocessor validates column headers against `config.json` mappings and provenance MCF declarations.
* The job outputs partitioned JSON-LD shards to a temporary staging bucket and writes a handshake file (`tempLocation/datacommons/ingestion_records/<workflow_id>.json`).
* The handshake file identifies generated import names, provenance IDs, and flags whether stat var groups require regeneration.

### Stage 2: Ingestion Locking
* Cloud Workflows reads the handshake JSON file from GCS.
* The workflow calls `POST /database/lock/acquire` on `datacommons-ingestion-helper`.
* If another ingestion holds the lock, the workflow backs off and polls for up to the configured lock acquisition timeout.
* Once the lock is acquired, the helper creates an entry in the `IngestionHistory` table with status `PENDING`.

### Stage 3: Dataflow Graph Ingestion
* Cloud Workflows launches the Apache Beam Flex Template on Cloud Dataflow (`GraphIngestionPipeline`).
* Dataflow executes partitioned DML deletes to remove outdated graph records for the specific import names being replaced.
* Dataflow reads the staged JSON-LD shards, collapses duplicate schema nodes, computes 64-bit FarmHash facet identifiers, and generates `entity1` search columns.
* Dataflow streams batched mutations into Cloud Spanner tables: `Node`, `Edge`, `Observation`, and `TimeSeries`.
* Cloud Workflows polls Dataflow until the job transitions to `JOB_STATE_DONE`.

### Stage 4: Parallel Postprocessing and Embeddings
Once Dataflow completes, Cloud Workflows executes two operations in parallel:
1. **Aggregation Helper (`datacommons-aggregation-helper`)**:
   * Launches a Cloud Run job that queries Spanner data via BigQuery external data connections.
   * Materializes statistical variable hierarchies into `STAT_VAR_GROUPS`.
   * Maps graph connections into `LINKED_EDGES`.
   * Builds dataset provenance records into `ProvenanceSummary`.
2. **Text Embeddings Generation (`datacommons-ingestion-helper`)**:
   * Calls `POST /embeddings/ingest`.
   * Identifies newly added statistical variables and entities.
   * Calls Google Cloud Vertex AI text embedding models to generate vector representations.
   * Writes the resulting embeddings into Spanner to enable natural language entity resolution.

### Stage 5: Finalization and Cache Busting
* Cloud Workflows updates `IngestionHistory` to `SUCCESS` and records the completion timestamp.
* The workflow calls `POST /database/lock/release` on the ingestion helper.
* If Redis is enabled, the workflow calls `POST /cache/clear` to flush stale cached queries.
* If automatic service restarts are enabled, the workflow patches the `datacommons-services` Cloud Run service with a new label (`restarted-at: <timestamp>`). This forces a rolling container deployment, ensuring newly launched serving containers mount the fresh graph metadata immediately.

---

## 4. End-to-End Serving Flow

The serving stack handles incoming data queries from web browsers, REST API clients, SDMX 3.0 consumers, and Model Context Protocol (MCP) agents.

```
 Client (Web Browser, Curl, SDMX Client, MCP Agent)
                      │
                      │ HTTPS Request
                      ▼
┌──────────────────────────────────────────────────────────────┐
│ datacommons-services Container (Cloud Run)                   │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Nginx / Envoy Proxy (Port 8081)                         │  │
│  │ - Transcodes HTTP/JSON requests into binary gRPC       │  │
│  │ - Routes static assets and Flask web routes            │  │
│  └──────────────────────────┬─────────────────────────────┘  │
│                             │                                │
│                             ▼ gRPC                           │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Mixer Serving Engine (Go gRPC Server)                  │  │
│  │                                                        │  │
│  │  ┌──────────────────────────────────────────────────┐  │  │
│  │  │ Dispatcher & Middleware                          │  │  │
│  │  │ - Evaluates query parameters                     │  │  │
│  │  │ - Checks Redis cache for precomputed hits        │  │  │
│  │  │ - Determines entity expansions                   │  │  │
│  │  └───────────────┬──────────────────┬───────────────┘  │  │
│  └──────────────────┼──────────────────┼──────────────────┘  │
└─────────────────────┼──────────────────┼─────────────────────┘
                      │                  │
                      ▼ SQL / GQL        ▼ Remote gRPC
┌───────────────────────────────┐ ┌────────────────────────────┐
│ Cloud Spanner Database        │ │ Base Data Commons          │
│ - Reads pinned to latest      │ │ - Public knowledge graph   │
│   promoted ingestion timestamp│ │   fallback                 │
│ - Queries Node, Edge, Obs     │ │ - Resolves global DCIDs    │
└───────────────────────────────┘ └────────────────────────────┘
```

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

### 4. Response Composition
* Mixer merges data points from the private Spanner graph with responses from base Data Commons.
* Private data takes precedence: if an entity-variable pair exists locally, Mixer serves the private observation.
* Mixer streams the unified Protobuf response back to Envoy.
* Envoy transcodes the binary Protobuf message into JSON and returns the HTTP response to the caller.
