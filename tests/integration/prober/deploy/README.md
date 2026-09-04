# Data Commons Platform (DCP) — Prober Deployment Runbook

This directory contains the automation and Terraform blueprint to deploy and update the **24/7 Continuous DCP Integration Prober** on Google Cloud.

---

## 🚀 Automated CI/CD vs. Manual Terraform Deployments

| Deployment Type | Scope | Trigger | How It Works |
| :--- | :--- | :--- | :--- |
| **🤖 Automated CI/CD** (`cloudbuild.yaml`) | **Container Image & Tests** | Push/Merge to `main` (`tests/integration/**`) | Cloud Build automatically builds the new container image and updates the `dcp-prober` Cloud Run Job to use the new image. **Zero manual action needed.** |
| **🛠️ Manual Infrastructure** (`deploy_prober.sh`) | **Full Terraform Blueprint** | Manual CLI execution | Manages the full GCP infrastructure (Service Accounts, Secrets, GCS Buckets, Cloud Scheduler cron, Cloud Monitoring alerts, and Cloud Run). |

> ℹ️ **Secret Auto-Reuse**: When running `./deploy_prober.sh`, the script automatically detects and reuses existing API keys (`dcp-prober-api-key`) and active settings (`dcp-prober-tfvars`) from Google Secret Manager. You do **not** need to re-enter sensitive keys or provide flags on routine updates.

---

## 🛠️ Manual Deployment & Infrastructure Updates (`deploy_prober.sh`)

Run the deployer script from your terminal:

```bash
./deploy_prober.sh \
  --project datcom-dcp \
  --prober-name dcp-prober \
  --schedule "0 */3 * * *" \
  --alert-email datacommons-alerts+dcp-prober@google.com \
  --test-config foobar_wages
```

> **Interactive Mode**: Running `./deploy_prober.sh` without arguments auto-detects your active `gcloud` project and interactively prompts for optional configuration overrides.

---

## ⚡ Fast Infrastructure Updates (`--skip-build`)

If you only modified Terraform configurations, alert recipients, cron schedules, or environment settings and **do not need to rebuild the Docker container**, use `--skip-build`:

```bash
./deploy_prober.sh --skip-build \
  --project datcom-dcp \
  --prober-name dcp-prober \
  --alert-email datacommons-alerts+dcp-prober@google.com \
  --schedule "0 */3 * * *"
```

---

## ⚙️ Available CLI Options

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--project <id>` | Active `gcloud` project | Target GCP Project ID for the prober |
| `--prober-name <name>` | `dcp-prober` | Resource name prefix for Cloud Run Job, Scheduler, and Bucket |
| `--schedule <cron>` | `0 */3 * * *` | Cron schedule for recurring prober execution |
| `--test-config <name>` | `foobar_wages` | Test dataset manifest to run on each execution |
| `--alert-email <email>` | *(none)* | Email address for Cloud Monitoring failure notifications |
| `--dc-api-key <key>` | *(none)* | Optional Data Commons API key |
| `--location <region>` | `us-central1` | GCP Region for Cloud Run Job and Scheduler |
| `--skip-build` | `false` | Skip Cloud Build container packaging |
| `--non-interactive` | `false` | Run with flags/defaults without interactive prompts |

---

## 🏗️ How Deployment Works (`deploy_prober.sh`)

When you run `./deploy_prober.sh`, the deployment executes two main phases:

### Phase 1: Container Build (Cloud Build)
* Packages Terraform 1.10, `uv`, `gcloud-cli`, Python dependencies, and `prober_runner.py` using [`Dockerfile`](Dockerfile) and [`cloudbuild.yaml`](cloudbuild.yaml).
* Pushes the image to Artifact Registry at `us-docker.pkg.dev/datcom-ci/datcom-tools/datacommons-platform-prober:latest`.
* Ensures the target project's Cloud Run Service Agent has `roles/artifactregistry.reader` on `datcom-ci`.

### Phase 2: Cloud Infrastructure Provisioning (Terraform)
* Uses [`terraform/`](terraform/) as a reusable blueprint to deploy the prober engine.
* Automatically creates the remote GCS state bucket (`gs://tf-state-<prober-name>-<project>`) if it does not exist.
* Runs `terraform init -backend-config="bucket=..." -reconfigure` to dynamically bind to your project's state bucket without modifying code files on disk.
* Runs `terraform apply`, injecting your CLI flags to provision:
  * **Dedicated Service Account** (`dcp-prober-sa`) with necessary deployment permissions.
  * **Serverless Cloud Run Job** (`dcp-prober`) running the containerized prober runner.
  * **Cloud Scheduler Cron Job** (`dcp-prober-cron`) triggering Cloud Run (default: every 3 hours).
  * **GCS Reports Bucket** (`dcp-prober-reports-<project>`) with 90-day lifecycle retention.
  * **Cloud Monitoring Alert Policy** and email notification channel for instant failure alerts.
  * **Secret Manager Secret** (`dcp-prober-tfvars`) archiving active deployment settings.

---

## 🔐 Cross-Project Permissions (Artifact Registry)

`deploy_prober.sh` automatically grants `roles/artifactregistry.reader` on the `datcom-ci` repository to the target project's Cloud Run Service Agent (`service-${PROJECT_NUMBER}@serverless-robot-prod.iam.gserviceaccount.com`). 

If deploying via a custom service account lacking IAM admin privileges, ensure an administrator grants this role on `datcom-ci` so Cloud Run can pull the container image.
