---
name: dcp-release-delta-synthesis
description: Subagent skill for analyzing raw PR verification files (prs_*.txt) and synthesizing image-level release deltas relative to the previously published release image.
---

# DCP Release Delta Synthesis Skill (Image Impact & Delta Analysis)

This skill provides step-by-step instructions for a subagent to analyze all raw PR verification files (`deploy/generate_release_notes/output/prs_*.txt`), evaluate component-level changes relative to the previously published container image, filter out intra-release intermediate bug fixes, and synthesize a unified `IMAGE_DELTAS_<new_version>.txt` document.

---

## Input & Output Files

- **Input Files**: `deploy/generate_release_notes/output/prs_*.txt` (`prs_services.txt`, `prs_preprocessing.txt`, `prs_dataflow_worker.txt`, `prs_ingestion_helper.txt`, `prs_postprocessing.txt`, `prs_dcp_monorepo.txt`).
- **Context Reference**: [`deploy/generate_release_notes/skills/dcp-context/SKILL.md`](file:///Users/calinc/datcom-datacommons/deploy/generate_release_notes/skills/dcp-context/SKILL.md).
- **Target Output File**: `deploy/generate_release_notes/output/IMAGE_DELTAS_<new_version>.txt`.

---

## Execution Steps

### 1. Read & Consolidate PR Verification Files
1. Read all `prs_*.txt` files from `deploy/generate_release_notes/output/`.
2. Group PRs by container image / component key (`services`, `preprocessing`, `dataflow_worker`, `ingestion_helper`, `postprocessing`, `dcp_monorepo`).

### 2. Intra-Release vs. Prior-Release Bug Fix Investigation
Perform deep investigation into every bug fix PR:
- **Intra-Release Intermediate Fix (EXCLUDE)**: Was the bug introduced by a feature/PR *merged within this current release window* (`[v_prev..v_new]`)? If so, exclude it! Platform users running `v_prev` were never exposed to this bug, so listing it creates noise.
- **Prior-Release True Fix (INCLUDE)**: Did the bug exist in the previously published container image (`v_prev` or earlier)? If so, synthesize it under true platform bug fixes for that component!

### 3. Synthesize Salient Image Deltas (Per Container Image)
For each container image / component, summarize the salient changes from the perspective of an operator upgrading from `<prev_version>` to `<new_version>`:

1. **Major Feature Capabilities Added**:
   - What new capabilities exist in this image that were not present in `<prev_version>`?
   - What new API endpoints, protocols (e.g. SDMX 3.0, FastMCP), or UI tools are now available?
2. **Configuration & Infra Updates**:
   - What new Terraform variables, CLI parameters (`--instance_name`), or environment variables were added?
   - What scaling bounds (`max_workers`, BigQuery slots) or memory optimizations were introduced?
3. **True Platform Bug Fixes**:
   - What issues present in `<prev_version>` were resolved in this container image?

---

## Output Document Structure (`IMAGE_DELTAS_<new_version>.txt`)

Write `deploy/generate_release_notes/output/IMAGE_DELTAS_<new_version>.txt` using the exact structure below:

```
================================================================================
DCP RELEASE DELTA SUMMARY: {prev_version} -> {new_version}
Generated Date: {date}
================================================================================

--------------------------------------------------------------------------------
1. COMPONENT: Core Services (Website, Mixer, MCP Agent)
   Container Image: gcr.io/datcom-ci/datacommons-services
--------------------------------------------------------------------------------

SALIENT FEATURES & CAPABILITIES (vs. {prev_version}):
- SDMX 3.0 REST Data & Availability Endpoints: Serves multi-entity observations in SDMX-CSV 2.0 format with facetId filtering and containedInPlace+ expansion ([mixer#1976], [mixer#1988], [mixer#2000]).
- FastMCP Agent Integration: Exposes get_multi_entity_observations tool and indicator search with custom_only/base_only target scopes ([agent-toolkit#211], [agent-toolkit#212]).

CONFIGURATION & OPERATOR UPDATES:
- Vector Search Profiles: Support custom embedding profiles via --spanner_search_config_path ([mixer#2039]).

TRUE PLATFORM BUG FIXES (Fixes issues present in {prev_version}):
- Serving SQL Optimization: Unroll SQL array parameters for size <= 10 to resolve latency spikes ([mixer#1993]).
- Place Browser Duplication: Fixed duplicate place rendering when multiple provenances exist ([website#6474]).

[INTRA-RELEASE FIXES EXCLUDED FROM PUBLIC NOTES: mixer#2025, mixer#2070]

--------------------------------------------------------------------------------
2. COMPONENT: Data Preprocessor
   Container Image: gcr.io/datcom-ci/datacommons-data
--------------------------------------------------------------------------------
...
```

Confirm when `IMAGE_DELTAS_<new_version>.txt` has been written cleanly.
