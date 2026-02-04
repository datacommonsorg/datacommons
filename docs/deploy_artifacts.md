# Deploying Data Commons Platform Artifacts

> **Internal Process Only**
> This document describes the process for deploying the Data Commons Platform docker artifacts to Google's managed Artifact Registry. These instructions are not intended for general users or external deployments.

## Prerequisites

-   [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed and authenticated.
-   Access to the `datcom-ci` GCP project.
-   `docker` installed locally (optional, for local builds).

## Building Locally

To build the Docker image locally, you **must run the command from the repository root**, pointing to the Dockerfile in `build/`.

```bash
docker build -f build/Dockerfile -t datacommons-platform:local .
```

To run the container locally:

```bash
docker run -p 5000:5000 datacommons-platform:local
```

Access the API at `http://localhost:5000`.

## Deploying via Cloud Build

We use Google Cloud Build to build and push images to Google Container Registry (GCR).

### Manual Deployment

You can manually trigger a build from your local machine using the `gcloud` CLI. You must provide the `COMMIT_SHA` substitution manually.

```bash
gcloud builds submit --config build/cloudbuild.yaml \
  --substitutions=COMMIT_SHA=$(git rev-parse HEAD) \
  --project=datcom-ci \
  .
```

This will:
1.  Upload your current workspace (files in `.`) to Cloud Build.
2.  Execute steps in `build/cloudbuild.yaml`.
3.  Push images to `gcr.io/datcom-ci/datacommons-platform:latest` and `:CommitSHA`.
