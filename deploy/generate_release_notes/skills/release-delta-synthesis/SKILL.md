---
name: dcp-release-delta-synthesis
description: Subagent skill for analyzing raw PR verification files (prs_*.txt) and synthesizing image-level release deltas relative to the previously published release image.
---

# DCP Release Delta Synthesis Skill (Image Impact & Delta Analysis)

**PRIME DIRECTIVE**: You are an expert Data Commons Release Delta Synthesizer. Your objective is to analyze all raw PR verification files (`deploy/generate_release_notes/output/prs_*.txt`), evaluate component-level changes relative to previously published container images, filter out intra-release intermediate bug fixes, and synthesize a unified `IMAGE_DELTAS_<new_version>.txt` document.

---

## Input & Output Contracts

### Input Files
- **Raw Verification Files**: `deploy/generate_release_notes/output/prs_*.txt` (`prs_services.txt`, `prs_preprocessing.txt`, `prs_dataflow_worker.txt`, `prs_ingestion_helper.txt`, `prs_postprocessing.txt`, `prs_dcp_monorepo.txt`).
- **Context Reference**: [`skills/dcp-context/SKILL.md`](../dcp-context/SKILL.md) (User Touchpoint Principles Section 2).

### Target Output Artifact
- **Unified Image Delta Summary**: `deploy/generate_release_notes/output/IMAGE_DELTAS_<new_version>.txt`.

---

## Execution SOP Sequence

### Step 1: Read & Consolidate PR Verification Files
1. Check that all expected `prs_*.txt` files exist in `deploy/generate_release_notes/output/`.
2. Read all `prs_*.txt` files.
3. Group PRs by component key (`services`, `preprocessing`, `dataflow_worker`, `ingestion_helper`, `postprocessing`, `dcp_monorepo`).

> [!IMPORTANT]
> **Input Verification Guardrail**: If any `prs_*.txt` file is missing or unreadable, halt execution immediately and report the missing component file to the orchestrator agent before proceeding.

### Step 2: Mandated Bug Fix Lineage Tracing (Thinking Phase)
For EVERY bug fix PR found across all `prs_*.txt` files, open a `<thinking>` block to record your step-by-step investigation:

1. **PR Title & Description Reference Check**:
   - Check if the PR description references another PR merged in the current range (e.g., *"Fixes #2015"*, *"Follow up to #2000"*, *"Regression introduced by #1967"*).
   - If it references an intermediate PR merged within `[t_prev..t_new]`, classify it as **`INTRA_RELEASE_INTERMEDIATE_FIX` (EXCLUDE FROM PUBLIC NOTES)**.
2. **Footprint & Feature Matching**:
   - Compare the PR's `Change Summary` and modified files against major features in `prs_*.txt` merged earlier in the window.
   - If the bug is for a feature first introduced in this release window (e.g. SDMX 3.0 REST endpoints, FastMCP tools), classify it as **`INTRA_RELEASE_INTERMEDIATE_FIX` (EXCLUDE FROM PUBLIC NOTES)** because users running `<prev_version>` were never exposed to this bug.
3. **Git History Verification (If Ambiguous)**:
   - If a bug fix is ambiguous, run `git log -S "<function_or_symbol>" <prev_version>` or inspect `git diff <prev_version>..<new_version>` via shell to check if the code existed in `<prev_version>`.
   - If the code existed in `<prev_version>` and was broken, classify it as **`PRIOR_RELEASE_TRUE_FIX` (INCLUDE IN PUBLIC NOTES)**.

### Step 3: Synthesize Salient Image Deltas & Preserve URLs
For each container image / component, summarize the salient changes from the perspective of an operator upgrading from `<prev_version>` to `<new_version>`.

*CRITICAL MANDATE*: Preserve the full `URL` string for EVERY PR referenced in the delta summary so the final Release Writer can format clean GFM links `[repo#PR](URL)` without guessing!

1. **Major Feature Capabilities Added**:
   - What new capabilities exist in this image that were not present in `<prev_version>`?
   - What new API endpoints, protocols (e.g. SDMX 3.0, FastMCP), or UI tools are now available?
2. **Configuration & Infra Updates**:
   - What new Terraform variables, CLI parameters (`--instance_name`), or environment variables were added?
   - What scaling bounds (`max_workers`, BigQuery slots) or memory optimizations were introduced?
3. **True Platform Bug Fixes**:
   - What issues present in `<prev_version>` were resolved in this container image? Include full PR URLs for each fix!

---

## Component & Service Separation Rules

Do NOT club Website, Mixer, and MCP Agent Toolkit together in the output synthesis. Separate them into distinct, dedicated component sections so developers and operators can clearly see changes per layer:

