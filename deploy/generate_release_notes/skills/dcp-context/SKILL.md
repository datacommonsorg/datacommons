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
| `dcp_monorepo` | DCP Monorepo & Terraform Infra | `datacommonsorg/datacommons` (`infra/dcp/`, `packages/`) | DCP Monorepo & Terraform Modules | `output/prs_dcp_monorepo.txt` |
