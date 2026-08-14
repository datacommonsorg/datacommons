# Data Commons Platform (DCP) Release & Versioning Guide

This guide details the release procedure for the Data Commons Platform (DCP). All platform packages (`datacommons-cli`, `datacommons-admin`, etc.), Terraform modules, and container images share unified lockstep versioning anchored by the root [`VERSION`](../VERSION) file and the centralized versioning script [`deploy/scripts/apply_version_bump.sh`](../deploy/scripts/apply_version_bump.sh).

---

## 1. High-Level Release Overview

The release process follows three sequential stages:

1. **Stage 1: Stage a Release Candidate (RC)**
   - Run `deploy/staging.yaml` with your target candidate version (e.g. `1.2.3rc1`).
   - The build ephemerally bumps version files in-container, pushes Git tag `v1.2.3rc1` to GitHub (*`main` branch remains untouched*), and publishes candidate wheels to **TestPyPI** for staging verification.
2. **Stage 2: Open & Merge Version Bump PR**
   - Run `deploy/bump_version.yaml` with the target release version (e.g. `1.2.3`).
   - The build opens an automated PR against `main` containing updated `VERSION` files, `infra/dcp/variables.tf`, and `uv.lock`.
   - Review and merge the PR into `main`.
3. **Stage 3: Publish Official Production Release**
   - Create and publish a GitHub Release with tag `v1.2.3` on `main`.
   - Cloud Build automatically validates that committed files match `1.2.3` and publishes official wheels to **PyPI**.

> [!IMPORTANT]
> **Package Build Order:** Packages are published alphabetically (`packages/*`). This guarantees `datacommons-admin` is published **before** `datacommons-cli`, satisfying the `datacommons-admin==VERSION` requirement on PyPI and TestPyPI.

---

## 2. Step-by-Step Release Walkthrough

### Phase 1: Stage & Verify a Release Candidate (RC)

#### Step 0: Tag Candidate Images & Flex Template
Ensure all core microservice images and the Dataflow flex template are built and tagged with the candidate version (e.g. `1.2.3rc1`):
* `gcr.io/datcom-ci/datacommons-services:1.2.3rc1`
* `gcr.io/datcom-ci/datacommons-data:1.2.3rc1`
* `gcr.io/datcom-ci/datacommons-ingestion-helper:1.2.3rc1`
* `gcr.io/datcom-ci/datacommons-aggregation-helper:1.2.3rc1`
* `us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion:1.2.3rc1`
* `gs://datcom-templates/templates/flex/ingestion-1.2.3rc1.json`

*(Note: Future followups will extend Cloud Build to automate image tagging).*

#### Step 1: Submit Staging Build (`deploy/staging.yaml`)
Submit `deploy/staging.yaml` with your target RC version:
```bash
# Build off latest main
gcloud builds submit \
  --config deploy/staging.yaml \
  --substitutions=_TARGET_VERSION="1.2.3rc1" \
  --project="datcom-ci" \
  .

# Or build off a specific commit SHA
gcloud builds submit \
  --config deploy/staging.yaml \
  --substitutions=_TARGET_VERSION="1.2.3rc1",_GITHUB_COMMIT="8f9b2a1" \
  --project="datcom-ci" \
  .
```

**What this step does:**
* Clones the target commit into a clean build container.
* Runs `apply_version_bump.sh "1.2.3rc1"` to update `VERSION`, `packages/*/VERSION`, `infra/dcp/variables.tf`, and lock `datacommons-admin==1.2.3rc1`.
* Creates a local commit containing these updated version files and force-pushes Git tag `v1.2.3rc1` to GitHub.
  *(Note: Tag `v1.2.3rc1` on GitHub points directly to this commit so remote Terraform module fetches via `?ref=v1.2.3rc1` resolve `default = "1.2.3rc1"` in `variables.tf`, while branch `main` remains clean).*
* Builds package wheels in subshells and publishes them to **TestPyPI**.

#### Step 2: Verify Release Candidate on Staging
- [ ] **TestPyPI Package Check:** Confirm wheels exist at `https://test.pypi.org/project/datacommons-cli/1.2.3rc1/`.
- [ ] **CLI Installation Test:** Install the candidate in an isolated terminal:
  ```bash
  uv tool install --force \
    --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    "datacommons-cli==1.2.3rc1"

  datacommons --version
  # Output: Data Commons CLI v1.2.3rc1
  ```
- [ ] **Scaffolding & Terraform Plan Test:** Initialize a test deployment stack:
  ```bash
  datacommons admin init \
    --project-id my-gcp-project \
    --instance-name test-rc-stack
  ```
  Run `cd test-rc-stack && terraform init && terraform plan` and verify that the plan output resolves container images tagged with `:1.2.3rc1`.

---

### Phase 2: Open & Merge Production Version Bump PR

Once the RC is verified on staging:

#### Step 1: Submit Version Bump PR Generator (`deploy/bump_version.yaml`)
```bash
gcloud builds submit \
  --config deploy/bump_version.yaml \
  --substitutions=_NEW_VERSION="1.2.3" \
  --project="datcom-ci" \
  .
```

