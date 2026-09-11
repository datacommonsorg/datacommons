# Data Commons Platform Architecture and Data Flows

## Overview

The Data Commons Platform (DCP) enables organizations to deploy, manage, and serve private statistical knowledge graphs alongside the public Google Data Commons graph. DCP pairs a scalable batch ingestion pipeline with a low-latency serving layer deployed on Google Cloud Platform (GCP).

This document outlines the system topology across the four core repositories, maps container artifacts to GCP compute targets, and traces end-to-end data flows for ingestion and serving.

* **Looking for Terraform module hierarchy and variable plumbing?** Read [Terraform Stack Architecture](terraform_stack.md).
* **Looking for Admin CLI internals and scaffolding contracts?** Read [Admin CLI Architecture](admin_cli.md).

---

## Core Subsystems and Architecture

At a high level, DCP is made up of three core subsystems working together:

### Managing the Instance (Terraform and the Admin CLI)
* **Setting up cloud resources**: Terraform scripts in `infra/dcp/` create everything the platform needs in Google Cloud, including Cloud Spanner for data storage, Cloud Run for running services, and Cloud Workflows for coordination.
* **Running the platform**: The `datacommons admin` CLI makes daily operations straightforward. It helps developers set up new deployment folders, prepare databases, run schema migrations, and trigger data imports.
* **Automatic connection**: The CLI reads Terraform deployment outputs directly, so it automatically discovers database names, bucket URLs, and service endpoints without requiring manual configuration.

### Importing Data (The Ingestion Pipeline)
* **From files to the graph**: Converts custom CSV spreadsheets and schema definitions (MCF files) into structured knowledge graph data loaded into Cloud Spanner.
* **Automated steps**: Google Cloud Workflows orchestrates the entire import: parsing data with `datacommons-data`, running large-scale distributed loading on Cloud Dataflow, generating topic hierarchies and provenance summaries via BigQuery postprocessing, and building search embeddings using Vertex AI.
* **Safe loading**: An ingestion lock prevents two imports from colliding, ensuring data is written cleanly and safely.

### Serving Queries (The Web and API Stack)
* **All-in-one serving container**: A single Cloud Run service (`dc-datacommons-service`) running the `datacommons-services` image hosts the web frontend for interactive charts, REST and gRPC APIs for applications, and an MCP server for AI agents.
* **Combining private and public data**: When a user queries data, the backend (Mixer) checks your private Spanner database and the public Google Data Commons graph at the same time, merging the results into a single response. Your private data always takes priority.
* **Clean user experience**: While a background import is loading new data, users can continue browsing and querying charts without seeing partial or broken updates. Once the import completes, caches clear automatically so the newest data shows up right away.

---

## Multi-Repository Topology

The architecture organizes responsibilities hierarchically across four repositories:
* **Orchestration Layer (`datacommons`)**: Deploys declarative cloud infrastructure and coordinates migrations.
* **Serving Layer (`mixer` and `website`)**: Mixer queries backend storage and Base Data Commons; Website serves the frontend UI and proxies requests.
* **Ingestion Layer (`import`)**: Transforms, validates, and commits batch graph mutations into Cloud Spanner.

### [datacommonsorg/datacommons](https://github.com/datacommonsorg/datacommons)
The platform hub and orchestration repository.
* **[infra/dcp/](../../infra/dcp)**: Declarative Terraform configurations and reusable modules for Cloud Spanner, Cloud Run, Google Cloud Storage (GCS), Cloud Workflows, Secret Manager, and VPC networking.
* **[packages/datacommons-cli/](../../packages/datacommons-cli)**: Lightweight entrypoint wrapper for the `datacommons` CLI distribution.
* **[packages/datacommons-admin/](../../packages/datacommons-admin)**: Python administration package implementing deployment scaffolding, Spanner database schema migrations, and ingestion trigger commands.
* **[packages/datacommons-db/](../../packages/datacommons-db)**: Database access layer containing SQLAlchemy models, Cloud Spanner clients, and versioned schema migration DDL scripts.
* **[tests/integration/](../../tests/integration)**: Hermetic integration test suite using Docker Compose to emulate Spanner, Cloud Storage, and serving containers.

