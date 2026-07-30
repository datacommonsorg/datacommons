---
name: dcp-pr-extraction
description: Instructions for extracting, filtering, and verifying merged Pull Requests per container image across Data Commons repositories for release notes generation.
---

# DCP PR Extraction & Image Verification Skill

This skill provides step-by-step instructions for extracting merged Pull Requests across all 6 Data Commons repositories and mapping them to their corresponding container images and components.

---

## Component & Image Source Rules

| Component Key | Component Name | Container Image URI / Artifact | Source Repos & Path Filters |
| :--- | :--- | :--- | :--- |
| `services` | Core Services (Website, Mixer, MCP Agent) | `gcr.io/datcom-ci/datacommons-services` | `datacommonsorg/website`<br>`datacommonsorg/mixer`<br>`datacommonsorg/agent-toolkit` |
| `preprocessing` | Data Preprocessor | `gcr.io/datcom-ci/datacommons-data` | `datacommonsorg/import` (filter: `simple/`) |
| `dataflow_worker` | Dataflow Ingestion Worker | `us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion` | `datacommonsorg/import` (filter: `pipeline/ingestion/`) |
| `ingestion_helper` | Ingestion Helper Service | `gcr.io/datcom-ci/datacommons-ingestion-helper` | `datacommonsorg/import` (filter: `pipeline/workflow/ingestion-helper/`) |
| `postprocessing` | Postprocessing Helper Service | `gcr.io/datcom-ci/datacommons-aggregation-helper` | `datacommonsorg/import` (filter: `pipeline/workflow/aggregation-helper/`) |
| `dcp` | DCP Monorepo & Terraform Infra | DCP Monorepo | `datacommonsorg/datacommons` |

---

## Extraction Steps

### 1. Image Tag & Timestamp Resolution
1. For each container image URI above, resolve the creation timestamp of `<prev_version>` and `<new_version>`:
   ```bash
   gcloud container images list-tags <image_uri> --filter="tags:<version>" --format="value(timestamp.datetime)"
   ```
2. If an image tag is missing (e.g. during staging before image tagging), set `t_new` to the current time `NOW()`.

### 2. Single Date-Range PR Search per Repository
For each repository, run a single `gh pr list` query spanning `[t_prev .. t_new]`:
```bash
gh pr list --repo <repo_name> --state merged --search "merged:<t_prev>..<t_new>" --json number,title,body,author,url,labels,files,mergedAt --limit 200
```
*(IMPORTANT: Do NOT pass `base:main` inside `--search`; use `--search "merged:<t_prev>..<t_new>"` directly to prevent GitHub Search API parse errors!)*

### 3. Intermediate Regression & Noise Filtering
1. **Filter Out Bot & Non-Production PRs**:
   - Exclude Dependabot, Renovate, and automated version bumps (`"bump version"`, `datacommons-robot-author`).
   - Exclude test-only PRs (unit/integration test harnesses, hermetic test refactors, test-only sample data, or benchmark fixtures).
2. **Filter Out Intermediate Release-Window Regressions**:
   - If a bug fix PR addresses a feature or code modified *within the same release window* (`[t_prev..t_new]`), mark it as an internal regression and DO NOT include it in public Bug Fixes!

### 4. Write Verification Files (`prs_<component>.txt`)
Write clean, human-readable verification text files to `deploy/generate_release_notes/output/`:

Format for each file:
```
================================================================================
Component: Core Services (Website, Mixer, MCP Agent)
Image URI: gcr.io/datcom-ci/datacommons-services
Release Range: v1.1.0 (2026-06-22) -> v1.1.1 (2026-07-28)
Total PRs: 86
================================================================================

[mixer#2027] Support containedInPlace+ expansion in SDMX availability queries
Author: calinc | Merged: 2026-07-23T10:11:31Z
URL: https://github.com/datacommonsorg/mixer/pull/2027
Files Changed: internal/server/sdmx/availability.go

[agent-toolkit#211] Query bilateral entity observations through get_multi_entity_observations tool
Author: calinc | Merged: 2026-07-21T18:00:00Z
URL: https://github.com/datacommonsorg/agent-toolkit/pull/211
Files Changed: src/datacommons_mcp/tools.py
```
