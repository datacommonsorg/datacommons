# Data Commons Platform Documentation

The Data Commons Platform (DCP) documentation directory is the central home for platform architecture, conceptual guides, developer tutorials, and operational manuals.

---

## 1. Documentation Architecture & Principles

To keep technical knowledge clear, maintainable, and discoverable, documentation in this repository follows three core principles:

### A. Centralized Architecture & Guides in `docs/`
All conceptual systems design, data flow diagrams, architectural invariants, and hands-on tutorials live under `docs/`. This keeps the repository root clean and ensures that anyone looking to understand *how the platform works* knows exactly where to look.

### B. Actionable, Command-Focused Local `README.md` Files
Subsystem and module directories (such as [infra/dcp/README.md](../infra/dcp/README.md), [deploy/README.md](../deploy/README.md), and [packages/datacommons-cli/README.md](../packages/datacommons-cli/README.md)) contain localized, operational READMEs. 
* Local READMEs must focus on practical execution: quickstart commands, active configuration variables, input and output references, and local testing instructions.
* Local READMEs should avoid multi-page theoretical essays. Instead, they should link directly to the corresponding technical specifications in `docs/architecture/` or `docs/`.

### C. Strict Persona Separation
Documentation in this repository serves two distinct audiences:
* **DCP Admins (Platform Operators)**: External data stewards, DevOps teams, and organization administrators deploying and operating a Data Commons instance to serve custom datasets.
  * *Primary Document*: [user_guide.md](user_guide.md).
  * *Boundary*: The Admin User Guide focuses purely on instance configuration, dataset preparation, and ingestion operations. Do not include internal developer onboarding or local development recipes in the Admin User Guide.
* **DCP Developers (Platform Contributors)**: Engineers contributing to the codebase, creating new Cloud Run services or jobs, debugging Spanner queries, or tuning CLI logic.
  * *Primary Documents*: [docs/codelabs/](codelabs/), [docs/architecture/](architecture/), and [../CONTRIBUTING.md](../CONTRIBUTING.md).

---

## 2. Documentation Map (Directory Index)

| Category | File | Target Audience | What It Covers |
| :--- | :--- | :--- | :--- |
| **Admin Operations** | [user_guide.md](user_guide.md) | DCP Admins | Comprehensive operational manual for deploying instances, preparing CSV/MCF datasets, configuring `config.json`, and triggering ingestion workflows. |
| **Developer Guide** | [developer_guide.md](developer_guide.md) | DCP Developers | Canonical workbench manual for monorepo package layout, `uv workspace` linking, local development recipes, and testing strategy. |
| **Developer Onboarding** | [codelabs/dcp_developer_onboarding.md](codelabs/dcp_developer_onboarding.md) | New Developers | Zero-to-hero hands-on tutorial. Covers Terraform and GCP basics, CLI scaffolding, deploying an instance, touring every provisioned GCP resource in the console, seeding tables, running ingestion, and clean teardown. |
| **Architecture** | [architecture/platform_architecture.md](architecture/platform_architecture.md) | All Contributors | Deep dive into the 4-repository topology, container image roles, and the complete end-to-end ingestion and serving data flows. |
| **Architecture** | [architecture/terraform_stack.md](architecture/terraform_stack.md) | Infrastructure Contributors | Deep dive into the Terraform module hierarchy (Root to Stack to Submodules), variable propagation pipelines, resource naming standards, and cross-module IAM wiring. |
| **Architecture** | [architecture/admin_cli.md](architecture/admin_cli.md) | CLI & Tooling Contributors | Deep dive into the `datacommons admin` CLI architecture, local state vs remote GCS state modes, the CLI source regex contract, and state-driven operation choreography. |
| **Database Schemas** | [schema_migrations_developer_guide.md](schema_migrations_developer_guide.md) | Database Contributors | Guide for writing, testing, and applying Cloud Spanner schema migrations and DDL scripts. |
| **Release Management** | [release.md](release.md) | Release Managers | Official 3-stage release candidate workflow (TestPyPI staging, GitHub main bump PR, lockstep PyPI publishing). |
| **Release Cheatsheet** | [../deploy/README.md](../deploy/README.md) | Release Managers & CI/CD | Operational cheatsheet for Cloud Build pipelines (`staging.yaml`, `bump_version.yaml`, `release.yaml`) and release scripts. |
| **Infrastructure Reference** | [../infra/dcp/README.md](../infra/dcp/README.md) | Operators & Contributors | Operational cheatsheet for `infra/dcp/`: execution commands, active variable references matching `terraform.tfvars.template`, and outputs. |
| **CLI Reference** | [../packages/datacommons-cli/README.md](../packages/datacommons-cli/README.md) | CLI Users & CI/CD | Full command reference (`init`, `init-db`, `migrate-db`, `seed-db`, `ingest start`), flag definitions, and execution cheatsheets. |

---

## 3. Directory Layout Standards

When contributing new documentation, place your files according to this structure:

```
docs/
├── README.md                            # This file (documentation standards and index)
├── developer_guide.md                   # Canonical workbench manual for DCP developers
├── user_guide.md                        # Master manual for DCP Admins
├── schema_migrations_developer_guide.md # Spanner database migration guide
├── release.md                           # Platform release engineering guide
│
├── codelabs/                            # Interactive, step-by-step tutorials
│   └── dcp_developer_onboarding.md      # Hands-on developer onboarding codelab
│
└── architecture/                        # Deep-dive system specifications
    ├── platform_architecture.md         # Big-picture platform and data flows
    ├── terraform_stack.md               # Terraform stack architecture and IAM
    └── admin_cli.md                     # Admin CLI architecture and Terraform integration
```


---

## 4. Documentation Writing Guidelines

All documentation should follow plain engineering writing principles:
1. **Standard Nomenclature with Plain Intuition**: Use established industry terms (`Hit@K`, `p99 Latency`, `Partitioned DML`, `ACID Transactions`), but explain their practical meaning in plain, direct English before diving into data or code.
2. **Actionable Structure**: Place takeaways and prerequisites at the top. Use numbered sequences for workflows and clear Markdown tables for options and comparisons.
3. **Punctuation and Typography**: Use colons, commas, or parentheses instead of em dashes or en dashes. Avoid decorative emojis in technical documentation.
4. **Link Integrity**: Use relative file links (e.g. `[user_guide.md](user_guide.md)` or `[infra/dcp/](../infra/dcp/README.md)`) to guarantee portability across developer workstations and GitHub viewers. Avoid hardcoding absolute local paths.
