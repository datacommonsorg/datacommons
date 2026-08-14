# Data Commons Platform (DCP) Release & Versioning Guide

This guide details the release procedure for the Data Commons Platform (DCP). All platform packages (`datacommons-cli`, `datacommons-admin`, etc.), Terraform modules, and container images share unified lockstep versioning anchored by the root [`VERSION`](../VERSION) file and the centralized versioning script [`deploy/scripts/apply_version_bump.sh`](../deploy/scripts/apply_version_bump.sh).

---

## 1. High-Level Release Overview

The release workflow consists of three distinct stages:

* **Stage 1: Release Candidate (RC Staging)**
  * **👤 Releaser Action:** Run `gcloud builds submit` targeting `deploy/staging.yaml` with candidate version (e.g. `1.2.3rc1`).
  * **🤖 Automated Action:** Ephemerally bumps version files in-container, creates a local commit, pushes Git tag `v1.2.3rc1` to GitHub (*`main` branch remains untouched*), and publishes wheels to **TestPyPI**.
* **Stage 2: Version Bump PR (Main Branch Sync)**
  * **👤 Releaser Action:** Run `gcloud builds submit` targeting `deploy/bump_version.yaml` with release version (e.g. `1.2.3`), then review and merge the generated PR into `main`.
  * **🤖 Automated Action:** Runs `apply_version_bump.sh`, updates `uv.lock`, commits changes, and opens an automated PR against `main`.
* **Stage 3: Production Release (PyPI & GitHub Release)**
  * **👤 Releaser Action:** Draft and publish an official GitHub Release with tag `v1.2.3` on `main`.
  * **🤖 Automated Action:** `deploy/release.yaml` runs **read-only validation** asserting that all committed files match `1.2.3`, then builds and publishes wheels to **Official PyPI**.

> [!IMPORTANT]
> **Package Build Order:** Packages are published alphabetically (`packages/*`). This guarantees `datacommons-admin` is published **before** `datacommons-cli`, satisfying the `datacommons-admin==VERSION` requirement on PyPI and TestPyPI.

---

## 2. Step-by-Step Release Walkthrough

### Phase 1: Stage & Verify a Release Candidate (RC)

#### Step 0: Component Image & Flex Template Tagging
Ensure all core microservice images and the Dataflow flex template are built and tagged with the candidate version (e.g. `1.2.3rc1`):
* `gcr.io/datcom-ci/datacommons-services:1.2.3rc1`
* `gcr.io/datcom-ci/datacommons-data:1.2.3rc1`
* `gcr.io/datcom-ci/datacommons-ingestion-helper:1.2.3rc1`
* `gcr.io/datcom-ci/datacommons-aggregation-helper:1.2.3rc1`
* `us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion:1.2.3rc1`
* `gs://datcom-templates/templates/flex/ingestion-1.2.3rc1.json`

*(Note: Future followups will extend Cloud Build to automate this image tagging step).*

#### Step 1: 👤 Releaser Action — Submit Staging Build
Submit `deploy/staging.yaml` targeting your RC version. (Optional: specify `_GITHUB_COMMIT="<SHA>"` to build off a specific commit):
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

#### Step 2: 🤖 Automated Pipeline Execution (`staging.yaml`)
1. Clones the target commit into a clean build container.
2. Executes `apply_version_bump.sh "1.2.3rc1"` to update `VERSION`, `packages/*/VERSION`, `infra/dcp/variables.tf`, and lock `datacommons-admin==1.2.3rc1`.
3. Creates a local commit containing these updated version files inside the container and force-pushes Git tag `v1.2.3rc1` to GitHub.
   *(Note: The remote tag `v1.2.3rc1` now points directly to this version-bumped commit on GitHub, ensuring remote Terraform module calls via `?ref=v1.2.3rc1` resolve `default = "1.2.3rc1"` in `variables.tf`, while branch `main` remains clean).*
4. Builds package wheels in subshells and publishes them to **TestPyPI**.

#### Step 3: ✅ Verification Checklist for Staging
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

Once the RC is fully verified on staging:

#### Step 1: 👤 Releaser Action — Submit Version Bump PR Generator
```bash
gcloud builds submit \
  --config deploy/bump_version.yaml \
  --substitutions=_NEW_VERSION="1.2.3" \
  --project="datcom-ci" \
  .
```

#### Step 2: 🤖 Automated Pipeline Execution (`bump_version.yaml`)
1. Clones `main` and checks out branch `chore/bump-version-1.2.3`.
2. Runs `apply_version_bump.sh "1.2.3"`.
3. Runs `uv lock` to update dependencies.
4. Commits tracked changes, pushes the branch to GitHub, and creates a Pull Request against `main`.

#### Step 3: 👤 Releaser Action — Review & Merge PR
1. Locate the auto-created PR (e.g. `chore: bump version to 1.2.3`) on GitHub.
2. Verify that `VERSION`, `packages/*/VERSION`, `packages/datacommons-cli/pyproject.toml`, and `infra/dcp/variables.tf` are updated to `1.2.3`.
3. Approve and merge the PR into `main`.

---

### Phase 3: Publish Production Release to PyPI

#### Step 0: Component Image & Flex Template Tagging
Ensure all production container images and Dataflow flex template are tagged with the official release version (`1.2.3`):
* `gcr.io/datcom-ci/datacommons-services:1.2.3`
* `gcr.io/datcom-ci/datacommons-data:1.2.3`
* `gcr.io/datcom-ci/datacommons-ingestion-helper:1.2.3`
* `gcr.io/datcom-ci/datacommons-aggregation-helper:1.2.3`
* `us-docker.pkg.dev/datcom-ci/gcr.io/dataflow-templates/ingestion:1.2.3`
* `gs://datcom-templates/templates/flex/ingestion-1.2.3.json`

#### Step 1: 👤 Releaser Action — Draft & Publish GitHub Release
1. Navigate to [GitHub Releases](https://github.com/datacommonsorg/datacommons/releases).
2. Click **Draft a new release**.
3. Fill out the fields:
   * **Choose a tag:** `v1.2.3` (select `+ Create new tag: v1.2.3 on publish`).
   * **Target:** `main` (must contain the merged version bump PR).
   * **Release title:** `v1.2.3`.
   * **Description:** Paste curated release notes.
4. Click **Publish release**.

#### Step 2: 🤖 Automated Pipeline Execution (`release.yaml`)
1. Cloud Build automatically triggers `deploy/release.yaml` on tag push `v1.2.3`.
2. Performs **strict read-only validation**:
   - Asserts root `VERSION == 1.2.3`.
   - Asserts all `packages/*/VERSION == 1.2.3`.
   - Asserts `datacommons-cli/pyproject.toml` locks `datacommons-admin==1.2.3`.
   - Asserts `infra/dcp/variables.tf` defaults `dcp_version = "1.2.3"`.
3. Builds package wheels in subshells and publishes them to **Official PyPI**.

#### Step 3: ✅ Verification Checklist for Production
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