1. **`Mixer Serving Engine & SDMX APIs`** (`datacommonsorg/mixer`): Core gRPC serving engine, SDMX 3.0 REST Data/Availability endpoints, all `/v2/` Mixer REST & gRPC endpoints, vector search indexing, SQL query planner optimizations.
2. **`MCP Agent Toolkit & FastMCP Tools`** (`datacommonsorg/agent-toolkit`): FastMCP tools, `get_multi_entity_observations`, indicator search tools, target scope resolution (`custom_only`, `base_only`).
3. **`Website UI & Exploration Tools`** (`datacommonsorg/website`): Explore UI, Download Tool, Place Browser, Croissant dataset metadata, web server routing and caching.
4. **`Data Preprocessor`** (`datacommonsorg/import` - `datacommons-data`): CSV/MCF validation, 10k-node streaming JSON-LD batching, namespace mapping.
5. **`Dataflow Ingestion Worker`** (`datacommonsorg/import` - Dataflow Templates): TFRecord loading, Spanner graph transformations, `max_workers` auto-scaling.
6. **`Ingestion Helper Service`** (`datacommonsorg/import` - `datacommons-ingestion-helper`): Cloud Workflows status tracking, execution IDs, history tables.
7. **`Postprocessing Aggregation Helper`** (`datacommonsorg/import` - `datacommons-aggregation-helper`): StatVar/Place/Entity rollups, summary store, DPV aggregations.
8. **`DCP Monorepo & Infrastructure`** (`datacommonsorg/datacommons`): Terraform modules (`infra/dcp/`), Admin CLI (`datacommons admin`), Cloud Run job orchestration.

---

## Output Document Structure (`IMAGE_DELTAS_<new_version>.txt`)

Write `deploy/generate_release_notes/output/IMAGE_DELTAS_<new_version>.txt` using the exact structure below:

```
================================================================================
DCP RELEASE DELTA SUMMARY: {prev_version} -> {new_version}
Generated Date: {date}
================================================================================

--------------------------------------------------------------------------------
1. COMPONENT: Mixer Serving Engine & SDMX APIs (datacommonsorg/mixer)
   Container Image: gcr.io/datcom-ci/datacommons-services (Mixer binary)
--------------------------------------------------------------------------------

SALIENT FEATURES & CAPABILITIES (vs. {prev_version}):
- SDMX 3.0 REST Data & Availability Endpoints: Serves multi-entity observations in SDMX-CSV 2.0 format with facetId filtering and containedInPlace+ expansion ([mixer#1976](https://github.com/datacommonsorg/mixer/pull/1976), [mixer#1988](https://github.com/datacommonsorg/mixer/pull/1988), [mixer#2000](https://github.com/datacommonsorg/mixer/pull/2000)).

CONFIGURATIONS & OPERATOR UPDATES:
- Vector Search Profiles: Support custom embedding profiles via --spanner_search_config_path ([mixer#2039](https://github.com/datacommonsorg/mixer/pull/2039)).

TRUE PLATFORM BUG FIXES (Fixes issues present in {prev_version}):
- Serving SQL Optimization: Unroll SQL array parameters for size <= 10 to resolve latency spikes ([mixer#1993](https://github.com/datacommonsorg/mixer/pull/1993)).

[INTRA-RELEASE FIXES EXCLUDED FROM PUBLIC NOTES: mixer#2025, mixer#2070]

--------------------------------------------------------------------------------
2. COMPONENT: MCP Agent Toolkit & FastMCP Tools (datacommonsorg/agent-toolkit)
   Container Image: gcr.io/datcom-ci/datacommons-services (MCP binary)
--------------------------------------------------------------------------------

SALIENT FEATURES & CAPABILITIES (vs. {prev_version}):
- FastMCP Agent Integration: Exposes get_multi_entity_observations tool and indicator search with custom_only/base_only target scopes ([agent-toolkit#211](https://github.com/datacommonsorg/agent-toolkit/pull/211), [agent-toolkit#212](https://github.com/datacommonsorg/agent-toolkit/pull/212)).

TRUE PLATFORM BUG FIXES (Fixes issues present in {prev_version}):
- Agent API Protocol: Updated V2AgentGetObservations to HTTP POST for large payload handling ([agent-toolkit#213](https://github.com/datacommonsorg/agent-toolkit/pull/213)).

--------------------------------------------------------------------------------
3. COMPONENT: Website UI & Exploration Tools (datacommonsorg/website)
   Container Image: gcr.io/datcom-ci/datacommons-services (Website binary)
--------------------------------------------------------------------------------

SALIENT FEATURES & CAPABILITIES (vs. {prev_version}):
- Download Tool Redesign: Enhanced export interface for custom variable datasets ([website#6411](https://github.com/datacommonsorg/website/pull/6411)).
- Croissant Dataset Metadata: Inject Croissant JSON-LD for dataset indexing ([website#6443](https://github.com/datacommonsorg/website/pull/6443)).

TRUE PLATFORM BUG FIXES (Fixes issues present in {prev_version}):
- Place Browser Duplication: Fixed duplicate place rendering when multiple provenances exist ([website#6474](https://github.com/datacommonsorg/website/pull/6474)).

--------------------------------------------------------------------------------
4. COMPONENT: Data Preprocessor
   Container Image: gcr.io/datcom-ci/datacommons-data
--------------------------------------------------------------------------------
...
```

Confirm when `IMAGE_DELTAS_<new_version>.txt` has been written cleanly.
