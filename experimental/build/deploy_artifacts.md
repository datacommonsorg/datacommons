# Deploying Data Commons Platform Artifacts

> **Internal Process Only**
> This document describes the process for deploying the Data Commons Platform docker artifacts to Google's managed Artifact Registry. These instructions are not intended for general users or external deployments.

## Prerequisites

-   [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed and authenticated.
-   Access to the `datcom-ci` GCP project.
-   `docker` installed locally (optional, for local builds).

## Building Locally

To build the Docker image locally, you **must run the command from the repository root**, pointing to the Dockerfile in `experimental/build/`.

```bash
docker build -f experimental/build/Dockerfile -t datacommons-platform:local .
```

To run the container locally:

```bash
docker run -p 5000:5000 datacommons-platform:local
```

Access the API at `http://localhost:5000`.

## Deploying via Cloud Build

We use Google Cloud Build to build and push images to Google Container Registry (GCR).

### Manual Deployment

You can manually trigger a build from your local machine using the `gcloud` CLI:

```bash
gcloud builds submit --config experimental/build/cloudbuild.yaml \
  --project=datcom-ci \
  .
```

This will:
1.  Upload your current workspace (files in `.`) to Cloud Build.
2.  Execute steps in `experimental/build/cloudbuild.yaml`.
3.  Push images to `us-docker.pkg.dev/datcom-ci/gcr.io/datacommons-platform:latest` and `:$SHORT_SHA`.

---

## Automated Cloud Build Trigger (Historical Context)

We previously maintained an automated Cloud Build trigger (`dcp-push-image-on-pr-merge`) in `datcom-ci` that built and published `datacommons-platform:latest` to Artifact Registry whenever code merged into `main`. Because active DCP deployments migrated to `datacommons-services` (built from `datcom-website`), this trigger was deleted to avoid unused builds.

If the team ever resumes automated publishing of the `datacommons-platform` container image, recreate the trigger in `datcom-ci`:

```bash
gcloud builds triggers create github \
  --project=datcom-ci \
  --name=dcp-push-image-on-pr-merge \
  --repo-owner=datacommonsorg \
  --repo-name=datacommons \
  --branch-pattern='^main$' \
  --build-config=experimental/build/cloudbuild.yaml \
  --description="Push latest Docker image on PR merge"
```
