# Data Commons Platform (DCP) Release Notes Generator

An agentic, skill-driven tool suite for generating publication-ready, partner-facing release notes for Data Commons Platform (DCP) releases.

---

## Quick Start (How to Use)

Simply point your LLM coding assistant (e.g. Antigravity / Gemini) at [`SKILL.md`](SKILL.md):

> **Prompt Example**:
> *"Please read `deploy/generate_release_notes/SKILL.md` and generate release notes for version v1.1.0 to v1.1.1."*

---

## How It Works (4 Automated Steps)

1. **PR Extraction**: The agent spawns dedicated subagents to query merged Pull Requests across all Data Commons repositories for each component layer within the release window (`[prev_version .. new_version]`).
2. **Developer Verification Checkpoint**: The agent generates human-readable text files per component under `output/prs_*.txt`. You can open and inspect these files to verify extracted PRs, change summaries, DCP impact, and excluded noise.
3. **Release Delta Synthesis**: An agent analyzes the verified PR lists to distinguish true platform bug fixes present in prior releases from intermediate intra-release fixes, generating `output/IMAGE_DELTAS_<version>.txt`.
4. **Final Release Notes Authoring**: The agent applies domain context and release-writing guidelines to generate the final publication-ready release notes: `output/RELEASE_NOTES_<version>.md`.

---

## Output Artifacts & Verification

All output artifacts are generated into `deploy/generate_release_notes/output/`:

- `output/prs_<component>.txt`: Extracted PRs per component with **Change Summary**, **DCP Impact**, and an **Excluded PRs Audit Log** (with explicit reasons for every ignored PR).
- `output/IMAGE_DELTAS_<version>.txt`: Intermediate summary of salient features, configuration updates, and true platform bug fixes per container image.
- `output/RELEASE_NOTES_<version>.md`: Final release notes formatted for external developers and instance operators.

---

## Architecture & Skill Reference

The pipeline is organized into modular skill instruction sets under `deploy/generate_release_notes/`:

```
deploy/generate_release_notes/
├── SKILL.md                          <-- 1. Master Orchestrator Skill (Entrypoint)
├── skills/
│   ├── pr-extraction/
│   │   └── SKILL.md                  <-- 2. PR Extraction Skill (Subagent Extraction)
│   ├── release-delta-synthesis/
│   │   └── SKILL.md                  <-- 3. Release Delta Synthesis Skill (Image Delta Analysis)
│   ├── dcp-context/
│   │   └── SKILL.md                  <-- 4. DCP Domain Context & Architectural Map (Single Source of Truth)
│   └── release-writer/
│       └── SKILL.md                  <-- 5. Partner-Facing Release Notes Writer
└── output/                            <-- Verification & Output Directory
```

### Skill Breakdown:
- **Orchestrator (`SKILL.md`)**: Coordinates subagents across component layers and manages the step-by-step workflow.
- **PR Extraction (`skills/pr-extraction/SKILL.md`)**: Instructions for date-range `gh pr list` queries, Artifact Registry tag resolution (with prompt on missing tags), and noise filtering.
- **Release Delta Synthesis (`skills/release-delta-synthesis/SKILL.md`)**: Rules for image delta synthesis, separating Mixer, MCP Agent Toolkit, and Website UI into dedicated sections.
- **DCP Domain Context (`skills/dcp-context/SKILL.md`)**: **Single Source of Truth** for component keys, repository mappings, subdirectory path filters, container image URIs, and persona guidelines.
- **Release Writer (`skills/release-writer/SKILL.md`)**: Guidelines for authoring publication-ready release notes with dynamic Executive Summary scaling and two-tier feature formatting (**What's New** + **Specific Capabilities** with `[repo#PR](URL)` links).
