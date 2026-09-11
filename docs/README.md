# Data Commons Platform Documentation

The Data Commons Platform (DCP) documentation directory is the central home for platform architecture, conceptual guides, developer tutorials, and operational manuals.

---

## Documentation Principles and Standards

To keep technical knowledge maintainable, discoverable, and accurate over time, all documentation in this repository follows four core principles:

### 1. Centralized Architecture and Actionable Local READMEs
* All conceptual systems design, data flow diagrams, architectural invariants, and hands-on tutorials live centrally under `docs/`.
* Subsystem and module directories (such as [infra/dcp/](../infra/dcp/README.md), [deploy/](../deploy/README.md), and [packages/datacommons-cli/](../packages/datacommons-cli/README.md)) contain concise, operational READMEs focused strictly on practical execution: quickstart commands, configuration references, and local testing instructions.
* Local READMEs link directly to corresponding technical specifications in `docs/architecture/` rather than repeating architectural essays.

### 2. Strict Persona Separation
* **DCP Admins (Platform Operators)**: External data stewards, DevOps teams, and organization administrators deploying and operating a Data Commons instance to serve custom datasets. Their dedicated manual is [user_guide.md](user_guide.md).
* **DCP Developers (Platform Contributors)**: Engineers contributing to the codebase, creating new Cloud Run services or jobs, debugging Spanner queries, or tuning CLI logic. Everything else in this repository serves this developer persona.

### 3. Maintainability and Single Source of Truth
* **Document Contracts, Not Implementation Details**: Documentation explains system boundaries, architectural invariants, and why components interact. Duplicating volatile details that code already defines (such as default configuration values, schema definitions, or exhaustive lists of fields and flags) introduces immediate rot risk as implementations evolve.
* **Point to Relevant Code**: Rather than transcribing implementation details into markdown tables or prose, link directly to the relevant and illustrative code. When code evolves, the documentation remains accurate because it explains the concept and directs readers to the source for the specifics.

### 4. Reproducibility and Plain Engineering Writing
* **Runnable Commands**: All CLI and shell snippets must be directly reproducible, with environment variables (`$PROJECT_ID`, `$INSTANCE_NAME`) explicitly declared before use.
* **Link Integrity**: Use relative file links (such as `[developer_guide.md](developer_guide.md)`) to guarantee portability across developer workstations and GitHub viewers.
* **Direct Phrasing**: Use active voice, clear headings, and established technical terms. Avoid decorative emojis, em dashes, and empty filler words.
