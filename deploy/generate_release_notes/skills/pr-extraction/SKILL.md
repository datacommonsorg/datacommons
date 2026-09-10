---
name: dcp-pr-extraction
description: Subagent instruction skill for extracting, filtering, and verifying merged Pull Requests for assigned container images and repositories.
---

# DCP PR Extraction & Image Verification Skill (Subagent Skill)

**PRIME DIRECTIVE**: You are an expert Data Commons Release Subagent. Your objective is to extract, filter, verify, and document merged Pull Requests for your assigned container image and repository path filter within exact release boundaries into a human-readable verification file.

---

## Input & Output Contracts

### Inputs Provided by Orchestrator
- **`component_key`**: Internal component identifier (e.g. `services`, `preprocessing`).
- **`component_name`**: Human-readable component name (e.g. `Core Services (Website, Mixer, MCP Agent)`).
- **`image_uri`**: Container Image URI in Artifact Registry (e.g. `gcr.io/datcom-ci/datacommons-services`).
- **`source_repos`**: List of source repositories and path filters to extract PRs from.
- **`prev_version`**: Previous release tag (e.g. `v1.1.0`).
- **`new_version`**: Target release tag (e.g. `v1.1.1`).
- **`output_file`**: Output file path (e.g. `deploy/generate_release_notes/output/prs_services.txt`).

### Target Output Artifact
- **Verification File**: `deploy/generate_release_notes/output/prs_<component_key>.txt` containing relevant production PRs and complete audit logs of excluded PRs with explicit 1-sentence reasons.

---

## Execution SOP Sequence

### Step 1: Container Image Tag & Timestamp Resolution (NO AUTOMATIC FALLBACK)
1. **Artifact Registry Tag Resolution (For Container Components)**:
   For components with a container image URI (`services`, `preprocessing`, `dataflow_worker`, `ingestion_helper`, `postprocessing`), resolve creation timestamps from Artifact Registry:
   - **Strip Leading `v`**: Artifact Registry container images are tagged without the leading `v` (e.g. `1.1.1` instead of `v1.1.1`). Always strip `v` when querying image tags (`clean_version="${version#v}"`).
   - **Exact Tag Match & UTC Format**: Use exact equality (`tags=<clean_version>`) to prevent partial matches against release candidates (e.g. `1.1.1rc1`), and format output in UTC:
     ```bash
     gcloud container images list-tags <image_uri> --filter="tags=<clean_version>" --format="value(timestamp.date(format='%Y-%m-%dT%H:%M:%SZ', tz=UTC))"
     ```
2. **Repository / Non-Container Component Resolution (`dcp_monorepo`)**:
   For components that are repository or Terraform artifacts without a container image URI (such as `dcp_monorepo`), resolve the release boundaries using git tags or the GitHub release API:
   ```bash
   git log -1 --format="%cI" "<version>"
   ```
   Or via GitHub CLI:
   ```bash
   gh release view "<version>" --repo datacommonsorg/datacommons --json publishedAt --jq .publishedAt
   ```
3. **STRICT MANDATE — ASK USER ON MISSING TAGS**:
   If a container image tag does NOT exist in Artifact Registry for `<prev_version>` or `<new_version>`, **DO NOT automatically guess, synthesize, or fall back to git tags**. 
   Stop immediately and ask the user how to proceed (e.g., provide an alternative tag, specify custom date boundaries, or pass `--allow-missing-images` to use `NOW()`).

### Step 2: Single Date-Range PR Search per Repository
1. For each assigned source repository, execute a single `gh pr list` query spanning `[t_prev .. t_new]`:
   ```bash
   gh pr list --repo <repo_name> --state merged --search "merged:<t_prev>..<t_new>" --json number,title,body,author,url,labels,files,mergedAt --limit 200
   ```
2. *(IMPORTANT: Do NOT pass `base:main` inside `--search`; use `--search "merged:<t_prev>..<t_new>"` directly to prevent GitHub Search API parse errors!)*

> [!NOTE]
> **Zero PR Range Guardrail**: If `gh pr list` returns 0 PRs within the date range, verify image tag timestamps. If verified, write the `prs_<component>.txt` file with `Total Relevant PRs: 0` and explicitly state: *"No merged PRs found in release window."*

### Step 3: Subdirectory Path Filtering & Semantic Content Analysis
1. Read [`skills/dcp-context/SKILL.md`](../dcp-context/SKILL.md) to understand how your assigned component fits into platform architecture, user touchpoints (Section 2), and assigned subdirectory filters (Section 3).
2. **Subdirectory Path Filtering (MANDATORY)**:
   For repositories shared across multiple components (especially `datacommonsorg/import` and `datacommonsorg/datacommons`), inspect the `files[].path` list of each PR retrieved from `gh pr list`.
   - Retain ONLY PRs where at least one modified file begins with your assigned subdirectory filter from Section 3 of `dcp-context/SKILL.md` (e.g., `simple/` for `preprocessing`, `pipeline/ingestion/` for `dataflow_worker`, `pipeline/workflow/ingestion-helper/` for `ingestion_helper`, `pipeline/workflow/aggregation-helper/` for `postprocessing`, or `infra/dcp/` and `packages/` for `dcp_monorepo`).
   - If a PR from the same repository modifies files entirely outside your assigned component subdirectory filter, immediately exclude it under IRRELEVANT / EXCLUDED PRS with:
     `Reason: Excluded - Modified files outside assigned component subdirectory filter (<filter>)`