### [datacommonsorg/mixer](https://github.com/datacommonsorg/mixer)
The high-performance data serving backend written in Go.
* **`proto/`**: Protocol Buffer definitions (`v1/`, `v2/`, `v3/`) specifying gRPC and REST APIs for observation queries, entity resolution, and node navigation.
* **`internal/server/dispatcher/`**: Middleware layer managing request routing, caching, entity expansion, and formula evaluation.
* **`internal/server/datasources/`**: Query facade executing concurrent scatter-gather queries across local Cloud Spanner databases, Redis caches, and remote base Data Commons endpoints.
* **`internal/server/spanner/`**: Spanner SQL and Graph Query Language (GQL) generators implementing read staleness guarantees tied to ingestion timestamps.

### [datacommonsorg/website](https://github.com/datacommonsorg/website)
The web application and serving entrypoint.
* **`server/`**: Python Flask controllers routing web requests, managing natural language explore endpoints (`/api/explore/detect-and-fulfill`), and proxying API traffic.
* **`static/`**: React and TypeScript browser interface containing data visualizers, map renderers, and statistical charting components.
* **`build/cdc_services/`**: Container packaging files (`Dockerfile`, `run.sh`, `nginx.conf`) combining Envoy, Mixer, and Website into a unified serving artifact (`datacommons-services`).
* **`build/cdc_data/`**: Container build files packaging the data preprocessor into `datacommons-data`.

### [datacommonsorg/import](https://github.com/datacommonsorg/import)
The data transformation and batch ingestion engine.
* **`simple/`**: Python data preprocessor (`import/simple`), packaged into `datacommons-data` and executed with `--mode=dcpbridge`.
* **`pipeline/ingestion/`**: Apache Beam Java Dataflow pipeline (`GraphIngestionPipeline`) that validates graph entities, computes FarmHash facet IDs, and commits mutations to Cloud Spanner.
* **`pipeline/workflow/aggregation-helper/`**: Postprocessing Cloud Run job executing BigQuery federated SQL queries to aggregate statistical hierarchies and edge relationships.
* **`pipeline/workflow/ingestion-helper/`**: FastAPI Cloud Run microservice managing database concurrency locks, ingestion status updates, and Vertex AI text embeddings.

---

## Container Images and GCP Compute Topology

DCP packages services into container images hosted on Google Cloud Artifact Registry or Container Registry (`gcr.io/datcom-ci/`).

| Image Name | Source Repository | Compute Target | Role in Platform |
| :--- | :--- | :--- | :--- |
| **`datacommons-services`** | `website` (submodules `mixer`) | Cloud Run Service (`dc-datacommons-service`) | Unified serving container. Hosts Nginx ingress, Website Flask/React frontend, Envoy gRPC-JSON transcoder, and Go Mixer backend. |
| **`datacommons-data`** | `website` + `import/simple` | Cloud Run Job (`dc-ingestion-preprocessing-job`) | Data preprocessor. Runs `stats.main --mode=dcpbridge` to parse CSV and MCF files into JSON-LD chunks. |
| **`ingestion-flex`** | `import/pipeline/ingestion` | Cloud Dataflow | Apache Beam Java Flex Template (`GraphIngestionPipeline`). Ingests graph nodes and observations into Cloud Spanner. |
| **`datacommons-aggregation-helper`** | `import/pipeline/workflow` | Cloud Run Job (`dc-ingestion-postprocessing-job`) | Postprocessing engine. Uses BigQuery federated queries over Spanner to generate `STAT_VAR_GROUPS`, `LINKED_EDGES`, and `ProvenanceSummary`. |
| **`datacommons-ingestion-helper`** | `import/pipeline/workflow` | Cloud Run Service (`dc-ingestion-helper`) | Operational coordinator. Provides REST endpoints for Spanner table locks, metadata history, and Vertex AI embeddings. |

---

## End-to-End Ingestion Flow

