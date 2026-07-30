---
name: dcp-release-notes
description: Master orchestrator skill for generating publication-ready, partner-facing Data Commons Platform (DCP) release notes across all 6 core repositories using agentic subagents.
---

# DCP Release Notes Generator (Orchestrator Skill)

This skill orchestrates the end-to-end generation of publication-ready, partner-facing release notes for the Data Commons Platform (DCP). It Coordinates specialized subagents to extract PRs per container image, verify PR lists with the developer in human-readable `.txt` files, apply domain context, and author concise release notes.

---

## Workflow Instructions

When the user asks to generate release notes (e.g., *"Generate release notes for v1.1.0 to v1.1.1"*):

### Step 1: Target Version Resolution
1. Identify the previous release tag (`<prev_version>`, e.g., `v1.1.0`) and target release tag (`<new_version>`, e.g., `v1.1.1`).
2. Create the output directory `deploy/generate_release_notes/output/` if it does not exist.

### Step 2: PR Extraction & Image Verification (Concurrent Subagent Spawning)
1. Read the **PR Extraction Skill**: [SKILL.md](file:///Users/calinc/datcom-datacommons/deploy/generate_release_notes/skills/pr-extraction/SKILL.md).
2. **Mandatory Subagent Spawning**: Call `invoke_subagent` to spawn 3 concurrent subagents in parallel:
   - **Subagent 1 (`services-extractor`)**: Extract PRs for `website`, `mixer`, `agent-toolkit` $\rightarrow$ write `deploy/generate_release_notes/output/prs_services.txt`.
   - **Subagent 2 (`import-extractor`)**: Extract PRs for `import` repo across `simple/`, `pipeline/ingestion/`, and `pipeline/workflow/` $\rightarrow$ write `prs_preprocessing.txt`, `prs_dataflow_worker.txt`, `prs_ingestion_helper.txt`, `prs_postprocessing.txt`.
   - **Subagent 3 (`monorepo-extractor`)**: Extract PRs for `datacommons` monorepo & Terraform infra $\rightarrow$ write `prs_dcp_monorepo.txt`.

3. Each subagent will use `gcloud` and `gh` CLI commands to:
   - Resolve Artifact Registry image tags (`gcr.io/datcom-ci/datacommons-services`, `datacommons-data`, etc.).
   - Execute date-range PR queries (`gh pr list --search "merged:<t_prev>..<t_new>"`) across their assigned repositories.
   - Filter out Dependabot, automated version bumps, and non-production test fixtures.
   - Deterministically detect intermediate release-window regressions.
   - Output human-verifiable text files per container image into `deploy/generate_release_notes/output/`.

4. Inform the developer that PR verification files are written in `deploy/generate_release_notes/output/` for review.

### Step 3: Load Domain Context & Architectural Principles
1. Read the **DCP Domain Context Skill**: [SKILL.md](file:///Users/calinc/datcom-datacommons/deploy/generate_release_notes/skills/dcp-context/SKILL.md).
2. Ensure strict adherence to:
   - **External Contracts & Operator Capabilities**: Focus strictly on APIs, Terraform variables, CLI commands, and operator capabilities.
   - **Zero Internal Implementation Mechanics**: Never output internal database table names (e.g., KeyValueStore, DDLs, schema cutovers).

### Step 4: Author Publication-Ready Release Notes
1. Read the **Release Writer Skill**: [SKILL.md](file:///Users/calinc/datcom-datacommons/deploy/generate_release_notes/skills/release-writer/SKILL.md).
2. Synthesize the verified PR lists from `deploy/generate_release_notes/output/prs_*.txt` into the final release notes document: `deploy/generate_release_notes/output/RELEASE_NOTES_<new_version>.md`.
3. Format according to the streamlined template:
   - **Executive Summary**: 1 single sentence (max 25 words).
   - **Key Feature Updates**: Non-verbose format (**What's New**: 1 paragraph combining description + benefit, followed by **Specific Capabilities**: bullets with `[repo#PR](URL)` links, NO horizontal rule dividers between features).
   - **Improvements & Configuration Updates**: Bullet points extracting concrete enums (`custom_only`, `base_only`) and scaling limits (`max_workers`).
   - **Bug Fixes**: 3–5 high-level functional categories (Deployment, Ingestion, Serving APIs, UI).
