# Data Commons CLI

<p align="center">
  <a href="https://www.datacommons.org"><img src="https://datacommons.org/images/dc-logo.svg" alt="Data Commons" width="120"></a>
</p>

<p align="center">
  <em>Standard command-line interface for interacting with, deploying, and administering the Data Commons Platform.</em>
</p>

---

[Data Commons](https://www.datacommons.org) is an open-source project initiated by Google that aggregates data from hundreds of public sources—such as the US Census, Eurostat, CDC, and UN—into a unified, standard Knowledge Graph.

The **Data Commons Platform** provides the infrastructure to run your own private instance of Data Commons, allowing you to seamlessly combine public datasets with your own custom, private data using modern APIs, graph query engines, and visualization dashboards.

---

## Installation

Install the Data Commons CLI using `pip` or `uv`:

```bash
sudo pip install -H datacommons-cli
```

For a global installation using `uv` (which manages your PATH automatically):

```bash
uv tool install datacommons-cli
```

Or execute it on-the-fly without installation using `uvx`:

```bash
uvx datacommons-cli --help
```

## Help & Documentation

For full documentation, tutorials, and deployment guides, visit:
👉 **[docs.datacommons.org](https://docs.datacommons.org)**

---

## Usage

The CLI exposes standard operations under the main `datacommons` entrypoint. You can check the version and get help instantly:

```bash
# Show help menu
datacommons --help

# Show version
datacommons --version
```

---

## Administrative Commands

All infrastructure setup, database operations, and ingestion pipelines are managed under the `admin` sub-command group:

```bash
datacommons admin [COMMAND] --help
```

### Available Commands

| Command | Description |
| --- | --- |
| **`init`** | Scaffolds a localized Terraform configuration to deploy the Data Commons Platform on Google Cloud Platform (GCP). |
| **`init-db`** | Configures database schemas and seeds baseline tables on GCP Spanner via the Ingestion Helper service. |
| **`seed-db`** | Re-runs or updates base geographic and schema seeds on GCP Spanner. |
| **`ingest start`** | Triggers a Cloud Run + Cloud Workflows background data ingestion pipeline to import your custom datasets. |
| **`ingest show-config`**| Prints current background ingestion parameters, GCS bucket paths, and active GCP credentials. |

### Quickstart: Scaffolding a Private Data Commons

1. Initialize your project configuration and scaffold Terraform templates:
   ```bash
   datacommons admin init --project-id my-gcp-project --namespace prod
   ```

2. Change directories to the scaffolded directory (e.g. `cd prod`).

3. Deploy using Terraform, then initialize and seed your Spanner database:
   ```bash
   datacommons admin init-db
   ```

4. Trigger your first background data ingestion pipeline:
   ```bash
   datacommons admin ingest start
   ```

---

License: [Apache-2.0](https://github.com/datacommonsorg/datacommons/blob/main/LICENSE)
