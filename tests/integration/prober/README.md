# Data Commons Platform (DCP) — Serverless Ephemeral Prober

An automated, serverless integration prober for the **Data Commons Platform (DCP)**.

The prober continuously provisions an isolated ephemeral DCP instance on GCP via Terraform, executes the full end-to-end integration test suite, uploads machine-readable execution reports to GCS, triggers Cloud Monitoring alerts on failure, and guarantees 100% infrastructure teardown.

---

## 🏗️ Architecture Overview

```mermaid
flowchart LR
    subgraph Trigger ["1. Trigger"]
        CS["⏰ Cloud Scheduler<br/>(Every 3 Hours)"] --> CRJ["🚀 Cloud Run Job<br/>(dcp-prober)"]
    end

    subgraph Execution ["2. Orchestration & Testing"]
        CRJ --> PR["🐍 prober_runner.py"]
        PR -->|Terraform Apply| TF["🛠️ Ephemeral DCP Instance<br/>(prober-UUID)"]
        TF --> E2E["🧪 Integration Test Suite<br/>(run_e2e_tests.py)"]
        E2E -->|Generate Artifacts| GCS["📦 GCS Reports Bucket"]
    end

    subgraph Teardown ["3. Lifecycle & Teardown"]
        E2E -.->|On Failure| MON["🚨 Cloud Monitoring Alert<br/>(Email Notification)"]
        E2E -->|Guaranteed Teardown| TFD["🗑️ Terraform Destroy<br/>(100% Cleanup)"]
    end
```

### Key Capabilities
- **State Isolation**: Reuses a single persistent state bucket (`tf-state-dcp-prober-${PROJECT}`) while dynamically generating unique execution prefixes (`ephemeral/prober-{uuid}/default.tfstate`). Eliminates cross-run state pollution and bucket creation rate limits.
- **Guaranteed Teardown**: Python `try ... finally` blocks and signal handlers guarantee that `terraform destroy -auto-approve` runs on success, test failure, provisioning error, or container cancellation.
- **Zero Retries at Container Level**: `max_retries = 0` on the Cloud Run Job prevents duplicate job executions when a test legitimately fails, while internal retry loops handle transient GCP API rate limits automatically.

---

## 🚀 Quick Start & Deployment

### 1. Deploy Prober Infrastructure
Run the main deployment script:

```bash
./tests/integration/prober/deploy/deploy_prober.sh \
  --project datcom-dcp \
  --prober-name dcp-prober \
  --test-config foobar_wages \
  --schedule "0 */3 * * *" \
  --alert-email gmechali@google.com \
  --location us-central1 \
  --dc-api-key "YOUR_DATACOMMONS_API_KEY" \
  --non-interactive
```

> **Note on Interactive Mode**: If you run `./tests/integration/prober/deploy/deploy_prober.sh` without flags, it automatically detects your active `gcloud` project (`datcom-dcp`) and interactively prompts for any optional configuration overrides.

### 2. Fast Deploy (`--skip-build`)
If you only modified Terraform files or environment settings and do not need to rebuild the Docker image:

```bash
./tests/integration/prober/deploy/deploy_prober.sh --skip-build
```

---

## ☁️ Deployed Cloud Infrastructure & Resource Links

Prober infrastructure and cron schedules are deployed via Terraform with **Remote State Management** stored in Google Cloud Storage:

* **Cloud Run Job**: [Cloud Run Job: `dcp-prober`](https://console.cloud.google.com/run/jobs/details/us-central1/dcp-prober/executions?project=datcom-dcp)
* **Cloud Scheduler Trigger**: [Cloud Scheduler Jobs (`datcom-dcp`)](https://console.cloud.google.com/cloudscheduler?project=datcom-dcp)
* **Terraform Remote State Bucket**: [`gs://tf-state-dcp-prober-datcom-dcp`](https://console.cloud.google.com/storage/browser/tf-state-dcp-prober-datcom-dcp?project=datcom-dcp)
* **Container Image in Artifact Registry**: [`us-docker.pkg.dev/datcom-ci/datcom-tools/datacommons-platform-prober:latest`](https://console.cloud.google.com/artifacts/docker/datcom-ci/us/datcom-tools/datacommons-platform-prober?project=datcom-ci)
* **Prober Data Commons API Key**: [Secret Manager: `dcp-prober-api-key` in `datcom-ci`](https://console.cloud.google.com/security/secret-manager/secret/dcp-prober-api-key/versions?project=datcom-ci)

---

## 🔐 Cross-Project Artifact Registry Permissions

`deploy_prober.sh` automatically grants `roles/artifactregistry.reader` on the `datcom-ci` Artifact Registry to the target project's Cloud Run Service Agent. If deploying via custom CI/CD service accounts, ensure the target project robot account (`service-${PROJECT_NUMBER}@serverless-robot-prod.iam.gserviceaccount.com`) has reader access on the repository.

---

## 🧪 Running Prober Runner Locally / Debugging

### Run Full Ephemeral Cycle Locally
```bash
uv run python tests/integration/prober/prober_runner.py \
    --project datcom-dcp \
    --test-config foobar_wages
```

### Retain Ephemeral Resources for Debugging (`--skip-destroy`)
To keep all provisioned GCP resources (Cloud Workflows, Cloud Run services, Spanner databases, logs) alive after test execution for manual inspection:

```bash
uv run python tests/integration/prober/prober_runner.py \
    --project datcom-dcp \
    --test-config foobar_wages \
    --skip-destroy
```

---

## 🧹 Interactive Resource Cleanup Tool

If a debugging session with `--skip-destroy` or an unexpected cancellation leaves temporary `prober-*` resources behind, run the interactive cleanup janitor:

```bash
python3 tests/integration/prober/tools/cleanup_prober_trash.py
```

This tool safely scans and prompts before removing any orphaned `prober-*` Spanner instances, Cloud Run services, buckets, IAM bindings, or API keys.
