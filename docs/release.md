# Release Guide

This repository implements lockstep versioning and automated CI/CD workflows using Google Cloud Build to publish package distributions to PyPI and TestPyPI.

---

## 1. Lockstep Versioning

All tracked packages (under `packages/`) and the root project share an identical version number. 

Version changes are single-sourced via the root [VERSION](../VERSION) file:
* **Build-time:** Sub-packages resolve their version dynamically via a symlinked `VERSION` file in their directory.
* **Runtime:** Sub-packages resolve their `__version__` attribute dynamically using `importlib.metadata.version()`.

---

## 2. CI/CD Tiers

Automated builds are powered by **Google Cloud Build** in two distinct release tiers:

### Staging (Release Candidates)
* **Configuration**: [staging.yaml](/deploy/staging.yaml)
* **Trigger**: Pushing a pre-release tag matching `v*rc*` (e.g., `v1.2.3rc1`).
* **Build-Time Actions**:
  * Stamps the tag version into the root `VERSION` file and all subpackage `__init__.py` files.
  * Dynamically updates the `dcp_version` default in `infra/dcp/variables.tf` to match the RC tag, ensuring packaged Terraform templates pull matching release candidate container images and Dataflow templates by default.
* **Output**: Publishes all non-experimental packages to **TestPyPI**.

### Production Release
* **Configuration**: [release.yaml](/deploy/release.yaml)
* **Trigger**: Publishing a release tag matching `v*` (e.g., `v1.2.3`, *no `rc` suffix*).
* **Build-Time Actions**:
  * Validates that the git release tag strictly matches the checked-in [VERSION](../VERSION) file.
  * Stamps `__version__` in subpackage `__init__.py` files.
* **Output**: Publishes all non-experimental packages to **Official PyPI**.

---

## 3. Release Workflows

The release process follows a two-step sequence: first publish and verify a Release Candidate (RC) on **TestPyPI**, then execute the version bump and publish the official release to **PyPI**.

### Step 1: Staging Pre-Release (TestPyPI)

Before opening the production version bump PR, create and push an `rc` tag to trigger the staging pipeline:

1. **Tag & Push RC Tag:**
   ```bash
   git tag v1.2.3rc1
   git push origin v1.2.3rc1
   ```
   * Pushing `v1.2.3rc1` automatically triggers `deploy/staging.yaml` via Cloud Build.
2. **Verify on TestPyPI:**
   * Confirm the package is live at `https://test.pypi.org/project/datacommons-admin/1.2.3rc1/`.
   * Test installation in a clean environment:
     ```bash
     pip install --upgrade --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ datacommons-admin==1.2.3rc1
     ```
3. **Verify Deployment:**
   * Initialize and test a deployment with `datacommons admin init` or update `dcp_version = "1.2.3rc1"` on a test stack to verify end-to-end data ingestion and service health.

---

### Step 2: Production Version Bump & PyPI Release

Once the release candidate is verified on TestPyPI and staging environments:

#### A. Bump Version & Merge PR

Trigger Cloud Build to automatically create a version-bump branch and GitHub Pull Request:
```bash
gcloud builds submit \
  --config deploy/bump_version.yaml \
  --substitutions=_NEW_VERSION="1.2.3" \
  --project="datcom-ci" \
  .
```
1. Go to GitHub and locate the auto-created PR (e.g., `chore: bump version to 1.2.3`).
2. Review that `VERSION`, `infra/dcp/variables.tf`, and `uv.lock` are updated to `1.2.3`.
3. Approve and merge the PR into `main`.

#### B. Publish Official GitHub Release

1. Go to [GitHub Releases](https://github.com/datacommonsorg/datacommons/releases).
2. Locate the auto-drafted release (e.g., `v1.2.3`) matching the newly bumped version.
3. Review and curate the release notes, and click **Publish release** (or run `gh release create v1.2.3 --target main`).
4. Publishing the GitHub Release creates tag `v1.2.3`, which automatically triggers `deploy/release.yaml` to build and publish the packages to **Official PyPI**.

#### C. Verify Production PyPI Release

1. Confirm packages are live on PyPI (`https://pypi.org/project/datacommons-admin/1.2.3/`).
2. Verify installation:
   ```bash
   pip install --upgrade datacommons-admin==1.2.3
   datacommons admin --version
   ```
