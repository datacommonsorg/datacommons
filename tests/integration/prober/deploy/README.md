# Data Commons Platform (DCP): Prober Deployment Runbook

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
  --schedule "17 */3 * * *" \
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
  --schedule "17 */3 * * *"
```

---

## Testing a Branch Image on the Prober

To check that a branch passes the prober before merging, build a prober image from the branch and run the `dcp-prober` job once with it.

1. Save the current `:latest` digest so you can roll back:

   ```bash
   REG=us-docker.pkg.dev/datcom-ci/datcom-tools/datacommons-platform-prober
   gcloud artifacts docker images describe $REG:latest --format='value(image_summary.digest)'
   ```

2. From the repository root on your branch, build the image. `_TAG` sets the image's dev tag. The build also tags `:latest` and points the `dcp-prober` job at the dev tag. It runs as the same service account as the CI trigger, which has permission to update the job.

   ```bash
   gcloud builds submit --project=datcom-ci \
     --service-account=projects/datcom-ci/serviceAccounts/datcom-dcp-prober-deployer-sa@datcom-ci.iam.gserviceaccount.com \
     --config=tests/integration/prober/deploy/cloudbuild.yaml \
     --substitutions=_TAG=<dev-tag>,_COMMIT_SHA=$(git rev-parse HEAD) .
   ```

   If you can't run builds as that service account, add `_UPDATE_JOB=false` to the substitutions and update the job yourself after the build finishes:

   ```bash
   gcloud run jobs update dcp-prober --image=$REG:<dev-tag> --region=us-central1 --project=datcom-dcp
   ```

3. Run the prober once and wait for it to finish (about 10 minutes):

   ```bash
   gcloud run jobs execute dcp-prober --region=us-central1 --project=datcom-dcp --wait
   ```

4. Check the result. A passing run ends with a `PROBER EXECUTION SUMMARY` log line showing `"integration_tests": "PASSED"`.

This changes the production prober. Scheduled runs keep using your image until the next merge under `tests/integration/**`, which rebuilds `:latest` from `main` and points the job back to it. To roll back sooner, retag the saved digest and update the job:

```bash
gcloud artifacts docker tags add $REG@<saved-digest> $REG:latest
gcloud run jobs update dcp-prober --image=$REG:latest --region=us-central1 --project=datcom-dcp
```

---

## ⚙️ Available CLI Options

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

## 🧪 Formatting & Validating Terraform (`terraform/`)

```bash
# Format Terraform in-place
uv run infra/dcp/scripts/check_terraform.py --tf-dir tests/integration/prober/deploy/terraform --fix

# Check formatting and validate Terraform configuration
uv run infra/dcp/scripts/check_terraform.py --tf-dir tests/integration/prober/deploy/terraform --fmt --validate
```

---

## 🔐 Cross-Project Permissions (Artifact Registry)

`deploy_prober.sh` automatically grants `roles/artifactregistry.reader` on the `datcom-ci` repository to the target project's Cloud Run Service Agent (`service-${PROJECT_NUMBER}@serverless-robot-prod.iam.gserviceaccount.com`). 

If deploying via a custom service account lacking IAM admin privileges, ensure an administrator grants this role on `datcom-ci` so Cloud Run can pull the container image.