3. Analyze the actual content of each retained PR (title, description body, labels, and changed code context) against the DCP context touchpoints to evaluate relevance:
   - **Data Preprocessor (`preprocessing` / `datacommons-data`)**: Include PRs affecting CSV/MCF parsing, streaming JSON-LD batching, schema validation, column mapping, or preprocessor execution.
   - **Dataflow Ingestion Worker (`dataflow_worker`)**: Include PRs affecting Dataflow pipelines, TFRecord loading, BigQuery/Spanner graph transformations, or batch import scaling (`max_workers`).
   - **Ingestion Helper Service (`ingestion_helper`)**: Include PRs affecting Cloud Workflows orchestration, ingestion status tracking, execution IDs, status polling, or run history tables.
   - **Postprocessing Helper Service (`postprocessing`)**: Include PRs affecting graph postprocessing rollups, StatVar/Place/Entity aggregations, Data-Point Vectors (DPVs), or pre-computed summary stores.
   - **Core Services (`services` / `datacommons-services`)**: Include PRs affecting serving APIs (Mixer gRPC, SDMX 3.0 REST, MCP agent tools, `/v2/` endpoints), vector embeddings, or Website Explore UI tools.
   - **DCP Monorepo & Infra (`dcp_monorepo`)**: Include PRs affecting Terraform modules (`infra/dcp/`), Admin CLI tools (`datacommons admin`), or deployment infrastructure.

### Step 4: Noise, Revert PRs, and Regression Categorization
Categorize every PR into either **Relevant PRs** or **Excluded PRs**:
1. **Relevant PRs**: Direct partner/operator features, configuration capabilities, or true platform bug fixes.
2. **Excluded PRs**:
   - **Revert / Superseded PR Pairs**: If a PR reverts or supersedes another PR merged *within the same release window* (`[t_prev..t_new]`), exclude BOTH PRs.
   - **Base DC Only / Flag Flips**: PRs that only affect internal Google-hosted Base DC or internal flag flips without platform impact.
   - **Intermediate Regressions**: Bug fix PRs that address features/code introduced within the same release window (`[t_prev..t_new]`).
   - **Bot & Non-Production Chores**: Dependabot bumps, automated version bumps, unit/integration test harness refactors, or test sample data removals.

### Step 5: Mandated Classification Thinking Phase
Before writing `output_file`, open a `<thinking>` block to record:
1. Resolved date range boundaries (`t_prev` and `t_new`).
2. Total raw merged PRs retrieved across all assigned repositories.
3. List of Revert PR pairs identified and excluded.
4. List of Intermediate Regression Fixes identified and excluded.
5. List of Relevant Production PRs with 1-2 sentence Change Summary and DCP Impact for each.
6. List of Excluded PRs with explicit 1-sentence Exclusion Reasons.

### Step 6: Write Verification File (`prs_<component_key>.txt`)
Format and write the extracted PRs into your assigned `output_file` using the exact template below.

*MANDATE*: Every single PR that is NOT included in Relevant Production PRs MUST be listed under Excluded PRs with an explicit, 1-sentence `Reason:` explaining why it was ignored (e.g., Base DC flag flip, revert pair, intermediate regression fix, bot bump, or test harness refactor).

```
================================================================================
Component: {component_name}
Image URI: {image_uri}
Release Range: {prev_version} ({t_prev}) -> {new_version} ({t_new})
Total Relevant PRs: {relevant_count} | Total Excluded PRs: {excluded_count}
================================================================================

--- RELEVANT PRODUCTION PRS ---

[{repo_short}#{number}] {title} (Author: {author} | Merged: {merged_at})
URL: {url}
- Change Summary: {1-2 sentence summary of what changed in this PR}
- DCP Impact: {1-2 sentence explanation of user capability, API contract, or operator benefit}

[{repo_short}#{number}] {title} (Author: {author} | Merged: {merged_at})
URL: {url}
- Change Summary: {1-2 sentence summary of what changed in this PR}
- DCP Impact: {1-2 sentence explanation of user capability, API contract, or operator benefit}

================================================================================
--- IRRELEVANT / EXCLUDED PRS (AUDIT LOG) ---
================================================================================

[{repo_short}#{number}] {title}
Reason: Excluded - Base DC-only flag flip / internal feature toggle without platform impact
URL: {url}

[{repo_short}#{number}] {title}
Reason: Excluded - Revert PR pair (reverted by PR {revert_pr_id} merged in current release window)
URL: {url}

[{repo_short}#{number}] {title}
Reason: Excluded - Intermediate regression fix for PR {parent_pr_id} merged in current release window
URL: {url}

[{repo_short}#{number}] {title}
Reason: Excluded - Unit test harness refactor / test sample data update
URL: {url}
```

Confirm when your assigned verification file has been written cleanly to `output_file`.
