# Data Commons Platform (DCP) — Integration Test Suite

A modular, data-driven end-to-end integration test harness for the Data Commons Platform (DCP).

---

## 🧭 Core Testing Principles & Platform Contract

The DCP integration test harness is governed by three foundational principles:

### 1. Targeted, Contract-Driven Assertions (No Arbitrary Goldens)
Tests are strictly focused on asserting specific features, behaviors, and contract boundaries rather than diffing against monolithic golden files. 
* Each test isolates and verifies deterministic pieces of the response (e.g., HTTP status codes, specific dimension values, existence of graph edges, precise error diagnostic strings).
* Brittle full-payload snapshots that break on unrelated timestamp or metadata additions are strictly prohibited; assertions must pinpoint exact functional regressions.

### 2. Living Contract of Supported Platform Capabilities
The integration test suite serves as the **executable specification and single source of truth** for everything DCP supports across all tiers.
* If a capability is supported by the platform (every ingestion format, database mapping, API request mode, SDMX filter syntax, or MCP tool capability), it must be explicitly represented in the test suite.
* Inspecting the integration test suites provides an unambiguous, comprehensive map of all supported platform features and operational guarantees.

### 3. Modular, Non-Redundant Organization (The 3-Tier Dataset Model)
Tests and datasets are organized into clear, non-overlapping domains to maximize coverage without duplicate overhead. Every capability belongs to a specific tier:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  Tier 1: Core Single-Entity Suite (foobar_wages)                                │
│  ⭐ The "Default" Benchmark: Exercises 80%+ of DCP platform capabilities        │
├──────────────────────────────────────────────────────────────────────────────────┤
│  Tier 2: Multi-Entity Dimension Suite (health_aid)                               │
│  Strictly reserved for multi-dimensional flow indexing, slices & availability   │
├──────────────────────────────────────────────────────────────────────────────────┤
│  Tier 3: Hierarchies Suite (topics_demo)                                         │
│  Custom Topic DAGs, BigQuery transitive closures & recursive expansion           │
└──────────────────────────────────────────────────────────────────────────────────┘
```

#### The Delineation Rule: Single-Entity vs. Multi-Entity
> **If a platform capability can be tested with a single entity dimension, it MUST be tested in `foobar_wages`.**  
> `health_aid` is strictly reserved for capabilities that are mathematically or architecturally impossible in single-entity data.

* **What `foobar_wages` (Single-Entity) Owns**:
  1. Generic Ingestion & Spanner Dataflow table population.
  2. Temporal Query Modes: Point (`LATEST`), Explicit Date (`2021`), Series (`all`).
  3. Existence Checks: Variable-Entity (`CheckVariableExistence`) & Variable-Source (`CheckVariableSourceExistence`).
  4. Node Expressions: Direct, Bracketed, Wildcards (`->*`), and Empty-arc predicate introspection (`->`).
  5. Vector Embeddings Semantic Search.
  6. **Single-Entity Property Variants**:
     * *Implicit default*: `observationAbout` mapped to `entity1`.
     * *Explicit standard*: `observationProperties: [observationAbout]`.
     * *Custom local property*: `observationProperties: [facility]`.
     * *Remote BaseDC property*: `observationProperties: [medicalCondition]`.
  7. Standard MCP single-entity tools: `search_indicators`, `get_observations`, `get_variable_metadata`.

* **What `health_aid` (Multi-Entity) Owns**:
  1. **Multi-Slot Dimension Sharding**: Mapping $N \ge 2$ entity dimensions into Spanner's `entity1`, `entity2`, `entity3` direct columns and `extra_entities_id` composite key (`val2^val3`).
  2. **Cross-Entity Secondary Slicing**: Slicing observations where the primary entity (`donorPlace`) is unconstrained, but a secondary entity (`recipientPlace` or `medicalCondition`) is filtered.
  3. **Cascading / Constrained Multi-Entity Availability**: Finding available values of Dimension B strictly when Dimension A is held constant.
  4. **Cross-Variable Compatibility Enforcement**: Rejecting batch requests that query variables with incompatible observation property shapes.
  5. **MCP Multi-Entity Dictionary Tool**: `get_multi_entity_observations`.

* **What `topics_demo` (Hierarchies) Owns**:
  1. **SVG Hierarchy & Custom Topic DAGs**: BigQuery transitive closure tables, recursive StatVarGroup/Topic tree expansion (`expand_topics=true`), and multi-hop parent/child indicator navigation.

---

## 🏗️ Test Execution Stages

The harness exercises platform components across 4 execution stages:
1. **Ingestion (`suites/01_ingestion/`):** CLI initialization, Spanner Node graph & observation seeding, and Cloud Workflows / Dataflow verification.
2. **Postprocessing (`suites/02_postprocessing/`):** Statistical Variable Group (SVG) hierarchy trees and Spanner vector embeddings semantic search.
3. **Serving API (`suites/03_serving_api/`):** Python SDK (`datacommons-client`), `/v2/observation` (point & series), `/v2/node`, and SDMX 3.0 REST endpoints.
4. **AI Agent & MCP (`04_mcp_agent/`):** Model Context Protocol (MCP) JSON-RPC 2.0 tool execution (`search_indicators`, `get_multi_entity_observations`, etc.).

---

## 🚀 Quick Start

### 1. Run Hermetic Emulated Tests (Local & Cloud Build)
Run the entire end-to-end stack (Spanner Omni emulator, Fake GCS, Apache Beam ingestion, Website, and MCP Agent) hermetically on Docker Compose without requiring live GCP infrastructure.

#### Local Execution (macOS / Linux):
```bash
# First run (boots emulators, runs schema DDL migrations, ingests dataset, runs tests):
uv run pytest tests/integration/suites/ \
    --instance local \
    --test-config foobar_wages

