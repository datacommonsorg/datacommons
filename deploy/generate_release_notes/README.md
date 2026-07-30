# Data Commons Platform (DCP) Release Notes Generator

An agentic, multi-repository tool for generating publication-ready, partner-facing release notes for the Data Commons Platform (DCP).

The tool automatically extracts merged Pull Requests across all 6 core Data Commons repositories, classifies them according to standard SOP categories using Gemini 3.6 Flash, filters out internal test noise and regressions, and formats concise release notes tailored for developers and platform operators building on top of DCP.

---

## Architecture Overview

The tool operates as a structured 3-step pipeline:

```
┌─────────────────────────┐     ┌──────────────────────────────┐     ┌────────────────────────────┐
│   Step 1: PR Extractor   │ ───►│  Step 2: Feature Extractor   │ ───►│ Step 3: Release Notes Writer│
│ (gh CLI + gcloud tags)  │     │   (Gemini 3.6 Flash LLM)     │     │   (Gemini 3.6 Flash GFM)   │
└─────────────────────────┘     └──────────────────────────────┘     └────────────────────────────┘
```

1. **Step 1: PR Extractor (`pr_extractor.py`)**: Resolves container image tags across Artifact Registry (`gcr.io/datcom-ci/datacommons-services`, `datacommons-data`, etc.) and Git tags. Queries GitHub CLI (`gh pr list`) in a single date-range search per repository to fetch all merged PRs between versions.
2. **Step 2: Feature Extractor (`feature_extractor.py`)**: Uses Gemini 3.6 Flash to filter out Dependabot PRs, test-only refactors, and intermediate release-window regressions (via deterministic file diff footprint matching). Synthesizes remaining PRs into structured `FeatureUpdate` objects categorized under:
   - **Spanner Graph & APIs** (SDMX 3.0 REST endpoints, `/v2/observation`, Mixer gRPC, MCP tools)
   - **Ingestion & Safety** (Dataflow workers, workflow orchestration, preprocessor, health probes)
   - **Search & Website** (Vector embeddings, search scope targeting, Website UI)
   - **Infra & Tooling** (Terraform modules, Admin CLI, monorepo versioning)
3. **Step 3: Release Notes Writer (`release_notes_writer.py`)**: Renders publication-ready GitHub Flavored Markdown (GFM) using the **"So What?" Rule**, strict **Anti-AI-Fluff Word Budgets**, side-by-side **DO vs. DON'T guidelines**, and clickable `[repo#PR](URL)` links.

---

## Prerequisites

Before running the tool, ensure you have the following installed and authenticated:

