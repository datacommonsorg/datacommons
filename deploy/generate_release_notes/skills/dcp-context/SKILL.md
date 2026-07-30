---
name: dcp-context
description: Architectural reference and domain context for Data Commons Platform (DCP) release notes generation.
---

# Data Commons Platform (DCP) Domain Context & Architectural Map

This skill provides the domain context, repository mapping, and architectural principles for writing publication-ready, partner-facing DCP release notes.

---

## 1. Core Architectural Overview

Data Commons Platform (DCP) is a self-hosted, Cloud Spanner-backed deployment of Data Commons. It replaces legacy Bigtable with Cloud Spanner graph tables and vector embeddings. It features custom data ingestion pipelines, specialized serving APIs, and deployment automation across 6 core repositories:

1. `datacommonsorg/datacommons` (Monorepo & Infra):
   - **Terraform Modules** (`infra/dcp/`, `infra/modules/`): Infrastructure provisioning for Spanner, Cloud Run, BigQuery, and Dataflow.
   - **CLI Tools** (`packages/datacommons-cli/`): `datacommons admin init`, `datacommons admin deploy`.
   - **Admin Portal** (`packages/datacommons-admin/`): Web management interface.

2. `datacommonsorg/website` (Web Application & Frontend):
   - Serves UI pages (Explore, Visualization Tools, Place Browser) and REST API routing (`server/`, `static/`, `build/cdc_services/`).

3. `datacommonsorg/mixer` (Core Serving Engine):
   - High-performance gRPC graph and StatVar serving engine (`internal/server/`, `proto/`, `deploy/helm_charts/`, ESPv2 gateway).
   - Serves SDMX 3.0 REST Data & Availability endpoints, `/v2/observation`, and vector search embeddings.

4. `datacommonsorg/agent-toolkit` (Model Context Protocol / MCP):
   - Model Context Protocol (MCP) server & FastMCP tools for AI agent integrations (`src/datacommons_mcp/`).
   - Enables agentic research playbooks, multi-entity observation retrieval, and indicator search across custom or base instances.

5. `datacommonsorg/import` (Ingestion Stack & Cloud Workflows):
   - **Data Preprocessor** (`simple/`): CSV/MCF validation and streaming JSON-LD batching (built into `datacommons-data` container image).
   - **Dataflow Ingestion Worker** (`pipeline/ingestion/`): Parallelized BigQuery/Spanner graph loading.
   - **Cloud Workflow Helpers** (`pipeline/workflow/ingestion-helper/`, `pipeline/workflow/aggregation-helper/`): Ingestion status tracking and postprocessing aggregations (StatVar, Place, Entity rollups).

---

## 2. Architectural Boundary & Persona Principles

### Focus on External Contracts & Operator Capabilities
- **Partner & Operator Focus**: Write specifically for external developers, data engineers, and instance operators building ON TOP OF DCP.
- **User Capabilities**: Frame every feature and improvement around *what the user can now do*, *which input formats are supported*, or *how compute resources scale*.
- **Extract Concrete Enums & Configuration Values**: Always extract valid enums (`custom_only`, `base_only`, `base_and_custom`), CLI flags (`--instance_name`), and scaling bounds (`max_workers`, BigQuery slots).

### Zero Internal Implementation Mechanics (STRICT)
- **NO Internal Database Terms**: NEVER output feature titles or section names containing internal database table names, schema DDLs, or storage migration mechanics (e.g. no "KeyValueStore", "Spanner Graph DDL", "Bigtable Cutover", "Database Schema Modification").
- **Frame Performance Speedups Around User Impact**: If an internal storage or cache layer change improves serving speed, title it around user impact: **"API Serving Latency & Query Throughput"** or **"Faster API Response Speed"** without naming internal database tables.

---

## 3. SOP Categories & Release Notes Mapping Matrix

The 4 SOP categories translate directly into the sections of the final release notes document:

| SOP Category | Scope & Included Components | Release Notes Section Mapping |
| :--- | :--- | :--- |
| **Spanner Graph & APIs** | Mixer gRPC, SDMX 3.0 REST, `/v2/observation`, FastMCP tools | **Key Feature Updates** (Major API/MCP Features)<br>**Bug Fixes**: *Serving API & Query Robustness* |
| **Ingestion & Safety** | Preprocessor, Dataflow workers, Cloud Workflows, postprocessing rollups | **Key Feature Updates** (Major Pipeline Features)<br>**Improvements**: *Dataflow Transformations / Postprocessing*<br>**Bug Fixes**: *Ingestion Pipeline Reliability* |
| **Search & Website** | Vector embeddings, semantic search, Explore UI, Download Tool, Place Browser | **Key Feature Updates** (Search/Embeddings)<br>**Improvements**: *Website Exploration Tools*<br>**Bug Fixes**: *Web UI & Visualization* |
| **Infra & Tooling** | Terraform modules, Admin CLI (`datacommons admin`), Cloud Run, IAM roles | **Improvements**: *Terraform Infrastructure & Auto-Scaling*<br>**Bug Fixes**: *Deployment & Infrastructure Reliability* |