# Fast re-runs (~1 second by reusing already-seeded emulators):
uv run pytest tests/integration/suites/ \
    --instance local \
    --test-config foobar_wages \
    --reuse-data
```

#### Cloud Build CI Execution:
```bash
gcloud builds submit \
    --project=datcom-ci \
    --config=tests/integration/emulated/cloudbuild_emulated_test.yaml \
    .
```
> 📖 See the [Hermetic Emulated Stack Guide](emulated/README.md) for architecture details, Cloud Build configuration, and image overrides.

### 2. Run Tests Against a Cloud Testbed (e.g. `testbed-1`)
```bash
uv run python tests/integration/run_e2e_tests.py \
    --instance testbed-1 \
    --test-config foobar_wages \
    --reuse-data
```

### 3. Run Composed Multi-Dataset Tests
You can combine multiple dataset specs directly on the CLI:
```bash
uv run python tests/integration/run_e2e_tests.py \
    --instance testbed-1 \
    --test-config foobar_wages \
    --test-config foobar_education \
    --reuse-data
```

### 4. Run a Specific Stage / Suite
```bash
# Run only Serving API suite:
uv run python tests/integration/run_e2e_tests.py \
    --instance testbed-1 \
    --test-config foobar_wages \
    --suite 03_serving_api \
    --reuse-data

# Run only Ingestion suite:
uv run python tests/integration/run_e2e_tests.py \
    --instance testbed-1 \
    --test-config foobar_wages \
    --suite 01_ingestion
```

---

## 📊 Structured Reporting & GCS Publishing

The runner automatically generates structured JSON reports with timestamp-sorted, context-rich filenames:
`YYYYMMDDTHHMMSSZ_<instance>_<datasets>_<commit>_<status>.json`

### Output to a Local Directory:
```bash
uv run python tests/integration/run_e2e_tests.py \
    --instance testbed-1 \
    --test-config foobar_wages \
    --report-output ./test_reports/ \
    --reuse-data
```

### Output Directly to Google Cloud Storage (`gs://`):
```bash
uv run python tests/integration/run_e2e_tests.py \
    --instance testbed-1 \
    --test-config foobar_wages \
    --report-output gs://testbed-1-dc-artifacts-datcom-dcp/integration_tests/ \
    --reuse-data
```

---

## 📡 Continuous Probers (24/7 Automated GCP Health Probing)

DCP includes an automated **Serverless Ephemeral Prober** that runs continuously in Google Cloud to verify platform health across end-to-end releases.

Every 3 hours, Cloud Scheduler triggers an isolated Cloud Run Job (`dcp-prober`) that:
1. Provisions a fresh ephemeral DCP instance via Terraform.
2. Runs the full end-to-end integration test suite against the live instance.
3. Publishes structured execution reports to Google Cloud Storage.
4. Triggers instant Cloud Monitoring alerts if any test fails.
5. Guarantees 100% infrastructure teardown.

