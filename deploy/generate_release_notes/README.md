# Data Commons Platform (DCP) Release Notes Generator

An agentic, skill-driven tool suite for generating publication-ready, partner-facing release notes for the Data Commons Platform (DCP).

The tool automatically extracts merged Pull Requests across all 6 core Data Commons repositories, classifies them according to standard SOP categories, filters out internal test noise and regressions, writes human-verifiable PR lists per container image (`output/prs_<component>.txt`), and formats concise release notes tailored for developers and platform operators building on top of DCP.

---

## Agentic Skill Suite Architecture

The release notes generation pipeline is structured into 4 modular `SKILL.md` instruction sets. Point your LLM agent at these skills to execute the generation process:

```
deploy/generate_release_notes/
├── SKILL.md                          <-- 1. Master Orchestrator Skill (Entrypoint)
├── skills/
│   ├── pr-extraction/
│   │   └── SKILL.md                  <-- 2. PR Extraction & Image Tag Resolution Skill
│   ├── dcp-context/
│   │   └── SKILL.md                  <-- 3. DCP Domain Context & Architectural Map
│   └── release-writer/
│       └── SKILL.md                  <-- 4. Partner-Facing Release Notes Writer
└── output/                            <-- Verification & Output Directory
    ├── prs_services.txt              <-- Verified PRs for Core Services (Website, Mixer, MCP)
    ├── prs_preprocessing.txt         <-- Verified PRs for Data Preprocessor (datacommons-data)
    ├── prs_dataflow_worker.txt       <-- Verified PRs for Dataflow Worker
    ├── prs_ingestion_helper.txt      <-- Verified PRs for Ingestion Helper
    ├── prs_postprocessing.txt        <-- Verified PRs for Postprocessing Helper
    ├── prs_dcp_monorepo.txt          <-- Verified PRs for DCP Monorepo & Infra
    └── RELEASE_NOTES_v1.1.1.md       <-- Final Publication-Ready Release Notes
```

---

## Developer Usage Instructions (Prompting Your LLM Agent)

