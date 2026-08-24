# Data Commons Platform (DCP) Release & Versioning Guide

This guide details the release procedure for the Data Commons Platform (DCP). All platform packages (`datacommons-cli`, `datacommons-admin`, etc.), Terraform modules, and container images share unified lockstep versioning anchored by the root [`VERSION`](../VERSION) file and the centralized versioning script [`deploy/scripts/apply_version_bump.py`](../deploy/scripts/apply_version_bump.py).

---

## 1. High-Level Release Overview

The release process follows three sequential stages:

1. **Stage 1: Stage a Release Candidate (RC) in TestPyPI**
   - **Pipeline:** `deploy/staging.yaml`
   - **Scripts:** [`apply_version_bump.py`](../deploy/scripts/apply_version_bump.py), [`tag_release_artifacts.py`](../deploy/scripts/tag_release_artifacts.py), [`publish_packages.py`](../deploy/scripts/publish_packages.py)
   - **Action:** Run `deploy/staging.yaml` with your target candidate version (e.g. `X.Y.ZrcN`) and artifact source tags. The build ephemerally bumps version files in-container, cross-tags the release container images and Dataflow Flex Template spec (see [`ARTIFACT_IMAGE_MAP`](../deploy/scripts/tag_release_artifacts.py)), pushes Git tag `vX.Y.ZrcN` to GitHub (*`main` branch remains untouched*), and publishes candidate wheels to **TestPyPI** for staging verification.

2. **Stage 2: Open & Merge Version Bump PR**
   - **Pipeline:** `deploy/bump_version.yaml`
   - **Scripts:** [`apply_version_bump.py`](../deploy/scripts/apply_version_bump.py), [`tag_release_artifacts.py`](../deploy/scripts/tag_release_artifacts.py)
   - **Action:** Run `deploy/bump_version.yaml` with the target release version (e.g. `X.Y.Z`) and candidate tag (`_PROMOTED_CANDIDATE_TAG`). The build promotes candidate artifacts to production tags, and opens an automated PR against `main` containing updated `VERSION` files, `infra/dcp/variables.tf`, and `uv.lock`. Review and merge the PR into `main`.