**What this step does:**
* Clones `main` and checks out branch `chore/bump-version-1.2.3`.
* Runs `apply_version_bump.sh "1.2.3"` to update `VERSION`, `packages/*/VERSION`, `packages/datacommons-cli/pyproject.toml`, and `infra/dcp/variables.tf`.
* Runs `uv lock` to update dependencies.
* Commits changes, pushes the branch to GitHub, and opens a Pull Request against `main`.

#### Step 2: Review & Merge PR
1. Locate the auto-created PR (e.g. `chore: bump version to 1.2.3`) on GitHub.
2. Verify that `VERSION`, `packages/*/VERSION`, `packages/datacommons-cli/pyproject.toml`, and `infra/dcp/variables.tf` are updated to `1.2.3`.
3. Approve and merge the PR into `main`.

---

### Phase 3: Publish Production Release to PyPI

#### Step 0: Tag Production Images & Flex Template
Ensure all production container images and Dataflow flex template are tagged with the release version (`1.2.3`):
* `gcr.io/datcom-ci/datacommons-services:1.2.3`
* `gcr.io/datcom-ci/datacommons-data:1.2.3`
* `gcr.io/datcom-ci/datacommons-ingestion-helper:1.2.3`
* `gcr.io/datcom-ci/datacommons-aggregation-helper:1.2.3`
* `us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion:1.2.3`
* `gs://datcom-templates/templates/flex/ingestion-1.2.3.json`

#### Step 1: Draft & Publish GitHub Release
1. Navigate to [GitHub Releases](https://github.com/datacommonsorg/datacommons/releases).
2. Click **Draft a new release**.
3. Fill out the fields:
   * **Choose a tag:** `v1.2.3` (select `+ Create new tag: v1.2.3 on publish`).
   * **Target:** `main` (must contain the merged version bump PR).
   * **Release title:** `v1.2.3`.
   * **Description:** Paste curated release notes.
4. Click **Publish release**.

**What this step triggers (`deploy/release.yaml`):**
* Cloud Build automatically runs `deploy/release.yaml` on tag push `v1.2.3`.
* Performs **strict read-only validation**:
  - Asserts root `VERSION == 1.2.3`.
  - Asserts all `packages/*/VERSION == 1.2.3`.
  - Asserts `datacommons-cli/pyproject.toml` locks `datacommons-admin==1.2.3`.
  - Asserts `infra/dcp/variables.tf` defaults `dcp_version = "1.2.3"`.
* Builds package wheels in subshells and publishes them to **Official PyPI**.

#### Step 2: Verify Production Release
- [ ] **PyPI Live Check:** Confirm packages are live at `https://pypi.org/project/datacommons-cli/1.2.3/`.
- [ ] **CLI Upgrade Test:**
  ```bash
  uv tool install --force "datacommons-cli==1.2.3"
  datacommons --version
  # Output: Data Commons CLI v1.2.3
  ```
- [ ] **Lockstep Dependency Check:** Run `pip list | grep datacommons` to confirm `datacommons-cli` and `datacommons-admin` are both at `1.2.3`.

---

## 3. Pre-Releases, Immutability & Recovery Protocols

### Pre-Release Versioning Conventions (Alpha, Beta, RC)
DCP uses standard [PEP 440](https://peps.python.org/pep-0440/) pre-release identifiers for staging and testing builds:
* **Alpha (`1.2.3a1`, `1.2.3a2`)**: Early internal testing builds.
* **Beta (`1.2.3b1`, `1.2.3b2`)**: Feature-complete integration builds.
* **Release Candidate (`1.2.3rc1`, `1.2.3rc2`)**: Final staging builds prior to production.

Package managers like `uv` and `pip` treat pre-releases safely: they will **not** install pre-release packages automatically unless explicitly requested with the pre-release version string (e.g. `"datacommons-cli==1.2.3rc1"`) or the `--pre` flag.

### What if a Release Candidate (RC) fails testing?
Do **not** overwrite or edit tag `v1.2.3rc1`. Fix the bug on `main`, and submit a new staging build with the next increment (`1.2.3rc2`):
```bash
gcloud builds submit \
  --config deploy/staging.yaml \
  --substitutions=_TARGET_VERSION="1.2.3rc2" \
  --project="datcom-ci" \
  .
```

### PyPI Version Immutability & Yanking
* **Immutability:** Once a specific version number (e.g. `1.2.3`) is published to PyPI or TestPyPI, its artifacts are **permanent and immutable**. PyPI will reject re-uploading wheels for an existing version number even if deleted.
* **Yanking a Broken Release:** If a critical defect is discovered in a published PyPI release:
  1. Navigate to the release on [PyPI](https://pypi.org/manage/project/datacommons-cli/releases/) and select **Yank release** with a reason.
  2. Yanking prevents `pip` and `uv` from installing the broken version by default while preserving reproducibility for existing pinned environments.
  3. Immediately cut and publish a patch release (e.g. `1.2.4`).

### What if `release.yaml` fails pre-publish validation?
If `release.yaml` aborts with `ERROR: Release tag (1.2.3) does not match VERSION file`:
1. Check whether the version bump PR was merged into `main` prior to creating the GitHub Release.
2. Delete the release draft/tag on GitHub, merge the version bump PR, and re-publish tag `v1.2.3`.
