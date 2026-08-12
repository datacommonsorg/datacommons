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

## 2. CI/CD Pipeline Architecture

Automated workflows are powered by **Google Cloud Build** across three components:

| Pipeline | Trigger / Method | Role & Actions | Version Bumping | Git Commit? | Destination |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`bump_version.yaml`** | `gcloud builds submit` | Automated version bump PR generator | Executes `deploy/scripts/apply_version_bump.sh` | **YES** (creates PR branch) | N/A |
| **`staging.yaml`** | Push `v*rc*` tag (e.g. `v1.2.3rc1`) | Release candidate verification | Executes `deploy/scripts/apply_version_bump.sh` (ephemeral container state) | **NO** | **TestPyPI** |
| **`release.yaml`** | Publish `v*` tag (e.g. `v1.2.3`) | Production release | **Read-only validation** (verifies committed versions match tag) | **NO** | **Official PyPI** |

---

## 3. Shared Version Bumping Script (`apply_version_bump.sh`)

All local version updates across files are single-sourced in [`deploy/scripts/apply_version_bump.sh`](../deploy/scripts/apply_version_bump.sh):

1. Updates `VERSION` and subpackage `packages/*/VERSION` files.
2. Updates `__version__` strings across all `packages/*/datacommons_*/__init__.py` files.
3. Updates `dcp_version` default variables in `infra/dcp/*.tf`.
4. Locks `"datacommons-admin>=$NEW_VERSION"` in `packages/datacommons-cli/pyproject.toml`.

---

## 4. Step-by-Step Release Walkthrough

### Step 1: Create & Push Release Candidate (RC) for Staging Verification

To test a release candidate without cluttering `main` Git history:

1. **Commit and Push Feature Changes:** Ensure all feature work is merged to `main`.
2. **Create and Push the Git RC Tag:**
   ```bash
   # Create RC tag locally
   git tag v1.2.3rc1

   # Push tag to GitHub (triggers deploy/staging.yaml on Cloud Build)
   git push origin v1.2.3rc1
   ```
3. **Verify Staging Build on TestPyPI:**
   - `staging.yaml` runs `apply_version_bump.sh 1.2.3rc1` in memory and publishes wheels to TestPyPI.
   - Verify package availability at `https://test.pypi.org/project/datacommons-cli/1.2.3rc1/`.
   - Test installation in a clean environment:
     ```bash
     uv tool install --force \
       --index-url https://test.pypi.org/simple/ \
       --extra-index-url https://pypi.org/simple/ \
       "datacommons-cli==1.2.3rc1"
     ```

---

### Step 2: Production Version Bump PR

Once the RC is verified:

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

1. **Draft GitHub Release:**
   - Navigate to [GitHub Releases](https://github.com/datacommonsorg/datacommons/releases).
   - Click **Draft a new release**.
   - Set tag to `v1.2.3` on target `main`.
   - Title: `v1.2.3`.
   - Add release notes and click **Publish release**.
2. **Production Pipeline Execution (`release.yaml`):**
   - Publishing tag `v1.2.3` automatically triggers `deploy/release.yaml`.
   - `release.yaml` performs read-only validation that all committed files match `1.2.3`, builds wheels, and publishes to **Official PyPI**.
3. **Verify Production PyPI Release:**
   ```bash
   uv tool install --force "datacommons-cli==1.2.3"
   datacommons --version
   # Expected output: Data Commons CLI v1.2.3
   ```