1. **Python 3.11+** and [`uv`](https://github.com/astral-sh/uv) (or `pip`).
2. **GitHub CLI (`gh`)**: Must be installed and authenticated to read pull requests:
   ```bash
   gh auth status
   # If not authenticated:
   gh auth login
   ```
3. **Google Cloud SDK (`gcloud`)**: Must be authenticated to query Artifact Registry image tags:
   ```bash
   gcloud auth list
   # If not authenticated:
   gcloud auth login
   gcloud auth application-default login
   ```
4. **Gemini API Key or GCP Credentials**:
   ```bash
   export GEMINI_API_KEY="your_gemini_api_key_here"
   ```

---

## Typical Usage Commands

### 1. Basic Production Release Notes Generation
Generate release notes between two published release tags (e.g. `v1.1.0` and `v1.1.1`):
```bash
uv run --group generate-release-notes python -m deploy.generate_release_notes \
  --prev v1.1.0 \
  --new v1.1.1 \
  --out ./RELEASE_NOTES_v1.1.1.md
```

### 2. Pre-Release / Staging Generation (Allow Missing Images)
Generate release notes for a staging release before container images have been tagged in Artifact Registry (extends search window to current time `NOW()`):
```bash
uv run --group generate-release-notes python -m deploy.generate_release_notes \
  --prev v1.1.0 \
  --new v1.1.1 \
  --allow-missing-images \
  --out ./RELEASE_NOTES_v1.1.1.md
```

### 3. Including High-Priority Release Highlights / Additional Instructions
Provide custom context or release highlights via a markdown file:
```bash
uv run --group generate-release-notes python -m deploy.generate_release_notes \
  --prev v1.1.0 \
  --new v1.1.1 \
  --additional-instructions ./release_highlights.md \
  --out ./RELEASE_NOTES_v1.1.1.md
```

### 4. Generating Release Notes with Full Audit Log Table
Include an append-only PR audit table at the bottom cross-referencing all 50+ processed PRs:
```bash
uv run --group generate-release-notes python -m deploy.generate_release_notes \
  --prev v1.1.0 \
  --new v1.1.1 \
  --include-audit-log \
  --out ./RELEASE_NOTES_v1.1.1.md
```

---

## Command-Line Options & Flags

| Flag / Option | Type | Required | Description |
| :--- | :--- | :---: | :--- |
| `--prev` | `STRING` | **Yes** | Previous release version tag (e.g. `v1.1.0`). |
| `--new` | `STRING` | **Yes** | Target release version tag (e.g. `v1.1.1`). |
| `--out`, `-o` | `PATH` | No | Path to write output markdown file (default: `./RELEASE_NOTES_<new>.md`). |
| `--allow-missing-images` | `BOOLEAN` | No | Bypass errors if container image tags are missing in Artifact Registry and extend date range to current time `NOW()`. |
| `--synthesis-model` | `STRING` | No | Gemini model to use for feature extraction & writing (default: `gemini-3.6-flash`). |
| `--additional-instructions` | `STRING/PATH` | No | Path to a markdown file or raw text containing high-priority user instructions or release highlights. |
| `--include-audit-log` | `BOOLEAN` | No | Append an audit log table mapping all raw PRs to their release classification status. |
| `--use-cache / --no-cache` | `BOOLEAN` | No | Enable or disable local disk caching for GitHub PR queries (default: `True`). |
| `--help` | `FLAG` | No | Display CLI help and exit. |

---

## Configuration & Component Registry (`config.py`)

The tool's multi-repository mappings, image URIs, and source rules are centrally configured in [`config.py`](file:///Users/calinc/datcom-datacommons/deploy/generate_release_notes/config.py).

### Core Data Structures in `config.py`:

1. **`SourceRule`**: Defines a GitHub repository and an optional sub-directory `path_filter` for mapping monorepo or multi-repo PRs:
   ```python
   SourceRule(repo="datacommonsorg/import", path_filter="simple/")
   ```
2. **`ComponentConfig`**: Configures a tracked release component:
   - `id`: Internal component key (e.g. `services`, `preprocessing`).
   - `name`: Human-readable display name.
   - `artifact_type`: Artifact category (`dcp_platform`, `docker_services`, `docker_data`, `dataflow_template`, `docker_ingestion_helper`, `docker_postprocessing`).
   - `image_uri`: Primary container image URI in Google Artifact Registry or GCR (e.g. `gcr.io/datcom-ci/datacommons-services`).
   - `default_tag_prefix`: Version tag prefix (e.g. `"v"` for `v1.1.1`).
   - `sources`: List of contributing `SourceRule` objects.

### Master `COMPONENTS` Registry:

```python
COMPONENTS: Dict[str, ComponentConfig] = {
    "dcp": ComponentConfig(
        id="dcp",
        name="DCP Monorepo & Infra (CLI, Admin, DB, Terraform)",
        artifact_type="dcp_platform",
        image_uri=None,
        default_tag_prefix="v",
        sources=[SourceRule(repo="datacommonsorg/datacommons")],
    ),
    "services": ComponentConfig(
        id="services",
        name="Core Services (Website, Mixer, MCP)",
        artifact_type="docker_services",
        image_uri="gcr.io/datcom-ci/datacommons-services",
        default_tag_prefix="v",
        sources=[
            SourceRule(repo="datacommonsorg/website"),
            SourceRule(repo="datacommonsorg/mixer"),
            SourceRule(repo="datacommonsorg/agent-toolkit"),
        ],
    ),
    "preprocessing": ComponentConfig(
        id="preprocessing",
        name="Data Preprocessor (datacommons-data)",
        artifact_type="docker_data",
        image_uri="gcr.io/datcom-ci/datacommons-data",
        default_tag_prefix="v",
        sources=[SourceRule(repo="datacommonsorg/import", path_filter="simple/")],
    ),
    "dataflow_worker": ComponentConfig(
        id="dataflow_worker",
        name="Dataflow Ingestion Worker",
        artifact_type="dataflow_template",
        image_uri="us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion",
        default_tag_prefix="v",
        sources=[SourceRule(repo="datacommonsorg/import", path_filter="pipeline/ingestion/")],
    ),
    "ingestion_helper": ComponentConfig(
        id="ingestion_helper",
        name="Ingestion Helper Service",
        artifact_type="docker_ingestion_helper",
        image_uri="gcr.io/datcom-ci/datacommons-ingestion-helper",
        default_tag_prefix="v",
        sources=[SourceRule(repo="datacommonsorg/import", path_filter="pipeline/workflow/ingestion-helper/")],
    ),
    "postprocessing": ComponentConfig(
        id="postprocessing",
        name="Postprocessing Aggregation Helper Service",
        artifact_type="docker_postprocessing",
        image_uri="gcr.io/datcom-ci/datacommons-aggregation-helper",
        default_tag_prefix="v",
        sources=[SourceRule(repo="datacommonsorg/import", path_filter="pipeline/workflow/aggregation-helper/")],
    ),
}
```

To add a new component or track an additional repository, simply define a new `ComponentConfig` in [`config.py`](file:///Users/calinc/datcom-datacommons/deploy/generate_release_notes/config.py).

---

## Repository Coverage

The tool automatically tracks and correlates PRs across all 6 core Data Commons repositories:

| Repository | Scope / Path Filter | Target Component |
| :--- | :--- | :--- |
| `datacommonsorg/datacommons` | All PRs (`infra/dcp/`, `packages/`) | DCP Monorepo & Infra (`dcp`) |
| `datacommonsorg/website` | All PRs (excluding `cdc_data/`) | Core Services (`services`) |
| `datacommonsorg/mixer` | All PRs (`internal/server/`, `proto/`, `deploy/`) | Core Services (`services`) |
| `datacommonsorg/agent-toolkit` | All PRs (`src/datacommons_mcp/`) | Core Services (`services`) |
| `datacommonsorg/import` | `simple/` | Data Preprocessor (`preprocessing`) |
| `datacommonsorg/import` | `pipeline/ingestion/` | Dataflow Worker (`dataflow_worker`) |
| `datacommonsorg/import` | `pipeline/workflow/ingestion-helper/` | Ingestion Helper (`ingestion_helper`) |
| `datacommonsorg/import` | `pipeline/workflow/aggregation-helper/` | Postprocessing Helper (`postprocessing`) |

---

## Development & Testing

Run the unit test suite (excludes live network/GitHub integration tests):
```bash
uv run pytest deploy/generate_release_notes/tests/ -m "not integration" -v
```

Run the full test suite (including live GitHub integration tests):
```bash
uv run pytest deploy/generate_release_notes/tests/ -v
```
