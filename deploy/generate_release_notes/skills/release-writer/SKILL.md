---
name: dcp-release-writer
description: Instructions for authoring publication-ready, partner-facing Data Commons Platform (DCP) release notes using GFM markdown.
---

# DCP Release Notes Writer Skill

This skill provides step-by-step instructions for authoring non-verbose, publication-ready, partner-facing release notes in GitHub Flavored Markdown (GFM).

---

## 1. Writing Style & Tone Constraints

- **Tone**: Direct, factual, punchy, senior-engineer technical changelog. Active voice for features ("You can now..."), past tense for bugs ("Resolved...").
- **BANNED AI FLUFF WORDS (STRICT)**: DO NOT use AI cliché words: `seamlessly`, `empower`, `leveraging`, `robust`, `overhaul`, `delivers a major`, `comprehensive`, `fosters`, `game-changing`, `cutting-edge`, `paradigm`.
- **STRICT WORD COUNT BUDGETS**:
  - **Executive Summary**: Maximum 25 words (1 single, punchy sentence).
  - **What's New**: Combine description and user benefit into 1 concise paragraph (25-35 words max).
  - **Specific Capabilities Bullets**: 12-15 words max per bullet.
- **GFM Link Rules**: Every PR reference MUST be a clean, clickable link: `[repo_short#PR](URL)`. NEVER wrap backticks around or inside link text (`[`repo#123`](URL)` is forbidden!).
- **NO Horizontal Dividers Between Features**: Do NOT place horizontal rule lines (`---`) between individual feature sections under Key Feature Updates. Use standard Markdown headers (`### Feature Title`) with single blank lines only!

---

## 2. Document Template & Section Structure

```markdown
# Data Commons Platform Release {new_version} ({release_date})

[Provide a high-impact, 1-sentence Executive Summary (max 25 words) highlighting the most important capabilities, performance boosts, and critical fixes introduced in this release for partners and platform operators.]

---

## Key Feature Updates

### [Feature Title]

**What's New**: [Clear 1-2 sentence description combining what changed and why it is important / user capability enabled.]

**Specific Capabilities**:
- [Actionable Use Case / Input Capability 1] ([repo_short#PR](URL))
- [Actionable Use Case / Input Capability 2] ([repo_short#PR](URL))

### [Next Feature Title]

**What's New**: [Clear 1-2 sentence description...]

**Specific Capabilities**:
- [Actionable Use Case / Input Capability 1] ([repo_short#PR](URL))

---

## Improvements & Configuration Updates

- **[Improvement Title]**: [Summary of update, step-by-step configuration instructions if required, and direct benefit] ([repo_short#PR](URL))
- **[Terraform & Scaling]**: [Concrete scaling parameters, enums like custom_only/base_only, max_workers, processing units] ([repo_short#PR](URL))

---

## Bug Fixes

- **[Deployment & Infrastructure]**: [Synthesized 1-2 sentence summary of deployment/IAM fixes] ([datacommons#163](URL), [datacommons#178](URL))
- **[Ingestion Pipeline Reliability]**: [Synthesized 1-2 sentence summary of workflow/preprocessor fixes] ([import#636](URL), [import#637](URL))
- **[Serving API & Query Robustness]**: [Synthesized 1-2 sentence summary of API/serving fixes] ([mixer#1995](URL), [mixer#2007](URL))
- **[Web UI & Visualization]**: [Synthesized 1-2 sentence summary of UI/Explore fixes] ([website#6411](URL), [website#6474](URL))
```

---

## 3. High-Level Bug Fix Grouping Rule

- **MAX 3–5 BULLETS TOTAL**: DO NOT output a laundry list of dozens of individual PRs!
- Group all raw bug fixes into 3 to 5 functional categories (*Deployment & Infrastructure*, *Ingestion Pipeline Reliability*, *Serving API & Query Robustness*, *Web UI & Visualization*).
- Combine all related PR links into the single grouped bullet point.
