---
name: dcp-context
description: Architectural reference and domain context for Data Commons Platform (DCP) release notes generation.
---

# Data Commons Platform (DCP) Domain Context & Architectural Map

This skill provides the domain context, repository mapping, and architectural principles for writing publication-ready, partner-facing DCP release notes.

---

## 1. Core Architectural Overview & Single Source of Truth Mapping

Data Commons Platform (DCP) is a self-hosted, Cloud Spanner-backed deployment of Data Commons. It replaces legacy Bigtable with Cloud Spanner graph tables and vector embeddings. It features custom data ingestion pipelines, specialized serving APIs, and deployment automation across 6 core repositories.

### 📌 Component & Repository Mapping Registry (SINGLE SOURCE OF TRUTH)
All skills and subagents MUST use this table as the single authoritative source of truth for component keys, source repositories, subdirectory path filters, target container images, and output verification files:

| Component Key | Component Name | Source Repositories & Subdirectory Filters | Container Image URI / Release Artifact | Output Verification File |
| :--- | :--- | :--- | :--- | :--- |
| `services` | Core Services (Website, Mixer, MCP Agent) | `datacommonsorg/website` (`server/`, `static/`, `build/cdc_services/`)<br>`datacommonsorg/mixer` (`internal/server/`, `proto/`, `deploy/`)<br>`datacommonsorg/agent-toolkit` (`src/datacommons_mcp/`) | `gcr.io/datcom-ci/datacommons-services` | `output/prs_services.txt` |
| `preprocessing` | Data Preprocessor | `datacommonsorg/import` (`simple/`) | `gcr.io/datcom-ci/datacommons-data` | `output/prs_preprocessing.txt` |
| `dataflow_worker` | Dataflow Ingestion Worker | `datacommonsorg/import` (`pipeline/ingestion/`) | `us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion` | `output/prs_dataflow_worker.txt` |
| `ingestion_helper` | Ingestion Helper Service | `datacommonsorg/import` (`pipeline/workflow/ingestion-helper/`) | `gcr.io/datcom-ci/datacommons-ingestion-helper` | `output/prs_ingestion_helper.txt` |
| `postprocessing` | Postprocessing Helper Service | `datacommonsorg/import` (`pipeline/workflow/aggregation-helper/`) | `gcr.io/datcom-ci/datacommons-aggregation-helper` | `output/prs_postprocessing.txt` |
| `dcp_monorepo` | DCP Monorepo & Terraform Infra | `datacommonsorg/datacommons` (`infra/dcp/`, `infra/modules/`, `packages/`) | DCP Monorepo & Terraform Modules | `output/prs_dcp_monorepo.txt` |

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

## 3. Section Mapping & Release Content Principles

Rather than using arbitrary internal categories, map changes directly into the three standard release notes sections based on technical impact:

1. **Key Feature Updates**:
   - Major, high-impact capabilities introduced in this release (e.g., SDMX 3.0 REST Data & Availability APIs, FastMCP AI agent tools, streaming JSON-LD preprocessors, vector search embeddings).
   - Must follow the non-verbose format: **What's New** (1 paragraph combining description + benefit) followed by **Specific Capabilities** (bullet points with `[repo#PR](URL)` links).

2. **Improvements & Configuration Updates**:
   - Incremental enhancements, operator tools, Terraform variables (`max_workers`, BigQuery slots), CLI flags (`--instance_name`), and scaling optimizations.
   - Must extract concrete enums (e.g. `custom_only`, `base_only`) and explicit configuration parameters.

3. **Bug Fixes**:
   - Synthesized into 3 to 5 functional categories (*Deployment & Infrastructure*, *Ingestion Pipeline Reliability*, *Serving API & Query Robustness*, *Web UI & Visualization*).
   - Must ONLY include true platform bug fixes present in prior releases (excluding intra-release intermediate fixes).
