---
name: dcp-pr-extraction
description: Subagent instruction skill for extracting, filtering, and verifying merged Pull Requests for assigned container images and repositories.
---

# DCP PR Extraction & Image Verification Skill (Subagent Skill)

This skill provides step-by-step instructions for an individual subagent to extract merged Pull Requests for its assigned container image(s) and repository path(s), filter noise/regressions, and write a human-readable verification `.txt` file.

---

## Input Parameters Provided by Orchestrator
When invoked, you will receive the following parameters:
- **`component_name`**: Human-readable component name (e.g. `Core Services (Website, Mixer, MCP Agent)`).
- **`image_uri`**: Container Image URI in Artifact Registry (e.g. `gcr.io/datcom-ci/datacommons-services`).
- **`source_repos`**: List of source repositories and path filters to extract PRs from.
- **`prev_version`**: Previous release tag (e.g. `v1.1.0`).
- **`new_version`**: Target release tag (e.g. `v1.1.1`).
- **`output_file`**: Output file path (e.g. `deploy/generate_release_notes/output/prs_services.txt`).

---

## Execution Steps

### 1. Container Image Tag & Timestamp Resolution
1. Resolve the creation timestamp for `<prev_version>` and `<new_version>` for your assigned `image_uri`:
   ```bash
   gcloud container images list-tags <image_uri> --filter="tags:<version>" --format="value(timestamp.datetime)"
   ```
2. If an image tag is missing (e.g. during staging before image tagging), set `t_new` to the current time `NOW()`.

### 2. Single Date-Range PR Search per Repository
For each assigned source repository, execute a single `gh pr list` query spanning `[t_prev .. t_new]`:
```bash
gh pr list --repo <repo_name> --state merged --search "merged:<t_prev>..<t_new>" --json number,title,body,author,url,labels,files,mergedAt --limit 200
```
*(IMPORTANT: Do NOT pass `base:main` inside `--search`; use `--search "merged:<t_prev>..<t_new>"` directly to prevent GitHub Search API parse errors!)*

### 3. DCP Context & Semantic Content Analysis
1. **Read DCP Context Skill**: Before analyzing PRs, you MUST read [`deploy/generate_release_notes/skills/dcp-context/SKILL.md`](file:///Users/calinc/datcom-datacommons/deploy/generate_release_notes/skills/dcp-context/SKILL.md) to understand how your assigned component fits into the platform architecture.
2. **Analyze PR Content**: Analyze the actual content of each PR (title, description body, labels, and changed code context) against the DCP context to evaluate relevance:
   - **Data Preprocessor (`preprocessing` / `datacommons-data`)**: Include PRs affecting CSV/MCF parsing, streaming JSON-LD batching, schema validation, column mapping, or preprocessor execution.
   - **Dataflow Ingestion Worker (`dataflow_worker`)**: Include PRs affecting Dataflow pipelines, TFRecord loading, BigQuery/Spanner graph transformations, or batch import scaling (`max_workers`).
   - **Ingestion Helper Service (`ingestion_helper`)**: Include PRs affecting Cloud Workflows orchestration, ingestion status tracking, execution IDs, status polling, or run history tables.
   - **Postprocessing Helper Service (`postprocessing`)**: Include PRs affecting graph postprocessing rollups, StatVar/Place/Entity aggregations, Data-Point Vectors (DPVs), or pre-computed summary stores.
   - **Core Services (`services` / `datacommons-services`)**: Include PRs affecting serving APIs (Mixer gRPC, SDMX 3.0 REST, MCP agent tools, `/v2/observation`), vector embeddings, or Website Explore UI tools.
   - **DCP Monorepo & Infra (`dcp_monorepo`)**: Include PRs affecting Terraform modules, Admin CLI tools (`datacommons admin`), or deployment infrastructure.

### 4. Noise, Base DC, and Regression Categorization
Categorize every PR into either **Relevant PRs** or **Excluded PRs**:
1. **Relevant PRs**: Direct partner/operator features, configuration capabilities, or true platform bug fixes.
2. **Excluded PRs**:
   - **Base DC Only / Flag Flips**: PRs that only affect internal Google-hosted Base DC or internal flag flips without platform impact.
   - **Intermediate Regressions**: Bug fix PRs that address features/code introduced within the same release window (`[t_prev..t_new]`).
   - **Bot & Non-Production Chores**: Dependabot bumps, automated version bumps, unit/integration test harness refactors, or test sample data removals.

### 5. Write Verification File (`prs_<component>.txt`)
Format and write the extracted PRs into your assigned `output_file`, including an **Irrelevant / Excluded PRs** section at the bottom for developer audit.

For each relevant PR, provide:
1. **Change Summary**: Concise description of what changed in the code.
2. **DCP Impact**: Direct impact on platform operators, developers, or end-users.

```
================================================================================
Component: {component_name}
Image URI: {image_uri}
Release Range: {prev_version} ({t_prev}) -> {new_version} ({t_new})
Total Relevant PRs: {relevant_count} | Total Excluded PRs: {excluded_count}
================================================================================

--- RELEVANT PRODUCTION PRS ---

[{repo_short}#{number}] {title} (Author: {author} | Merged: {merged_at})
- Change Summary: {1-2 sentence summary of what changed in this PR}
- DCP Impact: {1-2 sentence explanation of user capability, API contract, or operator benefit}

[{repo_short}#{number}] {title} (Author: {author} | Merged: {merged_at})
- Change Summary: {1-2 sentence summary of what changed in this PR}
- DCP Impact: {1-2 sentence explanation of user capability, API contract, or operator benefit}

================================================================================
--- IRRELEVANT / EXCLUDED PRS (AUDIT LOG) ---
================================================================================

[{repo_short}#{number}] {title}
Reason: Excluded - Base DC-only flag flip / internal feature toggle

[{repo_short}#{number}] {title}
Reason: Excluded - Intermediate regression fix for PR {parent_pr_id} merged in current release window

[{repo_short}#{number}] {title}
Reason: Excluded - Unit test harness refactor / test sample data update
```

Confirm when your assigned verification file has been written cleanly to `output_file`.
