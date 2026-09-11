# Data Commons

[![CI](https://github.com/datacommonsorg/datacommons/actions/workflows/ci.yaml/badge.svg)](https://github.com/datacommonsorg/datacommons/actions/workflows/ci.yaml)

Data Commons is an open source semantic graph database for modeling, querying, and analyzing interconnected data.

Data Commons powers [datacommons.org](https://datacommons.org), Google's open knowledge graph that connects public data across domains like demographics, economics, health, and education.

## Getting Started

* **New to DCP?** Follow the hands-on [Developer Onboarding Codelab](docs/codelabs/dcp_developer_onboarding.md) for a zero-to-hero tutorial deploying, inspecting, seeding, and tearing down an instance.
* **Contributing code?** Consult the [Developer Guide](docs/developer_guide.md) for monorepo topology, `uv workspace` linking, and testing, and review [CONTRIBUTING.md](CONTRIBUTING.md) for pull request guidelines.

This guide covers setting up Data Commons in Google Cloud Platform (GCP), defining schemas in JSON-LD, adding data via the command-line interface, and querying relationships.

## Prerequisites

Before you begin, ensure you have the following installed:

- [Python](https://www.python.org/downloads/) 3.11 or higher
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python project manager)
- A Google Cloud Platform (GCP) project with Cloud Spanner enabled
- A Cloud Spanner instance and database (using Google Standard SQL) for storing the knowledge graph

## Deploying Data Commons Platform In GCP

Use the CLI to scaffold a Terraform deployment directory:

```bash
git clone https://github.com/datacommonsorg/datacommons
cd datacommons/
uv run datacommons admin init
```

The command will prompt for:
- GCP project id
- Instance name
- Data Commons API key

It then creates a new folder with `main.tf`, `terraform.tfvars`, and a deployment `README.md`.

From the generated folder:

```bash
terraform init
terraform plan
terraform apply
```

Once infrastructure is deployed, initialize the database and trigger data ingestion using the CLI.

You can run these commands directly from your Terraform deployment directory (where state outputs are detected automatically), or from anywhere by passing the `--project-id` and `--instance-name` flags:

#### Option A: Run from your Terraform directory
```bash
# Run from inside your deployment folder (e.g. cd prod/)
uv run datacommons admin init-db

# Trigger data ingestion
uv run datacommons admin ingest start --imports <import_name>
```

#### Option B: Run from anywhere (Remote GCS State)
```bash
# Run from any directory or CI/CD runner without local Terraform files
uv run datacommons admin --project-id my-gcp-project --instance-name prod init-db

# Trigger data ingestion
uv run datacommons admin --project-id my-gcp-project --instance-name prod ingest start --imports <import_name>
```

## Documentation & Guides

| Guide | Target Audience | Purpose |
| :--- | :--- | :--- |
| **[Developer Onboarding Codelab](docs/codelabs/dcp_developer_onboarding.md)** | New Developers | Hands-on zero-to-hero onboarding tutorial deploying and testing an instance on GCP. |
| **[Developer Guide](docs/developer_guide.md)** | Monorepo Developers | Monorepo package layout, `uv workspace` linking, local development recipes, and testing strategy. |
| **[Platform Architecture](docs/architecture/platform_architecture.md)** | All Contributors | 4-repository architecture, container roles, and complete serving and ingestion data flows. |
| **[Terraform Stack Architecture](docs/architecture/terraform_stack.md)** | Infrastructure Developers | Module hierarchy, variable propagation pipelines, and cross-module IAM wiring. |
| **[Admin CLI Architecture](docs/architecture/admin_cli.md)** | CLI Contributors | Admin CLI internals, scaffolding regex contract, and state-driven operation choreography. |
| **[Data Commons Platform User Guide](docs/user_guide.md)** | DCP Admins | Comprehensive operational manual for deploying instances, preparing datasets, and managing platform operations. |
| **[Contributing Guide](CONTRIBUTING.md)** | Pull Request Authors | Code quality standards, formatting, linting, and unit test requirements. |
| **[Platform Release Guide](docs/release.md)** | Release Managers | Official 3-stage release candidate workflow and PyPI lockstep publishing procedures. |
| **[Documentation Standards](docs/README.md)** | All Readers | Platform documentation architecture and writing standards. |
| **[CLI Reference & Cheatsheet](packages/datacommons-cli/README.md)** | CLI Users & CI/CD | Full command reference and operational CLI cheatsheet. |
| **[Infrastructure Cheatsheet](infra/dcp/README.md)** | Operators & Contributors | Operational cheatsheet for `infra/dcp/`: commands, inputs, and outputs. |
