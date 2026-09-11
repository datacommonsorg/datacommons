# Data Commons Platform Documentation

The Data Commons Platform (DCP) documentation directory is the central home for platform architecture, conceptual guides, developer tutorials, and operational manuals.

---

## Documentation Principles and Standards

To keep technical knowledge maintainable, discoverable, and accurate over time, all documentation in this repository follows four core principles:

### 1. Centralized Architecture and Actionable Local READMEs
* All conceptual systems design, data flow diagrams, architectural invariants, and hands-on tutorials live centrally under `docs/`.
* Subsystem and module directories (such as [infra/dcp/](../infra/dcp/README.md), [deploy/](../deploy/README.md), and [packages/datacommons-cli/](../packages/datacommons-cli/README.md)) contain concise, operational READMEs focused strictly on practical execution: quickstart commands, active configuration tables, and local testing instructions.
* Local READMEs link directly to corresponding technical specifications in `docs/architecture/` rather than repeating architectural essays.

### 2. Strict Persona Separation
* **DCP Admins (Platform Operators)**: External data stewards, DevOps teams, and organization administrators deploying and operating a Data Commons instance to serve custom datasets. Their dedicated manual is [user_guide.md](user_guide.md).
* **DCP Developers (Platform Contributors)**: Engineers contributing to the codebase, creating new Cloud Run services or jobs, debugging Spanner queries, or tuning CLI logic. Everything else in this repository serves this developer persona.

### 3. Maintainability and Staleness Prevention (Code Pointers over Shadowed Defaults)
* **High-Level Invariants vs. Volatile Details**: Documentation must resist rot by decoupling prose from rapidly changing implementation details. If a developer makes an architectural change (such as adding a service or altering the distributed lock protocol), updating the corresponding architecture document is an obvious and expected part of that PR.
* **Avoid Shadowing Code Defaults**: Never duplicate volatile implementation details in markdown prose or tables (such as specific default variable values, struct definitions, or enum lists). A developer bumping a default value in [variables.tf](../infra/dcp/variables.tf) or updating a protobuf field will not, and should not have to, hunt down markdown tables to synchronize duplicate numbers.
* **Link to the Canonical Source of Truth**: Point directly to the highest-level source file (such as [variables.tf](../infra/dcp/variables.tf), [terraform.tfvars.template](../infra/dcp/terraform.tfvars.template), or [workflow.yaml](../infra/dcp/modules/ingestion/workflow/workflow.yaml)) as the authoritative reference for complete lists and active defaults. The documentation explains *how* and *why* components interact, leaving specific default values to the code itself.

### 4. Reproducibility and Plain Engineering Writing
* **Runnable Commands**: All CLI and shell snippets must be directly reproducible, with environment variables (`$PROJECT_ID`, `$NAMESPACE`) explicitly declared before use.
* **Link Integrity**: Use relative file links (such as `[developer_guide.md](developer_guide.md)`) to guarantee portability across developer workstations and GitHub viewers.
* **Direct Phrasing**: Use active voice, clear headings, and established technical terms. Avoid decorative emojis, em dashes, and empty filler words.
