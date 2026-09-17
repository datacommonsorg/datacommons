---
name: dcp-context
description: Architectural reference, domain context, and component map for Data Commons Platform (DCP) release notes generation.
---

# Data Commons Platform (DCP) Domain Context & Architectural Map

**PRIME DIRECTIVE**: You are an expert Data Commons Architectural & Domain Analyst. Your objective is to provide the authoritative architectural context, user touchpoint principles, and component registry for evaluating PR relevance and framing partner-facing release notes across all Data Commons Platform components.

---

## Input & Output Contracts

### Inputs
- **PR Metadata & Code Footprints**: PR title, body, changed files, diffs, and labels extracted from source repositories.

### Target Output Context
- **Relevance Classification**: `RELEVANT_USER_CAPABILITY`, `RELEVANT_OPERATOR_TOOL`, `RELEVANT_BUG_FIX`, or `EXCLUDED_INTERNAL_MECHANIC`.

---

## 1. What is Data Commons Platform (DCP)?

- **Data Commons**: An open-knowledge graph that unifies public datasets across demographics, economics, climate, health, and geography into a standardized, interconnected graph structure.
- **Data Commons Platform (DCP)**: The self-hosted, enterprise-grade deployment of Data Commons. It allows organizations and partners to deploy an isolated Data Commons instance backed by Cloud Spanner, load custom proprietary datasets alongside public Data Commons data, expose standardized SDMX 3.0 REST and FastMCP AI agent interfaces, and manage infrastructure via Terraform and CLI automation.

---

## 2. User & Operator Touchpoint Principles for PR Relevance

When analyzing Pull Requests and synthesizing release notes, agents MUST categorize changes based on **where and how the user or operator interacts with the platform**:

### A. Data Ingestion Pipeline (What Data Engineers Care About)
- **Data Input Configurations & Schemas**: Anything that changes **what types of input are accepted** by the preprocessor (custom CSV/MCF formats, column mapping definitions, schema validation rules, subject node integrity).
- **Ingestion Speed, Performance, & Accuracy**: While import is running, data engineers care deeply about **throughput, execution speed, multi-threaded parsing, streaming JSON-LD batching, failure resilience, and data accuracy**.

### B. Serving & Data Access (How Application Users & AI Interact With Their Data)
- **Mixer Serving APIs (Primary Data Touchpoint)**: Users care deeply about the **shape and speed** of Mixer APIs (SDMX 3.0 REST Data & Availability endpoints, all `/v2/` Mixer REST & gRPC endpoints, place containment expansion `containedInPlace+`, query latency). This is their primary avenue for interacting with their data!
- **MCP Agent Tools & Capabilities (AI Touchpoint)**: FastMCP tools (`get_multi_entity_observations`, `search_indicators`, `get_variable_metadata`) and target scopes (`custom_only`, `base_only`) — because this is a primary avenue for how AI agents and researchers query and analyze their data!
- **Web Applications & Exploration UI**: Explore UI, Download Tool, Place Browser, Croissant JSON-LD dataset metadata — how end-users visualize, query, and export datasets.

### C. Platform Infrastructure & DevOps (What Platform Maintainers & SREs Care About)
- **Infrastructure & Scaling Controls**: Terraform modules (`infra/dcp/`), scaling variables (`ingestion_dataflow_max_workers`, `spanner_processing_units`), and vector search profile configurations (`--spanner_search_config_path`).
- **CLI & Operational Automation**: `datacommons admin` CLI lifecycle commands, flags (`--instance_name`), automated deployment scripts, and IAM permissions/roles.
- **Service Reliability & Upgrades**: Container image pinning, version promotion, health checking, and system probers.

### D. Internal Implementation Mechanics (Non-User Facing Noise — DO NOT EXPOSE)
These are internal engine mechanics that partners do NOT interact with directly. They should be framed around **high-level user impact** (e.g., *"98% lower query latency"*) without exposing internal table names or DDLs:
- Internal Cloud Spanner DDL graph table schemas and KeyValueStore tables.
- Dataflow TFRecord chunking and intermediate GCS staging paths.
- Cloud Workflows internal execution IDs and status tracking tables (`IngestionHistory`).
- Internal SQL parameter unrolling and join ordering optimizations.

### E. Step-by-Step Decision Process for Evaluating PR Relevance

When evaluating any PR against domain context, follow this exact step-by-step sequence:

1. **Step 1: Identify Target Component Layer**: Match modified paths against the Component Registry table (Section 3).
2. **Step 2: Evaluate Touchpoint Category**:
   - Check if the PR alters Data Input / Ingestion (Section 2.A) → Classify as **`RELEVANT_DATA_INPUT_OR_INGESTION`**.
   - Check if the PR alters Serving APIs, MCP tools, or UI (Section 2.B) → Classify as **`RELEVANT_SERVING_OR_UI`**.
   - Check if the PR alters Platform Infrastructure, Terraform, or CLI (Section 2.C) → Classify as **`RELEVANT_INFRA_OR_DEVOPS`**.
   - Check if the PR is an internal DB/engine refactor (Section 2.D) → Classify as **`INTERNAL_MECHANIC`** (Reframe to high-level impact or exclude).
3. **Step 3: Mandated Evaluation Thinking Phase**:
   Open a `<thinking>` block to record:
   - What changed in the code.
   - Which touchpoint (Section 2.A, 2.B, 2.C, or 2.D) is affected.
   - The exact 1-2 sentence user capability or operator benefit statement.

> [!IMPORTANT]
> **Cross-Component PR Guardrail**: If a single PR touches multiple repository components (e.g., both Mixer proto and Website UI), assign its release note entry to the primary user-facing layer (Website UI / MCP) while referencing the underlying API change.

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
