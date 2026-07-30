# Data Commons Platform (DCP) Release Notes Generator

An agentic, skill-driven tool suite for generating publication-ready, partner-facing release notes for the Data Commons Platform (DCP).

The tool automatically extracts merged Pull Requests across all 6 core Data Commons repositories, classifies them according to platform layer and technical impact, filters out internal test noise and regressions, writes human-verifiable PR lists per container image (`output/prs_<component>.txt`), and formats concise release notes tailored for developers and platform operators building on top of DCP.

---

## Agentic Skill Suite Architecture

The release notes generation pipeline is structured into 4 modular `SKILL.md` instruction sets. Point your LLM agent at these skills to execute the generation process:

```
deploy/generate_release_notes/
├── SKILL.md                          <-- 1. Master Orchestrator Skill (Entrypoint)
├── skills/
│   ├── pr-extraction/
│   │   └── SKILL.md                  <-- 2. PR Extraction Skill (Subagent Extraction)
│   ├── release-delta-synthesis/
│   │   └── SKILL.md                  <-- 3. Release Delta Synthesis Skill (Image Delta Analysis)
│   ├── dcp-context/
│   │   └── SKILL.md                  <-- 4. DCP Domain Context & Architectural Map
│   └── release-writer/
│       └── SKILL.md                  <-- 5. Partner-Facing Release Notes Writer
└── output/                            <-- Verification & Output Directory
    ├── prs_services.txt              <-- Verified PRs for Core Services (Website, Mixer, MCP)
    ├── prs_preprocessing.txt         <-- Verified PRs for Data Preprocessor (datacommons-data)
    ├── prs_dataflow_worker.txt       <-- Verified PRs for Dataflow Worker
    ├── prs_ingestion_helper.txt      <-- Verified PRs for Ingestion Helper
    ├── prs_postprocessing.txt        <-- Verified PRs for Postprocessing Helper
    ├── prs_dcp_monorepo.txt          <-- Verified PRs for DCP Monorepo & Infra
    ├── IMAGE_DELTAS_v1.1.1.txt       <-- Intermediate Image Delta Summary (Delta vs. Previous Release)
    └── RELEASE_NOTES_v1.1.1.md       <-- Final Publication-Ready Release Notes
```

---

## Developer Usage Instructions (Prompting Your LLM Agent)

### Step 1: Point Your LLM Agent at the Orchestrator Skill
To generate release notes for a release range, point your LLM agent at [`SKILL.md`](SKILL.md):

> **Prompt Example**:
> *"Please read `deploy/generate_release_notes/SKILL.md` and generate release notes for version v1.1.0 to v1.1.1."*

### Step 2: PR Extraction & Intermediate Verification Files
Your LLM agent will spawn concurrent subagents using `skills/pr-extraction/SKILL.md` and `skills/dcp-context/SKILL.md` to:
1. Resolve container image tags across Artifact Registry via `gcloud`.
2. Query merged Pull Requests across all 6 Data Commons repositories via `gh pr list`.
3. Analyze PR content, change summary, and DCP impact.
4. Output human-verifiable text files per container image into `deploy/generate_release_notes/output/prs_*.txt`.

Developers can open and inspect these `.txt` files to verify that all relevant PRs for each image are correctly captured, and inspect the **Irrelevant / Excluded PRs** audit log at the bottom.

### Step 3: Release Delta Synthesis (Delta vs. Previously Published Image)
Your LLM agent will spawn a **Release Delta Synthesis Subagent** using `skills/release-delta-synthesis/SKILL.md` to:
1. Analyze all `output/prs_*.txt` files.
2. Distinguish true platform bug fixes present in `<prev_version>` vs. intermediate bug fixes introduced and resolved within `<new_version>` (omitting intra-release fixes).
3. Summarize salient features and operator capabilities added to each container image relative to `<prev_version>`.
4. Output the intermediate delta summary file: `deploy/generate_release_notes/output/IMAGE_DELTAS_<new_version>.txt`.

### Step 4: Final Release Notes Authoring
Your LLM agent will load `skills/release-writer/SKILL.md` and author the publication-ready release notes:
`deploy/generate_release_notes/output/RELEASE_NOTES_<new_version>.md`

---

## Modular Skill Breakdown

### 1. Orchestrator Skill (`SKILL.md`)
The master entrypoint skill that coordinates subagent execution, manages the step-by-step pipeline, and ensures intermediate verification files are generated before writing the final release notes.

### 2. PR Extraction Skill (`skills/pr-extraction/SKILL.md`)
Contains exact commands and rules for `gcloud container images list-tags` resolution (with strict user prompt on missing tags), date-range `gh pr list` queries, non-production test filtering, and intermediate regression exclusion.

### 3. DCP Domain Context Skill (`skills/dcp-context/SKILL.md`)
Defines the architectural map across all 6 core repositories (`datacommons`, `website`, `mixer`, `agent-toolkit`, `import`) and enforces strict **External Contracts & Operator Capabilities** vs. **Zero Internal Implementation Mechanics** (no internal database table names or DDLs).

### 4. Release Writer Skill (`skills/release-writer/SKILL.md`)
Defines the non-verbose, partner-facing GFM format:
- **Dynamic Executive Summary**: Scales length dynamically with release size (2–3 sentences for major releases, 1 punchy sentence for patch releases).
- **Key Feature Updates**: **What's New** (1 paragraph combining description + benefit) followed by **Specific Capabilities** (bullet points with `[repo#PR](URL)` links).
- **Improvements & Configuration Updates**: Bullet points extracting concrete enums (`custom_only`, `base_only`) and scaling limits (`max_workers`).
- **Bug Fixes**: 3–5 high-level functional categories (Deployment, Ingestion, Serving APIs, UI).
