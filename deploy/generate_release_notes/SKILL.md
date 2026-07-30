---
name: dcp-release-notes
description: Master orchestrator skill for generating publication-ready, partner-facing Data Commons Platform (DCP) release notes across all 6 core repositories using agentic subagents.
---

# DCP Release Notes Generator (Orchestrator Skill)

This skill orchestrates the end-to-end generation of publication-ready, partner-facing release notes for the Data Commons Platform (DCP). It coordinates specialized subagents to extract PRs per container image, write human-readable verification `.txt` files for developer review, apply domain context, and author concise release notes.

---

## Component & Container Image Registry

| Component Key | Component Name | Container Image URI / Artifact | Source Repos & Content Focus | Output Verification File |
| :--- | :--- | :--- | :--- | :--- |
| `services` | Core Services (Website, Mixer, MCP Agent) | `gcr.io/datcom-ci/datacommons-services` | `datacommonsorg/website`<br>`datacommonsorg/mixer`<br>`datacommonsorg/agent-toolkit`<br>*(Serving APIs, SDMX 3.0, FastMCP, UI)* | `output/prs_services.txt` |
| `preprocessing` | Data Preprocessor | `gcr.io/datcom-ci/datacommons-data` | `datacommonsorg/import`<br>*(CSV/MCF validation, JSON-LD streaming batching)* | `output/prs_preprocessing.txt` |
| `dataflow_worker` | Dataflow Ingestion Worker | `us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion` | `datacommonsorg/import`<br>*(Dataflow pipelines, TFRecord loading, Spanner graph transforms)* | `output/prs_dataflow_worker.txt` |
| `ingestion_helper` | Ingestion Helper Service | `gcr.io/datcom-ci/datacommons-ingestion-helper` | `datacommonsorg/import`<br>*(Cloud Workflows status tracking, run history tables)* | `output/prs_ingestion_helper.txt` |
| `postprocessing` | Postprocessing Helper Service | `gcr.io/datcom-ci/datacommons-aggregation-helper` | `datacommonsorg/import`<br>*(Graph postprocessing rollups, StatVar/Place aggregations, summary store)* | `output/prs_postprocessing.txt` |
| `dcp_monorepo` | DCP Monorepo & Terraform Infra | DCP Monorepo | `datacommonsorg/datacommons`<br>*(Terraform modules, Admin CLI, deployment infra)* | `output/prs_dcp_monorepo.txt` |

---

## Workflow Instructions

When requested to generate release notes (e.g., *"Generate release notes for v1.1.0 to v1.1.1"*):

### Step 1: Version Resolution & Output Directory Setup
1. Identify the previous release tag (`<prev_version>`, e.g., `v1.1.0`) and target release tag (`<new_version>`, e.g., `v1.1.1`).
2. Ensure `deploy/generate_release_notes/output/` directory exists.

### Step 2: Spawn PR Extraction Subagents
Call `invoke_subagent` to spawn subagents concurrently across the components above. 

Provide each subagent with:
1. The **PR Extraction Skill**: [`deploy/generate_release_notes/skills/pr-extraction/SKILL.md`](file:///Users/calinc/datcom-datacommons/deploy/generate_release_notes/skills/pr-extraction/SKILL.md).
2. The **DCP Context Skill**: [`deploy/generate_release_notes/skills/dcp-context/SKILL.md`](file:///Users/calinc/datcom-datacommons/deploy/generate_release_notes/skills/dcp-context/SKILL.md).
3. Its assigned **Component Name**, **Image URI**, **Source Repos**, `<prev_version>`, `<new_version>`, and target **Output Verification File**.

#### Subagent Tasks:
- **Subagent 1 (`services-extractor`)**: Extract PRs for `gcr.io/datcom-ci/datacommons-services` from `website`, `mixer`, `agent-toolkit` $\rightarrow$ write `output/prs_services.txt`.
- **Subagent 2 (`import-extractor`)**: Extract PRs for `import` repo for preprocessor, Dataflow worker, ingestion helper, and postprocessing helper $\rightarrow$ write `output/prs_preprocessing.txt`, `output/prs_dataflow_worker.txt`, `output/prs_ingestion_helper.txt`, `output/prs_postprocessing.txt`.
- **Subagent 3 (`monorepo-extractor`)**: Extract PRs for `datacommonsorg/datacommons` monorepo & Terraform infra $\rightarrow$ write `output/prs_dcp_monorepo.txt`.

### Step 3: Verification Checkpoint & Release Delta Synthesis Subagent
1. Notify the developer that raw PR verification files have been generated under `deploy/generate_release_notes/output/prs_*.txt` for review.
2. Call `invoke_subagent` to spawn a specialized **Release Delta Synthesis Subagent** (`delta-synthesizer`).
3. Provide the subagent with the **Release Delta Synthesis Skill**: [`deploy/generate_release_notes/skills/release-delta-synthesis/SKILL.md`](file:///Users/calinc/datcom-datacommons/deploy/generate_release_notes/skills/release-delta-synthesis/SKILL.md).
4. The subagent will:
   - Read all `output/prs_*.txt` files.
   - Investigate and distinguish true bug fixes present in `<prev_version>` vs. intermediate bug fixes introduced and fixed within `<new_version>` (omitting intra-release fixes).
   - Summarize salient features and configuration updates per container image relative to `<prev_version>`.
   - Output the unified image delta summary to: `deploy/generate_release_notes/output/IMAGE_DELTAS_<new_version>.txt`.

### Step 4: Author Publication-Ready Release Notes
1. Read the **DCP Domain Context Skill**: [`deploy/generate_release_notes/skills/dcp-context/SKILL.md`](file:///Users/calinc/datcom-datacommons/deploy/generate_release_notes/skills/dcp-context/SKILL.md).
2. Read the **Release Writer Skill**: [`deploy/generate_release_notes/skills/release-writer/SKILL.md`](file:///Users/calinc/datcom-datacommons/deploy/generate_release_notes/skills/release-writer/SKILL.md).
3. Read `deploy/generate_release_notes/output/IMAGE_DELTAS_<new_version>.txt`.
4. Author the final release notes from the verified image delta summary into: `deploy/generate_release_notes/output/RELEASE_NOTES_<new_version>.md`.
