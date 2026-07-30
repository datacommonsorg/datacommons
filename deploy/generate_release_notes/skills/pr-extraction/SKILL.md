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

### 3. Path & Directory Filtering
If your assigned component specifies a path filter (e.g. `simple/` for preprocessor, `pipeline/ingestion/` for Dataflow worker, `pipeline/workflow/ingestion-helper/` for ingestion helper):
- Inspect `files[].path` for each PR.
- Keep ONLY PRs that modify files within your assigned path filter!

### 4. Noise & Intermediate Regression Filtering
1. **Filter Out Bot & Non-Production PRs**:
   - Exclude Dependabot, Renovate, and automated version bumps (`"bump version"`, `datacommons-robot-author`).
   - Exclude test-only PRs (unit/integration test harnesses, hermetic test refactors, test-only sample data, or benchmark fixtures).
2. **Filter Out Intermediate Release-Window Regressions**:
   - Check if a bug fix PR addresses a feature or code modified *within the same release window* (`[t_prev..t_new]`).
   - If it fixes an intermediate PR merged earlier in `[t_prev..t_new]`, tag it as an internal regression and DO NOT include it in public Bug Fixes!

### 5. Write Verification File (`prs_<component>.txt`)
Format and write the extracted PRs into your assigned `output_file`:

```
================================================================================
Component: {component_name}
Image URI: {image_uri}
Release Range: {prev_version} ({t_prev}) -> {new_version} ({t_new})
Total PRs Extracted: {count}
================================================================================

[{repo_short}#{number}] {title}
Author: {author} | Merged: {merged_at}
URL: {url}
Files Changed: {files_summary}

[{repo_short}#{number}] {title}
Author: {author} | Merged: {merged_at}
URL: {url}
Files Changed: {files_summary}
```

Confirm when your assigned verification file has been written cleanly to `output_file`.