Batch ingestion loads raw data from Cloud Storage into Cloud Spanner across a 5-stage pipeline orchestrated by Google Cloud Workflows ([workflow.yaml](../../infra/dcp/modules/ingestion/workflow/workflow.yaml)):

1. **Preprocessing**: Cloud Workflows launches the Cloud Run preprocessing job (`dc-ingestion-preprocessing-job`, running image `datacommons-data`), executing `stats.main --mode=dcpbridge` against input datasets. The job validates CSV headers against `config.json`, outputs partitioned JSON-LD shards, and writes a handshake file to `<tempLocation>/datacommons/ingestion_records/<workflow_id>.json`. The workflow reads this handshake blob to extract the sanitized `importList` and `generateStatVarGroups` flag before launching subsequent stages.
2. **Distributed Locking Protocol**: The workflow calls `POST /database/lock/acquire` on `dc-ingestion-helper`:
   * **Atomic Spanner Transaction**: The helper service executes a read-write transaction on the Spanner `IngestionLock` table (`LockName = 'global_ingestion_lock'`). It checks whether the lock is currently held.
   * **Contention and Backoff Retry Loop**: If another active run holds the lock, the endpoint returns HTTP 503. The workflow enters a retry loop (`increment_retries_and_wait`), sleeping for 120 seconds between attempts until acquired or reaching `max_lock_retries` (`lock_acquisition_timeout / 120`). The default `lock_acquisition_timeout` of 82,800 seconds (23 hours) defines the lock acquisition retry window, allowing sequential ingestion runs to queue safely behind active jobs.
   * **Ingestion History Record**: Once acquired, the workflow calls `POST /imports/ingestion-history` on `dc-ingestion-helper` to record an `IngestionHistory` entry with status `PENDING` and stage `dataflow`.
3. **Dataflow Ingestion**: Cloud Workflows updates `IngestionHistory` to status `RUNNING` (stage `dataflow`) and launches the Apache Beam Java pipeline (`GraphIngestionPipeline`) on Dataflow. Dataflow deletes outdated records for replaced imports, computes 64-bit FarmHash facet identifiers, generates search columns, and streams batched mutations into Spanner tables (`Node`, `Edge`, `Observation`, `TimeSeries`).
4. **Parallel Postprocessing and Embeddings**: Cloud Workflows updates `IngestionHistory` to status `RUNNING` (stage `postprocessing`) and executes two parallel branches:
   * **Aggregation Helper Job**: Launches Cloud Run job `dc-ingestion-postprocessing-job` (`datacommons-aggregation-helper`), executing BigQuery federated queries over Spanner to generate statistical variable hierarchies (`STAT_VAR_GROUPS` written to `Node` and `Edge`), graph relationships (`LINKED_EDGES` written to `Edge`), and dataset summaries (`ProvenanceSummary` written to `KeyValueStore`).
   * **Vertex AI Embeddings**: Calls `POST /embeddings/ingest` on `dc-ingestion-helper`, which executes Spanner `ML.PREDICT` against Vertex AI to compute vector representations for new statistical variables.
5. **Finalization, Cache Busting, and Rolling Restart**:
   * Updates `IngestionHistory` to status `SUCCESS` and stage `completed` via `POST /imports/ingestion-history`. This commit serves as the atomic version promotion watermark for downstream queries.
   * If `enable_redis_cache_clearing` is enabled, flushes the Redis query cache via `POST /cache/clear` on `dc-ingestion-helper`.
   * If `enable_datacommons_services_restart` is enabled, Cloud Workflows issues a patch call (`googleapis.run.v2.projects.locations.services.patch`) on `dc-datacommons-service` to update `template.labels.restarted-at`, triggering a zero-downtime rolling revision restart.
   * The workflow releases the distributed mutex by calling `POST /database/lock/release` on `dc-ingestion-helper`.

#### Failure Handling and Lock Release Guarantee
If Dataflow or postprocessing throws an unhandled exception:
* Cloud Workflows intercepts the error in its global `try/except` block ([workflow.yaml](../../infra/dcp/modules/ingestion/workflow/workflow.yaml)).
* It updates `IngestionHistory` to status `FAILED` and stage `failed` via `POST /imports/ingestion-history`.
* The workflow always executes `release_lock_on_failure` (`POST /database/lock/release`) before re-raising the error, ensuring the Spanner lock is never orphaned and subsequent ingestion runs are not blocked.

