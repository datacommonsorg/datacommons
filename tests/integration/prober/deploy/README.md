# Data Commons Platform (DCP): Prober Deployment Runbook

This directory contains the automation and Terraform blueprint to deploy and update the **24/7 Continuous DCP Integration Prober** on Google Cloud.

---

## 🚀 Automated CI/CD vs. Manual Terraform Deployments

| Deployment Type | Scope | Trigger | How It Works |
| :--- | :--- | :--- | :--- |
| **🤖 Automated CI/CD** (`cloudbuild.yaml`) | **Container Image & Tests** | Push/Merge to `main` (`tests/integration/**`) | Cloud Build automatically builds the new container image and updates the `dcp-prober` Cloud Run Job to use the new image. **Zero manual action needed.** |
| **🛠️ Manual Infrastructure** (`deploy_prober.sh`) | **Full Terraform Blueprint** | Manual CLI execution | Manages the full GCP infrastructure (Service Accounts, Secrets, GCS Buckets, Cloud Scheduler cron, Cloud Monitoring alerts, and Cloud Run). |
| **Dev Image Test** (`push_image.sh`) | **Container Image (dev tag)** | Manual CLI execution | Builds and pushes an image from your branch under a dev tag. You point the `dcp-prober` job at it, run it, and switch it back when done. See [Testing a Dev Prober Image](#testing-a-dev-prober-image). |

---

## Testing a Dev Prober Image

To check that a prober change passes before you merge it, run the `dcp-prober` job once on an image built from your branch.

1. From the repository root on your branch, build and push the image with a dev tag such as `alice-pr123`. The script leaves `:latest` and the prober Cloud Run job unchanged.

   ```bash
   ./tests/integration/prober/deploy/push_image.sh <dev-tag>
   ```

2. Update the prober Cloud Run job to use your dev image:

   ```bash
   gcloud run jobs update dcp-prober --image=us-docker.pkg.dev/datcom-ci/datcom-tools/datacommons-platform-prober:<dev-tag> \
     --region=us-central1 --project=datcom-dcp
   ```

3. Run the prober manually and wait for it to finish, which takes about 10 minutes:

   ```bash
   gcloud run jobs execute dcp-prober --region=us-central1 --project=datcom-dcp --wait
   ```

   If the run fails, the `PROBER EXECUTION SUMMARY` line at the end of the execution's logs shows which stage failed.

> [!NOTE]
> Every prober run, including scheduled runs, keeps using your dev image until you run step 4 or until a merged prober PR triggers CI to build and deploy a new image.

4. When you're done testing, whether the run passed or failed, switch the job back to the latest image from `main`:

   ```bash
   gcloud run jobs update dcp-prober --image=us-docker.pkg.dev/datcom-ci/datcom-tools/datacommons-platform-prober:latest \
     --region=us-central1 --project=datcom-dcp
   ```

---

## 🛠️ Manual Deployment & Infrastructure Updates (`deploy_prober.sh`)

Run the deployer script from your terminal:

```bash
./deploy_prober.sh \
  --project datcom-dcp \
  --prober-name dcp-prober \
  --schedule "17 */3 * * *" \
  --alert-email datacommons-alerts+dcp-prober@google.com \
  --test-config foobar_wages
```

> **Interactive Mode**: Running `./deploy_prober.sh` without arguments auto-detects your active `gcloud` project and interactively prompts for optional configuration overrides.

> ℹ️ **Secret Auto-Reuse**: When running `./deploy_prober.sh`, the script automatically detects and reuses existing API keys (`dcp-prober-api-key`) and active settings (`dcp-prober-tfvars`) from Google Secret Manager. You do **not** need to re-enter sensitive keys or provide flags on routine updates.

### 🧪 Formatting & Validating Terraform (`terraform/`)

```bash
# Format Terraform in-place
uv run infra/dcp/scripts/check_terraform.py --tf-dir tests/integration/prober/deploy/terraform --fix

# Check formatting and validate Terraform configuration
uv run infra/dcp/scripts/check_terraform.py --tf-dir tests/integration/prober/deploy/terraform --fmt --validate
```

### ⚡ Fast Infrastructure Updates (`--skip-build`)

If you only modified Terraform configurations, alert recipients, cron schedules, or environment settings and **do not need to rebuild the Docker container**, use `--skip-build`:

```bash
./deploy_prober.sh --skip-build \
  --project datcom-dcp \
  --prober-name dcp-prober \
  --alert-email datacommons-alerts+dcp-prober@google.com \
  --schedule "17 */3 * * *"
```

### ⚙️ Available CLI Options

| Flag | Default | Description |
| :--- | :--- | :--- |
| `--project <id>` | Active `gcloud` project | Target GCP Project ID for the prober |
| `--prober-name <name>` | `dcp-prober` | Resource name prefix for Cloud Run Job, Scheduler, and Bucket |
| `--schedule <cron>` | `17 */3 * * *` | Cron schedule for recurring prober execution |
| `--test-config <name>` | `foobar_wages` | Test dataset manifest to run on each execution |
| `--alert-email <email>` | *(none)* | Email address for Cloud Monitoring failure notifications |
| `--dc-api-key <key>` | Active Secret Manager version | Data Commons API key (required on initial deploy; auto-reused from Secret Manager afterward) |
| `--location <region>` | `us-central1` | GCP Region for Cloud Run Job and Scheduler |
| `--image-tag <tag>` | `latest` | Container image tag in Artifact Registry |
| `--skip-build` | `false` | Skip Cloud Build container packaging |
| `--non-interactive` | `false` | Run with flags/defaults without interactive prompts |

---

## 🏗️ How Deployment Works (`deploy_prober.sh`)

When you run `./deploy_prober.sh`, the deployment executes two main phases:

### Phase 1: Container Build (Cloud Build)
* Packages Terraform 1.10, `uv`, `gcloud-cli`, Python dependencies, and `prober_runner.py` using [`Dockerfile`](Dockerfile) and [`cloudbuild.yaml`](cloudbuild.yaml).
* Pushes the image to Artifact Registry at `us-docker.pkg.dev/datcom-ci/datcom-tools/datacommons-platform-prober`, tagged `:<image-tag>` (default `latest`) and `:<short-commit-sha>`.
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
