# Data Commons

[![CI](https://github.com/datacommonsorg/datacommons/actions/workflows/ci.yaml/badge.svg)](https://github.com/datacommonsorg/datacommons/actions/workflows/ci.yaml)

Data Commons is an open source semantic graph database for modeling, querying, and analyzing interconnected data.

Data Commons powers [datacommons.org](https://datacommons.org), Google's open knowledge graph that connects public data across domains like demographics, economics, health, and education.

## Getting Started

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

For the full infrastructure module and complete variable reference, see the detailed [GCP Infrastructure Guide](infra/dcp/README.md).
