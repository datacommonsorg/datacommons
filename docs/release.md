# Data Commons Platform (DCP) Release & Versioning Guide

This repository implements lockstep versioning and automated CI/CD workflows using Google Cloud Build to publish package distributions to PyPI and TestPyPI.

---

## 1. Architectural Principles & Lockstep Versioning

### Single-Sourced Versioning
All tracked packages under `packages/` and the root repository share an identical version number.
* **Root Version:** Version declarations are single-sourced via the root [`VERSION`](../VERSION) file.
* **Subpackage Versioning:** Subpackage `pyproject.toml` files dynamically pull their version from the symlinked `VERSION` file (`version = {file = "VERSION"}`).
* **Runtime Version:** Packages expose `__version__` in `__init__.py`, stamped during version bumping.

### Package Dependency Locking (`datacommons-cli` $\rightarrow$ `datacommons-admin`)
The `datacommons-cli` package depends on `datacommons-admin`. To prevent version drift when clients upgrade (e.g. upgrading `datacommons-cli` without upgrading `datacommons-admin`), the build system locks the requirement in `packages/datacommons-cli/pyproject.toml`:
```toml
dependencies = [
  "click>=8.1.7",
  "datacommons-admin>=1.2.3",
]
```

> [!IMPORTANT]
> **Strict Publication Order:** In all CI/CD pipelines, package publishing is executed alphabetically (`packages/*`). This guarantees `datacommons-admin` is built and published **before** `datacommons-cli`, allowing dependency resolution on PyPI and TestPyPI to succeed cleanly.

---

## 2. CI/CD Pipeline Architecture & Intentional Triggers

Automated workflows are powered by **Google Cloud Build** across three distinct pipelines, each with a single, unambiguous trigger method:

| Pipeline | Trigger / Method | Role & Actions | Version Bumping | Git Tag Action | Destination |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`staging.yaml`** | Manual `gcloud builds submit` | Release candidate staging (supports custom commit SHA) | Executes `deploy/scripts/apply_version_bump.sh` | **Tags & Pushes `v<VERSION>` to GitHub** (does not commit to `main`) | **TestPyPI** |
| **`bump_version.yaml`** | Manual `gcloud builds submit` | Automated version bump PR generator | Executes `deploy/scripts/apply_version_bump.sh` | **Creates PR branch on Git** | N/A |
| **`release.yaml`** | Publish GitHub Release `v*` | Production release (runs on tagged commit SHA) | **Read-only validation** (verifies committed versions match tag) | **NO** | **Official PyPI** |

---

## 3. Shared Version Bumping Script (`apply_version_bump.sh`)

All local version updates across files are single-sourced in [`deploy/scripts/apply_version_bump.sh`](../deploy/scripts/apply_version_bump.sh):

1. Updates `VERSION` and subpackage `packages/*/VERSION` files.
2. Updates `__version__` strings across all `packages/*/datacommons_*/__init__.py` files.
3. Updates `dcp_version` default variables in `infra/dcp/*.tf`.
4. Locks `"datacommons-admin>=$NEW_VERSION"` in `packages/datacommons-cli/pyproject.toml`.

---

## 4. Step-by-Step Release Walkthrough

### Step 1: Trigger Staging Pre-Release (TestPyPI & GitHub RC Tag)

To build, tag, and publish a Release Candidate (RC) for partner testing off **`main`** or **any specific commit SHA**:

1. **Trigger Staging Build via Cloud Build:**
   Run `gcloud builds submit` targeting `deploy/staging.yaml` with your target RC version string. You can optionally specify `_GITHUB_COMMIT` to build off a specific commit SHA (defaults to `main`):
   ```bash
   # Build off latest main
   gcloud builds submit \
     --config deploy/staging.yaml \
     --substitutions=_TARGET_VERSION="1.2.3rc1" \
     --project="datcom-ci" \
     .

   # Build off a specific commit SHA (e.g. 8f9b2a1)
   gcloud builds submit \
     --config deploy/staging.yaml \
     --substitutions=_TARGET_VERSION="1.2.3rc1",_GITHUB_COMMIT="8f9b2a1" \
     --project="datcom-ci" \
     .
   ```

#### What `staging.yaml` Executes:
1. Clones a clean copy of the target commit SHA (or `main`) directly from GitHub.
2. Applies the version bump (`1.2.3rc1`) to local files (`VERSION`, `pyproject.toml`, `__init__.py`, `variables.tf`).
3. Creates a local commit inside Cloud Build and **pushes Git tag `v1.2.3rc1` to GitHub**. 
   - *Note:* The tag `v1.2.3rc1` on GitHub points to the bumped commit, allowing raw HTTP template fetches (`variables.tf?ref=v1.2.3rc1`) to succeed during `datacommons admin init`.
   - *Note:* Branch `main` is untouched.
4. Builds wheels and publishes packages to **TestPyPI**.

2. **Verify Staging RC & Installation:**
   - Confirm package availability on TestPyPI (`https://test.pypi.org/project/datacommons-cli/1.2.3rc1/`).
   - Test installation in a clean environment:
     ```bash
     uv tool install --force \
       --index-url https://test.pypi.org/simple/ \
       --extra-index-url https://pypi.org/simple/ \
       "datacommons-cli==1.2.3rc1"
     ```
   - Initialize a test deployment:
     ```bash
     datacommons admin init \
       --project-id my-gcp-project \
       --instance-name test-rc-stack
     ```
     *(The CLI automatically passes `--tf-git-ref v1.2.3rc1`, which pulls the newly published GitHub tag with default `dcp_version = "1.2.3rc1"`).*

---

### Step 2: Production Version Bump PR

Once the RC is verified on TestPyPI and staging environments:

1. **Trigger Version Bump Workflow:**
   ```bash
   gcloud builds submit \
     --config deploy/bump_version.yaml \
     --substitutions=_NEW_VERSION="1.2.3" \
     --project="datcom-ci" \
     .
   ```
2. **Review & Merge PR:**
   - Locate the auto-created PR (e.g. `chore: bump version to 1.2.3`) on GitHub.
   - Confirm that `VERSION`, `pyproject.toml`, `__init__.py` files, and `infra/dcp/*.tf` are updated to `1.2.3`.
   - Approve and merge the PR into `main`.

---

### Step 3: Publish Official Production Release

1. **Draft & Publish GitHub Release:**
   - Navigate to [GitHub Releases](https://github.com/datacommonsorg/datacommons/releases).
   - Click **Draft a new release**.
   - Select target tag `v1.2.3` and choose target branch/commit.
   - Title: `v1.2.3`.
   - Add release notes and click **Publish release**.
2. **Production Pipeline Execution (`release.yaml`):**
   - Publishing tag `v1.2.3` automatically triggers `deploy/release.yaml` on that commit SHA.
   - `release.yaml` performs read-only validation that all committed files match `1.2.3`, builds wheels, and publishes to **Official PyPI**.
3. **Verify Production PyPI Release:**
   ```bash
   uv tool install --force "datacommons-cli==1.2.3"
   datacommons --version
   # Expected output: Data Commons CLI v1.2.3
   ```
