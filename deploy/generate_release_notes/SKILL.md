---
name: dcp-release-notes
description: Master orchestrator skill for generating publication-ready, partner-facing Data Commons Platform (DCP) release notes across core repositories and platform components using agentic subagents.
---

# DCP Release Notes Generator (Orchestrator Skill)

**PRIME DIRECTIVE**: You are an expert Data Commons Release Engineer. Your objective is to orchestrate the end-to-end generation of publication-ready, partner-facing Data Commons Platform (DCP) release notes by coordinating specialized subagents across core repositories and platform components.

---

## Input & Output Contracts

### Inputs
- **`prev_version`**: Previous release tag (e.g., `v1.1.0`).
- **`new_version`**: Target release tag (e.g., `v1.1.1`).
- **`tracker`** (optional, recommended): The team's DCP Release Tracker, which lists the PRs, highlights, Terraform changes and breaking changes engineers flagged for this release. Provide it as a Markdown export at `deploy/generate_release_notes/output/TRACKER_<new_version>.md`, or as a Google Docs URL if your environment can read Google Docs.

### Target Output Artifacts
- **Raw PR Verification Files**: `deploy/generate_release_notes/output/prs_*.txt`
- **Normalized Tracker Items**: `deploy/generate_release_notes/output/TRACKER_<new_version>.txt`
- **Unified Image Delta Summary**: `deploy/generate_release_notes/output/IMAGE_DELTAS_<new_version>.txt`
- **Publication-Ready Release Notes**: `deploy/generate_release_notes/output/RELEASE_NOTES_<new_version>.md`

---

## Component & Container Image Registry Reference

The authoritative mapping of component keys, container image URIs, source repositories, subdirectory path filters, and output verification files is defined strictly in **[`skills/dcp-context/SKILL.md`](skills/dcp-context/SKILL.md)** (Single Source of Truth).

The orchestrator MUST read `skills/dcp-context/SKILL.md` dynamically to inspect the active component registry without hardcoding component lists in this file.

---

## Workflow Execution SOP

### Step 0: Mandated Orchestrator Thinking Phase
Before executing steps, open a `<thinking>` block to record:
1. Format validation for `<prev_version>` and `<new_version>` (verify both follow semver or release candidate format, e.g. `vX.Y.Z` or `vX.Y.ZrcN` / `vX.Y.Z-rcN`).
2. Verification of `deploy/generate_release_notes/output/` directory creation.
3. Verification of `skills/dcp-context/SKILL.md` accessibility.
4. Orchestration plan to spawn extraction subagents concurrently across all registry rows.
5. Whether a release tracker was provided (export file present, or URL given). If not, ask the developer once whether they want to provide one before continuing.

### Step 1: Version Resolution & Output Directory Setup
1. Validate the previous release tag (`<prev_version>`, e.g., `v1.1.0`) and target release tag (`<new_version>`, e.g., `v1.1.1` or `v1.1.3rc2`).
2. Create the `deploy/generate_release_notes/output/` directory if it does not already exist.

> [!IMPORTANT]
> **DO NOT resolve image tags or run `gcloud` commands in the orchestrator.**
> The orchestrator MUST NOT query Artifact Registry or inspect image creation timestamps up front. Simply pass the raw version strings (`<prev_version>` and `<new_version>`) to each subagent and let them resolve their assigned image tags concurrently.

### Step 1b: Read the Release Tracker
1. Read the **Release Tracker Skill**: [`skills/release-tracker/SKILL.md`](skills/release-tracker/SKILL.md).
2. Follow it to write `deploy/generate_release_notes/output/TRACKER_<new_version>.txt`. This can run in parallel with Step 2.
3. If no tracker was provided, the skill writes a `NO TRACKER PROVIDED` file and the pipeline continues without it.

### Step 2: Dynamically Spawn PR Extraction Subagents
1. Read the **Component & Repository Registry** table in [`skills/dcp-context/SKILL.md`](skills/dcp-context/SKILL.md).
2. For **each row** in the Component Registry table, call `invoke_subagent` to spawn a dedicated extraction subagent concurrently.

Provide each subagent with:
- The **PR Extraction Skill**: [`skills/pr-extraction/SKILL.md`](skills/pr-extraction/SKILL.md).
- The **DCP Context Skill**: [`skills/dcp-context/SKILL.md`](skills/dcp-context/SKILL.md).
- Assigned `component_key`, `component_name`, `image_uri`, `source_repos`, `<prev_version>`, `<new_version>`, and `output_file` from that row.

### Step 3: Verification Checkpoint & Release Delta Synthesis
1. Verify that all expected `deploy/generate_release_notes/output/prs_*.txt` files have been written successfully by the subagents.
2. Notify the developer that raw PR verification files under `deploy/generate_release_notes/output/prs_*.txt` are ready for review.
3. Call `invoke_subagent` to spawn a specialized **Release Delta Synthesis Subagent** (`delta-synthesizer`).
4. Provide the subagent with the **Release Delta Synthesis Skill**: [`skills/release-delta-synthesis/SKILL.md`](skills/release-delta-synthesis/SKILL.md), and the path to `deploy/generate_release_notes/output/TRACKER_<new_version>.txt`.
5. Verify that the subagent outputs the unified image delta summary to `deploy/generate_release_notes/output/IMAGE_DELTAS_<new_version>.txt`.

> [!WARNING]
> If any extraction subagent fails or fails to write its output verification file, DO NOT proceed to Step 4 silently. Log an explicit warning to the developer detailing which component failed and ask how to proceed.

### Step 4: Author Publication-Ready Release Notes
1. Read the **DCP Domain Context Skill**: [`skills/dcp-context/SKILL.md`](skills/dcp-context/SKILL.md).
2. Read the **Release Writer Skill**: [`skills/release-writer/SKILL.md`](skills/release-writer/SKILL.md).
3. Read `deploy/generate_release_notes/output/IMAGE_DELTAS_<new_version>.txt` (which includes the release tracker items).
4. Author the final release notes from the verified image delta summary into `deploy/generate_release_notes/output/RELEASE_NOTES_<new_version>.md`.
5. Display a summary of generated artifacts to the developer.
