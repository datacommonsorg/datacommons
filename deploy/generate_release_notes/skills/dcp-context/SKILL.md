---
name: dcp-context
description: Architectural reference, domain context, and component map for Data Commons Platform (DCP) release notes generation.
---

# Data Commons Platform (DCP) Domain Context & Architectural Map

This skill provides the domain context, platform architecture, user touchpoints, and single source of truth component mapping for evaluating Pull Request relevance and generating partner-facing release notes.

---

## 1. What is Data Commons Platform (DCP)?

- **Data Commons**: An open-knowledge graph that unifies public datasets across demographics, economics, climate, health, and geography into a standardized, interconnected graph structure.
- **Data Commons Platform (DCP)**: The self-hosted, enterprise-grade deployment of Data Commons. It allows organizations and partners to deploy an isolated Data Commons instance backed by Cloud Spanner, load custom proprietary datasets alongside public Data Commons data, expose standardized SDMX 3.0 REST and FastMCP AI agent interfaces, and manage infrastructure via Terraform and CLI automation.

---

## 2. User & Operator Touchpoints vs. Internal Implementation

When analyzing Pull Requests and synthesizing release notes, agents MUST distinguish between **external user/operator touchpoints** (what partners interact with) and **internal implementation mechanics** (non-user facing code).

### A. External User & Operator Touchpoints (PUBLIC RELEASE RELEVANT)
These represent the interfaces, contracts, and capabilities that partners, developers, data engineers, and instance operators directly interact with:

1. **Serving APIs & Protocols**:
   - SDMX 3.0 REST Data and Availability endpoints (`/sdmx/v3/rest/data/...`, `/sdmx/v3/rest/availability/...`).
   - Observations V2 API (`/v2/observation`) and Mixer gRPC graph endpoints.
   - Place containment expansion (`containedInPlace+`), time-series filtering (`TIME_PERIOD`).
2. **AI Agent Integration (MCP / Model Context Protocol)**:
   - FastMCP tools for AI agent research playbooks (`get_multi_entity_observations`, `search_indicators`, `get_variable_metadata`).
   - Indicator search target scopes (`custom_only`, `base_only`, `base_and_custom`).
3. **Web Applications & Exploration Tools**:
   - Explore UI, Download Tool, Place Browser, Croissant JSON-LD dataset metadata.
4. **Infrastructure & Deployment Automation**:
   - Terraform modules (`infra/dcp/`), variables (`ingestion_dataflow_max_workers`, `spanner_processing_units`), and IAM role configurations.
   - Admin CLI (`datacommons admin init`, `datacommons admin deploy`) and Admin Portal web interface.
   - Vector search profile configurations (`--spanner_search_config_path`).
5. **Data Ingestion Inputs**:
   - Custom CSV/MCF dataset formats, column mapping definitions, and batch import job configurations.

### B. Internal Implementation Mechanics (NON-USER FACING — DO NOT EXPOSE)
These are internal engine mechanics that partners do NOT interact with directly. They should be framed around high-level user impact (e.g. *"98% lower query latency"*) without exposing internal table names or DDLs:
- Internal Cloud Spanner DDL graph table schemas and KeyValueStore tables.
- Dataflow TFRecord chunking and intermediate GCS staging paths.
- Cloud Workflows internal execution IDs and status tracking tables (`IngestionHistory`).
- Internal SQL parameter unrolling and join ordering optimizations.

---

## 3. Component & Repository Registry (SINGLE SOURCE OF TRUTH)

All skills and subagents MUST use this table as the single authoritative source of truth for component keys, source repositories, subdirectory path filters, target container images, and output verification files:

| Component Key | Component Name | Source Repositories & Subdirectory Filters | Container Image URI / Release Artifact | Output Verification File |
| :--- | :--- | :--- | :--- | :--- |
| `services` | Core Services (Website, Mixer, MCP Agent) | `datacommonsorg/website` (`server/`, `static/`, `build/cdc_services/`)<br>`datacommonsorg/mixer` (`internal/server/`, `proto/`, `deploy/`)<br>`datacommonsorg/agent-toolkit` (`src/datacommons_mcp/`) | `gcr.io/datcom-ci/datacommons-services` | `output/prs_services.txt` |
| `preprocessing` | Data Preprocessor | `datacommonsorg/import` (`simple/`) | `gcr.io/datcom-ci/datacommons-data` | `output/prs_preprocessing.txt` |
| `dataflow_worker` | Dataflow Ingestion Worker | `datacommonsorg/import` (`pipeline/ingestion/`) | `us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion` | `output/prs_dataflow_worker.txt` |
| `ingestion_helper` | Ingestion Helper Service | `datacommonsorg/import` (`pipeline/workflow/ingestion-helper/`) | `gcr.io/datcom-ci/datacommons-ingestion-helper` | `output/prs_ingestion_helper.txt` |
| `postprocessing` | Postprocessing Helper Service | `datacommonsorg/import` (`pipeline/workflow/aggregation-helper/`) | `gcr.io/datcom-ci/datacommons-aggregation-helper` | `output/prs_postprocessing.txt` |
| `dcp_monorepo` | DCP Monorepo & Terraform Infra | `datacommonsorg/datacommons` (`infra/dcp/`, `packages/`) | DCP Monorepo & Terraform Modules | `output/prs_dcp_monorepo.txt` |
