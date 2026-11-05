---
name: dcp-release-tracker
description: Skill for reading the team's curated DCP Release Tracker (flagged PRs, highlights, Terraform changes, breaking changes) and normalizing the section for the target release into TRACKER_<new_version>.txt.
---

# DCP Release Tracker Skill (Curated Release Input)

**PRIME DIRECTIVE**: You are a Data Commons Release Engineer. Your objective is to read the section of the DCP Release Tracker that covers `<new_version>`, extract the items engineers flagged for the release notes, and write them to `deploy/generate_release_notes/output/TRACKER_<new_version>.txt` without rewording or dropping anything.

The tracker is a curated, human-maintained list. PR extraction finds *everything* that merged; the tracker says *what must be called out*. When the two disagree, the tracker wins on inclusion and the PR extraction wins on facts (titles, URLs, merge status).

---

## Input & Output Contracts

### Inputs
- **`<new_version>`**: Target release tag (e.g., `v1.1.8` or `v1.1.8rc1`).
- **Tracker source**, in order of preference:
  1. A Markdown export of the tracker at `deploy/generate_release_notes/output/TRACKER_<new_version>.md` (or any path the developer provides).
  2. A Google Docs URL provided by the developer, if your environment has a tool that can read Google Docs.

### Target Output Artifact
- **Normalized Tracker Items**: `deploy/generate_release_notes/output/TRACKER_<new_version>.txt`.

> [!NOTE]
> The tracker is optional. If no tracker source is available, write `TRACKER_<new_version>.txt` containing only the header and the line `NO TRACKER PROVIDED`, report this to the orchestrator, and stop. The rest of the pipeline then runs exactly as it did without a tracker.

---

## Tracker Structure

The tracker has one section per release, newest first. The upcoming release's heading looks like `▶ vX.Y.Z (upcoming)`; released versions look like `vX.Y.Z · Released <date>`. Each release section contains these subsections:

| Subsection | What it holds |
| --- | --- |
| Highlights for release notes | 3–5 partner-facing candidate bullets |
| User-facing Terraform changes | Table: Change, Variable / resource, Details, Customer action |
| Breaking changes and required actions | Bullets: what customers must do when upgrading |
| Flagged PRs | Table: PR, Repo, Area, Type, Release notes? (Highlight / Mention), Owner, Partner-facing summary |
| Full diff | Per-repo GitHub compare links (do not extract; PR extraction covers this) |
| Validation, Known issues, Release checklist | Release process (do not extract, except Known issues) |

---

## Execution SOP Sequence

### Step 1: Locate the Release Section
1. Strip any release-candidate suffix from `<new_version>` (`v1.1.8rc1` → `v1.1.8`).
2. Find the section whose heading contains that version. Ignore the template section at the end of the doc.
3. If no section matches, write `NO TRACKER SECTION FOR <version>` to the output file, report it to the orchestrator, and stop.

### Step 2: Extract Items Verbatim
Extract these subsections as-is. Skip empty rows, placeholder rows, and cells that only contain `TBD` or `—`.
1. **Highlights**: each bullet, with its PR links.
2. **User-facing Terraform changes**: each table row.
3. **Breaking changes and required actions**: each bullet, with its PR links.
4. **Flagged PRs**: each table row. Normalize every PR reference to `repo#number` plus its full GitHub URL (`https://github.com/datacommonsorg/<repo>/pull/<number>`).
5. **Known issues / carried over**: each bullet that isn't `TBD`.

> [!IMPORTANT]
> Do not reword, merge, or filter tracker items. Engineers added them deliberately. The Release Writer applies style rules later.

### Step 3: Write `TRACKER_<new_version>.txt`

```
================================================================================
DCP RELEASE TRACKER ITEMS: {new_version}
Source: {export path or doc URL}
Extracted Date: {date}
================================================================================

HIGHLIGHTS:
- {bullet text} ({repo#PR}: {URL}, ...)

USER-FACING TERRAFORM CHANGES:
- [{Change}] {Variable / resource}: {Details}. Customer action: {Customer action}

BREAKING CHANGES & REQUIRED ACTIONS:
- {bullet text} ({repo#PR}: {URL}, ...)

FLAGGED PRS:
- {repo#PR} ({URL}) | Area: {Area} | Type: {Type} | Release notes: {Highlight|Mention} | Owner: {Owner}
  Summary: {Partner-facing summary}

KNOWN ISSUES:
- {bullet text}
```

Write `NONE` under any heading with no items. Confirm to the orchestrator how many items were extracted per heading.