3. **Stage 3: Publish Official Production Release**
   - **Pipeline:** `deploy/release.yaml`
   - **Scripts:** [`validate_release_version.py`](../deploy/scripts/validate_release_version.py), [`publish_packages.py`](../deploy/scripts/publish_packages.py)
   - **Action:** Create and publish a GitHub Release with tag `vX.Y.Z` on `main`. The [Cloud Build trigger `dcp-production-deployment`](https://console.cloud.google.com/cloud-build/triggers/edit/da2c3b51-0f87-44c5-a125-6024b4436bbb?project=datcom-ci) in `datcom-ci` automatically runs [`deploy/release.yaml`](../deploy/release.yaml), validates that committed files and remote release artifacts exist for `X.Y.Z`, and publishes official wheels to **PyPI**.

> [!IMPORTANT]
> **Clean-Room Pre-Publish Verification & Topological Order:** Before publishing packages to TestPyPI or PyPI, [`deploy/scripts/publish_packages.py`](../deploy/scripts/publish_packages.py) builds all wheels into an isolated temporary directory, creates a sandbox `uv venv`, and verifies dependency resolution against PyPI along with runtime smoke tests (module imports and CLI execution). If any dependency is unresolvable or if packaged data assets (e.g. `schema.sql`) are missing, the release aborts before any upload. Packages are published in strict topological dependency order (`datacommons-db` -> `datacommons-admin` -> `datacommons-cli`), satisfying lockstep version pins (`datacommons-db==VERSION` and `datacommons-admin==VERSION`).

---

## 2. Step-by-Step Release Walkthrough

### Phase 1: Stage & Verify a Release Candidate (RC) in TestPyPI

#### Step 1: Submit Staging Build (`deploy/staging.yaml`)
Submit `deploy/staging.yaml` with your target RC version and artifact source tags:
```bash
gcloud builds submit \
  --config deploy/staging.yaml \
  --substitutions=_TARGET_VERSION="1.1.2rc1",_DEFAULT_SOURCE_TAG="1.1.1",_SERVICES_TAG="1574ed3-79627f8-e265a1d" \
  --project="datcom-ci" \
  .
```

**Substitutions Reference:**
* `_TARGET_VERSION`: The target candidate version tag (e.g. `1.1.2rc1`) [Required].
* `_DEFAULT_SOURCE_TAG`: Baseline source tag inherited by all container images and the Dataflow template unless overridden.
* `_SERVICES_TAG`: Source tag or commit SHA for `datacommons-services`.
* `_PREPROCESSOR_TAG`: Source tag for `datacommons-data` (preprocessor).
* `_POSTPROCESSOR_TAG`: Source tag for `datacommons-aggregation-helper` (postprocessor).
* `_INGESTION_HELPER_TAG`: Source tag for `datacommons-ingestion-helper`.
* `_DATAFLOW_TEMPLATE_TAG` (or `_DATAFLOW_TAG`): Source tag for Dataflow Flex Template spec in GCS (redirects `latest` to `stable`).
* `_DATAFLOW_IMAGE_TAG`: Optional explicit override for Dataflow worker image tag. If omitted, dynamically extracted from the source Flex Template JSON.
* `_GITHUB_COMMIT`: Optional commit SHA on datacommons repository (defaults to `_GITHUB_BRANCH` / `main`).

**What this step does:**
1. Clones the target commit and runs `apply_version_bump.py "X.Y.ZrcN"` to update `VERSION`, `packages/*/VERSION`, `infra/dcp/variables.tf`, and lock `datacommons-admin==X.Y.ZrcN`.
2. Creates a local commit and force-pushes Git tag `vX.Y.ZrcN` to GitHub (*`main` branch remains clean*).
3. Runs [`tag_release_artifacts.py`](../deploy/scripts/tag_release_artifacts.py) to cross-tag all 5 container images and stage the rendered Dataflow Flex Template JSON spec in GCS.
4. Runs `publish_packages.py --target testpypi` to verify package resolution & imports in an isolated sandbox, then upload candidate wheels to **TestPyPI** in topological order.

#### Step 2: Verify Release Candidate on Staging
- [ ] **TestPyPI Package Check:** Confirm wheels exist at `https://test.pypi.org/project/datacommons-cli/X.Y.ZrcN/`.
- [ ] **CLI Installation Test:** Install the candidate in an isolated terminal:
  ```bash
  uv tool install --force \
    --default-index https://test.pypi.org/simple/ \
    --index https://pypi.org/simple/ \
    --index-strategy unsafe-first-match \
    --prerelease=allow \
    "datacommons-cli==X.Y.ZrcN"

  datacommons --version
  # Output: Data Commons CLI, version X.Y.ZrcN
  ```
- [ ] **Scaffolding & Terraform Plan Test:** Initialize a test deployment stack:
  ```bash
  datacommons admin init \
    --project-id my-gcp-project \
    --instance-name test-rc-stack
  ```
  Run `cd test-rc-stack && terraform init && terraform plan` and verify that the plan output resolves container images tagged with `:X.Y.ZrcN`.

---

### Phase 2: Open & Merge Production Version Bump PR

Once the RC is verified on staging:

#### Step 1: Submit Version Bump PR Generator (`deploy/bump_version.yaml`)
Pass `_NEW_VERSION` and the verified `_PROMOTED_CANDIDATE_TAG`:
```bash
gcloud builds submit \
  --config deploy/bump_version.yaml \
  --substitutions=_NEW_VERSION="1.1.2",_PROMOTED_CANDIDATE_TAG="1.1.2rc1" \
  --project="datcom-ci" \
  .
```

**What this step does:**
1. Runs [`tag_release_artifacts.py`](../deploy/scripts/tag_release_artifacts.py) promoting all candidate images and the Dataflow Flex Template spec from `1.1.2rc1` to production `1.1.2`.
2. Clones `main` and checks out branch `chore/bump-version-1.1.2`.
3. Runs `apply_version_bump.py "1.1.2"` to update `VERSION`, `packages/*/VERSION`, `packages/datacommons-cli/pyproject.toml`, and `infra/dcp/variables.tf`.
4. Runs `uv lock` to update dependencies.
5. Commits changes, pushes the branch to GitHub, and opens a Pull Request against `main`.

#### Step 2: Review & Merge PR
1. Locate the auto-created PR (e.g. `chore: bump version to 1.1.2`) on GitHub.
2. Verify that `VERSION`, `packages/*/VERSION`, `packages/datacommons-cli/pyproject.toml`, and `infra/dcp/variables.tf` are updated to `1.1.2`.
3. Approve and merge the PR into `main`.

---

### Phase 3: Publish Production Release to PyPI

#### Step 1: Draft & Publish GitHub Release
1. Navigate to [GitHub Releases](https://github.com/datacommonsorg/datacommons/releases).
2. Click **Draft a new release**.
3. Fill out the fields:
   * **Choose a tag:** `vX.Y.Z` (select `+ Create new tag: vX.Y.Z on publish`).
   * **Target:** `main` (must contain the merged version bump PR).
   * **Release title:** `vX.Y.Z`.
   * **Description:** Paste curated release notes.
4. Click **Publish release**.

**What this step triggers ([`deploy/release.yaml`](../deploy/release.yaml)):**
* The [Cloud Build trigger `dcp-production-deployment`](https://console.cloud.google.com/cloud-build/triggers/edit/da2c3b51-0f87-44c5-a125-6024b4436bbb?project=datcom-ci) in `datcom-ci` automatically runs [`deploy/release.yaml`](../deploy/release.yaml) on tag push `vX.Y.Z` (matching regex `^v\d+\.\d+\.\d+$`).
* Runs `deploy/scripts/validate_release_version.py "vX.Y.Z" --check-remote-artifacts` to perform **strict pre-publish validation**:
  - Asserts root `VERSION == X.Y.Z`.
  - Asserts all `packages/*/VERSION == X.Y.Z`.
  - Asserts `packages/datacommons-cli/pyproject.toml` locks `datacommons-admin==X.Y.Z`.
  - Asserts `packages/datacommons-admin/pyproject.toml` locks `datacommons-db==X.Y.Z`.
  - Asserts `infra/dcp/variables.tf` defaults `dcp_version = "X.Y.Z"`.
  - **Remote Verification:** Asserts all 5 container images exist in GCR / Artifact Registry and the Dataflow Flex Template exists in GCS at tag `X.Y.Z`.
* Runs `deploy/scripts/publish_packages.py --target pypi` to verify package resolution & imports in an isolated sandbox, then upload official wheels to **Official PyPI** in topological order.

> [!TIP]
> Maintainers can run local pre-flight checks before staging or releasing:
> ```bash
> # Verify version consistency across all repo files:
> python3 deploy/scripts/validate_release_version.py vX.Y.Z
>
> # Test complete package build, sandbox installation, and CLI smoke test locally:
> python3 deploy/scripts/publish_packages.py --dry-run
> ```

#### Step 2: Verify Production Release
- [ ] **PyPI Live Check:** Confirm packages are live at `https://pypi.org/project/datacommons-cli/X.Y.Z/`.
- [ ] **CLI Upgrade Test:**
  ```bash
  uv tool install --force "datacommons-cli==X.Y.Z"
  datacommons --version
  # Output: Data Commons CLI vX.Y.Z
  ```
- [ ] **Lockstep Dependency Check:** Run `pip list | grep datacommons` to confirm `datacommons-cli`, `datacommons-admin`, and `datacommons-db` are all at `X.Y.Z`.

---

## 3. Pre-Releases, Immutability & Recovery Protocols

### Release Candidate (RC) Versioning Conventions
DCP uses standard [PEP 440](https://peps.python.org/pep-0440/) release candidate identifiers (e.g. `X.Y.Zrc1`, `X.Y.Zrc2`) for staging and pre-release testing builds.

Package managers like `uv` and `pip` treat release candidates safely: they will **not** install candidate packages automatically unless explicitly requested with the candidate version string (e.g. `"datacommons-cli==X.Y.ZrcN"`) or the `--pre` flag.

### What if a Release Candidate (RC) fails testing?
Do **not** overwrite or edit tag `vX.Y.ZrcN`. Fix the bug on `main`, and submit a new staging build with the next increment (`X.Y.Zrc(N+1)`):
```bash
gcloud builds submit \
  --config deploy/staging.yaml \
  --substitutions=_TARGET_VERSION="X.Y.Zrc2" \
  --project="datcom-ci" \
  .
```

### PyPI Version Immutability & Yanking
* **Immutability:** Once a specific version number (e.g. `X.Y.Z`) is published to PyPI or TestPyPI, its artifacts are **permanent and immutable**. PyPI will reject re-uploading wheels for an existing version number even if deleted.
* **Yanking a Broken Release:** If a critical defect is discovered in a published PyPI release:
  1. Navigate to the release on [PyPI](https://pypi.org/manage/project/datacommons-cli/releases/) and select **Yank release** with a reason.
  2. Yanking prevents `pip` and `uv` from installing the broken version by default while preserving reproducibility for existing pinned environments.
  3. Immediately cut and publish a patch release (e.g. `X.Y.(Z+1)`).

### What if `release.yaml` fails pre-publish validation?
If `release.yaml` aborts with `ERROR: Release tag (X.Y.Z) does not match VERSION file`:
1. Check whether the version bump PR was merged into `main` prior to creating the GitHub Release.
2. Delete the release draft/tag on GitHub, merge the version bump PR, and re-publish tag `vX.Y.Z`.