---

## End-to-End Serving Flow

The serving stack handles incoming data queries from web browsers, REST API clients, SDMX 3.0 consumers, and Model Context Protocol (MCP) agents through a multi-process container architecture hosted inside `datacommons-services`:

### Internal Serving Container Port Topology

Inside the `datacommons-services` Cloud Run container, traffic is multiplexed across dedicated internal ports:

| Service Component | Port | Interface | Responsibility |
| :--- | :--- | :--- | :--- |
| **Nginx Ingress** | `8080` | HTTP (Public) | Container front door. Routes `/*` to Website, `/core/api/*` to Envoy, and `/mcp/*` to MCP server. |
| **Website Service** | `7070` | HTTP (Internal) | Python Flask and Gunicorn application serving web pages and UI assets. |
| **Envoy ESP Sidecar** | `8081` | HTTP (Internal) | REST-to-gRPC transcoder. Translates HTTP/JSON requests into binary gRPC calls for Mixer. |
| **Mixer Backend** | `12345` | gRPC (Internal) | Core Go data serving engine executing queries against Spanner, Redis, and Base Data Commons. |
| **MCP Server** | `8082` | HTTP / SSE | Model Context Protocol server. Polls `http://localhost:8081/version` and starts once Mixer is healthy. |

### Serving Request Lifecycle

#### 1. Request Ingestion and Routing
* External clients submit HTTPS requests to Cloud Run port `8080`.
* **Nginx Reverse Proxy** inspects the URL path:
  * Static UI routes and explore pages route to Website on port `7070`.
  * `/core/api/*` routes to Envoy ESP on port `8081` with CORS headers and WebSocket upgrade support.
  * `/mcp/*` routes to the `datacommons-mcp` daemon on port `8082` with streaming buffering disabled.
* Envoy matches the request against Google API HTTP annotations (`mixer-grpc.pb`), transcodes JSON payloads into binary Protobuf messages, and forwards them to Mixer on port `12345`.

#### 2. Mixer Dispatcher and Scatter-Gather Facade
* Mixer's dispatcher receives incoming gRPC requests.
* Mixer inspects in-memory caches and Redis for matching query results.
* On cache misses, Mixer executes concurrent scatter-gather lookups:
  * **Private Graph Query**: Formulates SQL queries against the private Cloud Spanner database.
  * **Base Data Commons Query**: Formulates remote gRPC calls to `api.datacommons.org` to resolve public variables or parent geographic entities.

#### 3. Spanner Transactional Read Staleness and Active Write Isolation
* To isolate readers from partial updates during background ingestion pipelines, Mixer queries Spanner `IngestionHistory`:
  ```sql
  SELECT MIN(CreationTimestamp) AS StalenessTimestamp
  FROM IngestionHistory
  WHERE (SELECT MAX(CompletionTimestamp) FROM IngestionHistory WHERE Status = 'SUCCESS') IS NULL
     OR CreationTimestamp > (SELECT MAX(CompletionTimestamp) FROM IngestionHistory WHERE Status = 'SUCCESS');
  ```
* If an active ingestion run is in flight, Mixer pins reads to `MIN(CreationTimestamp)` of the active run. Readers are guaranteed never to observe uncommitted, partial, or mutating batch data.
* **Retention Fallback**: If the pinned timestamp exceeds Cloud Spanner's version retention period (default 24 hours) and Spanner returns `FAILED_PRECONDITION`, or if `IngestionHistory` is empty, Mixer catches the error and falls back to exact staleness (15 seconds) against head.

#### 4. Response Composition
* Mixer merges local Spanner graph observations with data from Base Data Commons.
* Private data takes precedence: if an entity-variable observation exists locally, Mixer serves the local record.
* Mixer streams the Protobuf response to Envoy on port `8081`, which transcodes the payload into JSON and returns it through Nginx on port `8080` to the client.