### Step 1: Point Your LLM Agent at the Orchestrator Skill
To generate release notes for a release range, point your LLM agent at [`deploy/generate_release_notes/SKILL.md`](file:///Users/calinc/datcom-datacommons/deploy/generate_release_notes/SKILL.md):

> **Prompt Example**:
> *"Please read `deploy/generate_release_notes/SKILL.md` and generate release notes for version v1.1.0 to v1.1.1."*

### Step 2: PR Extraction & Intermediate Verification Files
Your LLM agent will follow the PR extraction skill (`skills/pr-extraction/SKILL.md`) to:
1. Resolve container image tags across Artifact Registry via `gcloud`.
2. Query merged Pull Requests across all 6 Data Commons repositories via `gh pr list`.
3. Filter out non-production test fixtures and intermediate release-window regressions.
4. Output human-verifiable text files per container image into `deploy/generate_release_notes/output/`:
   - `prs_services.txt` (Core Services: Website, Mixer, MCP Agent)
   - `prs_preprocessing.txt` (Data Preprocessor: `datacommons-data`)
   - `prs_dataflow_worker.txt` (Dataflow Ingestion Worker)
   - `prs_ingestion_helper.txt` (Ingestion Helper Service)
   - `prs_postprocessing.txt` (Postprocessing Aggregation Helper)
   - `prs_dcp_monorepo.txt` (DCP Monorepo & Terraform Infra)

Developers can open and inspect these `.txt` files to verify that all relevant PRs for each image are correctly captured before the final release notes are written.

### Step 3: Domain Context & Final Writing
Your LLM agent will load the domain context (`skills/dcp-context/SKILL.md`) and author the final release notes according to `skills/release-writer/SKILL.md`, outputting:
`deploy/generate_release_notes/output/RELEASE_NOTES_<new_version>.md`

---

## Modular Skill Breakdown

### 1. Orchestrator Skill (`SKILL.md`)
The master entrypoint skill that coordinates subagent execution, manages the step-by-step pipeline, and ensures intermediate verification files are generated before writing the final release notes.

### 2. PR Extraction Skill (`skills/pr-extraction/SKILL.md`)
Contains exact commands and rules for `gcloud container images list-tags` resolution, date-range `gh pr list` queries, non-production test filtering, and intermediate regression exclusion.

### 3. DCP Domain Context Skill (`skills/dcp-context/SKILL.md`)
Defines the architectural map across all 6 core repositories (`datacommons`, `website`, `mixer`, `agent-toolkit`, `import`) and enforces strict **External Contracts & Operator Capabilities** vs. **Zero Internal Implementation Mechanics** (no internal database table names or DDLs).

### 4. Release Writer Skill (`skills/release-writer/SKILL.md`)
Defines the non-verbose, partner-facing GFM format:
- **Executive Summary**: 1 single sentence (max 25 words).
- **Key Feature Updates**: **What's New** (1 paragraph combining description + benefit) followed by **Specific Capabilities** (bullet points with `[repo#PR](URL)` links).
- **Improvements & Configuration Updates**: Bullet points extracting concrete enums (`custom_only`, `base_only`) and scaling limits (`max_workers`).
- **Bug Fixes**: 3–5 high-level functional categories (Deployment, Ingestion, Serving APIs, UI).

---

## Standalone CLI Execution (Python Pipeline)

Alternatively, for non-LLM or CI/CD automated environments, run the standalone Python CLI tool:

```bash
uv run --group generate-release-notes python -m deploy.generate_release_notes \
  --prev v1.1.0 \
  --new v1.1.1 \
  --allow-missing-images \
  --manifest-out ./output/manifest_v1.1.1.json \
  --out ./output/RELEASE_NOTES_v1.1.1.md
```

### CLI Options Reference:
| Flag / Option | Type | Description |
| :--- | :--- | :--- |
| `--prev` | `STRING` | Previous release version tag (e.g. `v1.1.0`). |
| `--new` | `STRING` | Target release version tag (e.g. `v1.1.1`). |
| `--out`, `-o` | `PATH` | Output markdown file path (default: `./RELEASE_NOTES_<new>.md`). |
| `--allow-missing-images` | `BOOLEAN` | Bypass missing container image tag errors during staging. |
| `--manifest-out` | `PATH` | Export JSON manifest mapping all PRs to their container image URIs. |
| `--include-audit-log` | `BOOLEAN` | Append raw PR audit log table at the bottom of the release notes. |

---

## Repository Mapping

| Repository | Scope / Path Filter | Target Component & Image |
| :--- | :--- | :--- |
| `datacommonsorg/datacommons` | All PRs (`infra/dcp/`, `packages/`) | DCP Monorepo & Infra (`dcp`) |
| `datacommonsorg/website` | All PRs (excluding `cdc_data/`) | Core Services (`services`) $\rightarrow$ `gcr.io/datcom-ci/datacommons-services` |
| `datacommonsorg/mixer` | All PRs (`internal/server/`, `proto/`, `deploy/`) | Core Services (`services`) $\rightarrow$ `gcr.io/datcom-ci/datacommons-services` |
| `datacommonsorg/agent-toolkit` | All PRs (`src/datacommons_mcp/`) | Core Services (`services`) $\rightarrow$ `gcr.io/datcom-ci/datacommons-services` |
| `datacommonsorg/import` | `simple/` | Data Preprocessor (`preprocessing`) $\rightarrow$ `gcr.io/datcom-ci/datacommons-data` |
| `datacommonsorg/import` | `pipeline/ingestion/` | Dataflow Worker (`dataflow_worker`) $\rightarrow$ Dataflow Templates |
| `datacommonsorg/import` | `pipeline/workflow/ingestion-helper/` | Ingestion Helper (`ingestion_helper`) $\rightarrow$ `datacommons-ingestion-helper` |
| `datacommonsorg/import` | `pipeline/workflow/aggregation-helper/` | Postprocessing Helper (`postprocessing`) $\rightarrow$ `datacommons-aggregation-helper` |