### Monitoring Active Probers & Execution Status
* **Cloud Run Job Executions**: [Console: `dcp-prober` Executions](https://console.cloud.google.com/run/jobs/details/us-central1/dcp-prober/executions?project=datcom-dcp)
* **Cloud Scheduler Cron**: [Console: `dcp-prober-cron`](https://console.cloud.google.com/cloudscheduler/jobs/edit/us-central1/dcp-prober-cron?project=datcom-dcp)
* **Historical Prober Reports**: [Console: `dcp-prober-reports-datcom-dcp/reports`](https://console.cloud.google.com/storage/browser/dcp-prober-reports-datcom-dcp/reports?project=datcom-dcp) (`gs://dcp-prober-reports-datcom-dcp/reports/`)

> 📖 **Deploying or Updating Probers**:
> * To update prober schedules, alert recipients, or test dataset manifests, see the [Prober Architecture Guide](prober/README.md).
> * For the full deployment and update runbook using `deploy_prober.sh`, see the [Prober Deployment Runbook](prober/deploy/README.md).

---

## 🎛️ CLI Package Testing (Local / TestPyPI / PyPI)

### Test Local CLI Development Source
```bash
uv run python tests/integration/run_e2e_tests.py \
    --instance testbed-1 \
    --test-config foobar_wages \
    --cli-source local
```

### Test Candidate CLI Package from TestPyPI
```bash
uv run python tests/integration/run_e2e_tests.py \
    --instance testbed-1 \
    --test-config foobar_wages \
    --cli-source testpypi \
    --cli-version 1.1.2rc1
```

---

## 📁 Directory Architecture

```
tests/integration/
├── README.md                      # This documentation
├── run_e2e_tests.py               # Master CLI & programmatic runner
├── conftest.py                    # Pytest lifecycle hooks & dynamic parameterization
│
├── emulated/                      # Hermetic Local Docker Compose Stack & Cloud Build CI
│   ├── README.md                  # Local emulated architecture & usage guide
│   ├── docker-compose.yml         # Spanner Omni, Fake GCS, Helper & Website services
│   ├── environment.py             # EmulatedEnvironment lifecycle manager
│   ├── cloudbuild_emulated_test.yaml # Standalone Cloud Build hermetic CI pipeline
│   └── patches/                   # Runtime patches (IPv4 resolution, GCS & Spanner mock)
│
├── prober/                        # Automated 24/7 GCP Prober & Ephemeral runner
│   ├── README.md                  # Prober architecture, flow & local debugging
│   ├── prober_runner.py           # Ephemeral instance orchestrator (3-Phase lifecycle)
│   ├── ephemeral_dcp_overrides.tfvars.template # Static overrides for ephemeral target instances
│   ├── deploy/                    # Cloud deployment automation & Terraform blueprint
│   │   ├── README.md              # Complete Prober deployment runbook
│   │   ├── deploy_prober.sh       # Cloud Build & Terraform deployment script
│   │   ├── Dockerfile             # Prober container image definition
│   │   ├── cloudbuild.yaml        # Cloud Build pipeline configuration
│   │   └── terraform/             # Infrastructure-as-Code for Prober daemon
│   │       ├── backend.tf         # Remote GCS state locking
│   │       ├── main.tf            # Service Account, Cloud Run Job, Scheduler & Alerts
│   │       ├── variables.tf       # Prober Terraform variables
│   │       └── outputs.tf         # Terraform outputs
│   └── tools/                     # Prober operational utilities
│       └── cleanup_prober_trash.py # Interactive janitor for orphaned ephemeral resources
│
├── test_data/                     # Benchmark datasets & self-contained test specs
│   ├── foobar_wages/              # FooBar Wages CSV, MCF, config.json, test_spec.yaml
│   └── foobar_education/          # FooBar Education CSV, MCF, config.json, test_spec.yaml
│
├── suites/                        # Generic, dataset-agnostic test suites
│   ├── 01_ingestion/              # CLI Ingestion & Cloud Spanner graph verification
│   ├── 02_postprocessing/         # SVG hierarchy trees & vector embeddings
│   ├── 03_serving_api/            # datacommons-client (/v2/node, /v2/observation) & SDMX 3.0
│   └── 04_mcp_agent/              # Model Context Protocol (MCP) tool execution
│
├── core/                          # Runtime test execution engines
│   ├── target.py                  # DCPTarget and ArtifactConfig dataclasses
│   ├── resolver.py                # Discovers live endpoints & deployed images from Terraform
│   ├── cli_runner.py              # Subprocess DatacommonsCLI runner (local/testpypi/pypi)
│   ├── spanner_client.py          # Direct Cloud Spanner query client
│   ├── permissions.py             # Preflight IAM TokenCreator, GCS & Spanner verification
│   ├── mcp_client.py              # JSON-RPC 2.0 MCP client
│   ├── config_schema.py           # Typed manifest schemas, loader, and multi-spec merger
│   └── reporter.py                # Structured JSON reporter & timestamped GCS uploader
│
├── unit_tests/                    # Fast local unit tests (no GCP/network required)
│   └── test_config_schema.py      # Schema parsing, loader, and multi-manifest merge tests
│
└── tools/                         # Developer utilities
    └── synthesizer.py             # Auto-generates test_spec.yaml from raw dataset folders
```
