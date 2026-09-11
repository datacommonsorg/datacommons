# Contributing to the Data Commons Platform

The Data Commons Platform (DCP) welcomes contributions from developers, researchers, and data practitioners.

This document outlines how to get started as a developer, how our codebase and documentation are structured, and our guidelines for submitting pull requests.

---

## 1. Getting Started for Developers

If you are new to the Data Commons Platform, start with our hands-on developer onboarding codelab:
* **[Developer Onboarding Codelab](docs/codelabs/dcp_developer_onboarding.md)**: A step-by-step tutorial that walks you through cloud prerequisites, scaffolding an instance with the CLI, deploying test infrastructure with Terraform, inspecting resources in the Google Cloud Console, seeding the database, running data ingestion, and testing live API queries.
* **[Platform Architecture](docs/architecture/platform_architecture.md)**: An overview of the 4-repository topology, container artifacts, and end-to-end data flows.

### Developer Tooling Prerequisites

To build, test, and contribute to this repository, install the following tools:
* **Python (v3.11+)**: Required for core packages.
* **[uv](https://docs.astral.sh/uv/)**: Fast Python project manager. Used to manage monorepo virtual environments, dependencies, and package execution.
* **[Terraform](https://developer.hashicorp.com/terraform/install) (v1.5+)**: Infrastructure as Code tool used to manage GCP resources in `infra/dcp/`.
* **[gcloud CLI](https://cloud.google.com/sdk/docs/install-sdk)**: Google Cloud SDK for project authentication and cloud resource management.

---

## 2. Repository Structure

This repository is organized as a monorepo containing multiple Python packages, Terraform infrastructure configurations, and centralized documentation:

```
datcom-datacommons/
├── packages/                            # Python monorepo packages managed via uv
│   ├── datacommons-cli/                 # User-facing CLI entrypoint (datacommons)
│   ├── datacommons-admin/               # Administrative logic, scaffolding, and cloud client wrappers
│   ├── datacommons-db/                  # Database models, Spanner client (DCGraph), migrations
│   ├── datacommons-api/                 # API service components
│   └── datacommons-schema/              # Schema definitions and data model utilities
│
├── infra/
│   └── dcp/                             # Terraform modules for provisioning GCP infrastructure
│       ├── main.tf                      # Root Terraform configuration
│       ├── variables.tf                 # Root variable definitions
│       ├── terraform.tfvars.template    # Configuration template for deployments
│       └── modules/                     # Modular components (spanner, storage, auth, ingestion, etc.)
│
├── docs/                                # Centralized platform documentation
│   ├── README.md                        # Documentation blueprint and directory index
│   ├── codelabs/                        # Hands-on interactive tutorials for developers
│   ├── architecture/                    # Deep-dive system specifications and technical designs
│   └── user_guide.md                    # Operational manual for DCP Admins
│
├── tests/                               # Integration tests and automated cloud probers
└── samples/                             # Sample datasets for local testing and ingestion verification
```

---

## 3. Documentation Standards

To keep documentation clean, discoverable, and accessible to newcomers, all contributions must follow our documentation standards (detailed in [docs/README.md](docs/README.md)):

1. **Centralize Architecture and Tutorials in `docs/`**:
   * Deep architectural specifications belong in `docs/architecture/`.
   * Hands-on onboarding tutorials belong in `docs/codelabs/`.
   * Do not create new documentation directories at the repository root.
2. **Keep Local `README.md` Files Strictly Operational**:
   * Local module READMEs (such as [infra/dcp/README.md](infra/dcp/README.md) and [packages/datacommons-cli/README.md](packages/datacommons-cli/README.md)) must focus on operational commands, inputs, outputs, and variable references.
   * Do not add lengthy architectural essays to localized READMEs. Link to the corresponding document in `docs/architecture/` instead.
3. **Maintain Strict Persona Separation**:
   * [docs/user_guide.md](docs/user_guide.md) serves **DCP Admins** (operators deploying and managing Data Commons instances for organizations).
   * Developer workflows, codelabs, and contributor guidelines belong in `docs/codelabs/`, `docs/architecture/`, or this file.
4. **Plain Engineering Writing**:
   * Write in direct, active developer language. Explain standard technical metrics in plain English before presenting data.
   * Avoid decorative emojis and avoid em dashes or en dashes. Use relative file links rather than absolute local paths.

---

## 4. Local Development Workflows

### Running CLI Packages Locally

When developing or modifying Python packages in `packages/`, run commands in editable workspace mode using `uv`:

```bash
# Run admin init using local repository code
uv run --package datacommons-cli datacommons admin init

# Run database setup against an existing deployment
uv run --package datacommons-cli datacommons admin init-db
```

### Working with Terraform Infrastructure

When modifying Terraform configurations in `infra/dcp/`:
* Inspect the root module in [infra/dcp/main.tf](infra/dcp/main.tf) and the orchestrator in [infra/dcp/modules/stack/main.tf](infra/dcp/modules/stack/main.tf).
* **Critical Scaffolding Contract**: Never reformat or alter line 166 in [infra/dcp/main.tf](infra/dcp/main.tf) (`source = "./modules/stack"`). The `datacommons admin init` CLI command relies on exact matching of this line to replace it with the remote GitHub Git module URL for downstream users.
* Test your changes locally in `infra/dcp/` by creating a `terraform.tfvars` file from `terraform.tfvars.template` and running `terraform plan`.

---

## 5. Testing Guidelines

Before opening a pull request, verify that all relevant tests pass:

### Unit Tests
Run the pytest suite across all monorepo packages:

```bash
uv run pytest
```

### Hermetic Integration Tests
The repository includes a local hermetic test suite using Docker Compose to emulate Spanner, Cloud Storage, Ingestion Helper, and serving containers:

```bash
uv run pytest tests/integration/suites/ \
    --instance local \
    --test-config foobar_wages
```
For details on emulated test options, fast re-runs (`--reuse-data`), and cloud testbed execution, refer to [tests/integration/README.md](tests/integration/README.md).


---

## 6. Pull Request & Review Guidelines

1. **Focused Commits**: Structure pull requests with clear, descriptive commit messages following the Conventional Commits format (e.g. `feat(cli): ...`, `fix(terraform): ...`, `docs: ...`).
2. **Review Discipline**: Keep pull requests focused on a single logical change or feature. Avoid bundling unrelated refactors or formatting changes.
3. **No Force Pushing on Active Review Branches**: Once a pull request is undergoing review, push incremental commits rather than force-pushing or rewriting commit history, allowing reviewers to inspect incremental diffs easily.
4. **Preserve Documentation Integrity**: When adding new features or changing variables, update the corresponding documentation files in `docs/` and localized READMEs.

---

## 7. License

By contributing to Data Commons, you agree that your contributions will be licensed under the [Apache-2.0 License](LICENSE).
