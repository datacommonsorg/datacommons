# Data Commons Platform (DCP) Release & Versioning Guide

This guide provides a comprehensive, step-by-step procedure for release engineers and maintainers to safely cut Release Candidates (RC) and Production Releases across PyPI and TestPyPI.

---

## 1. Prerequisites & Required Access

Before executing any release workflow, ensure your environment meets the following requirements:

1. **CLI Tools Installed:**
   - [`gcloud`](https://cloud.google.com/sdk/docs/install) (authenticated to Google Cloud)
   - [`gh`](https://cli.github.com/) (GitHub CLI, authenticated via `gh auth login`)
   - [`uv`](https://docs.astral.sh/uv/) (Python package manager)
2. **GCP Project Access:**
   - Member access to project `datcom-ci` with `Cloud Build Editor` or `Cloud Build Service Account` permissions.
3. **Repository Access:**
   - Write access to repository `datacommonsorg/datacommons` to merge PRs and publish GitHub Releases.

---

## 2. Architectural Overview & Workflow Flowchart

All packages (`datacommons-cli`, `datacommons-admin`, `datacommons-services`, etc.) share lockstep versioning anchored by the root [`VERSION`](../VERSION) file.

### Release Flowchart

```
                 +---------------------------------------------+
                 | 1. Stage Release Candidate (staging.yaml)   |
                 | gcloud builds submit --substitutions...     |
                 +----------------------+----------------------+
                                        |
                                        v
                 +---------------------------------------------+
                 | TestPyPI & GitHub Tag (v1.2.3rc1)           |
                 | - Validated via: uv tool install ...        |
                 | - Validated via: datacommons admin init ... |
                 +----------------------+----------------------+
                                        |
                                        v
                 +---------------------------------------------+
                 | 2. Create Version Bump PR (bump_version.yaml|
                 | gcloud builds submit --substitutions...     |
                 +----------------------+----------------------+
                                        |
                                        v
                 +---------------------------------------------+
                 | Code Review & Merge PR to main             |
                 +----------------------+----------------------+
                                        |
                                        v
                 +---------------------------------------------+
                 | 3. Publish Production Release (release.yaml)|
                 | Publish GitHub Release tag (v1.2.3)         |
                 +----------------------+----------------------+
                                        |
                                        v
                 +---------------------------------------------+
                 | Official PyPI Live Release (v1.2.3)         |
                 +---------------------------------------------+
```

---

## 3. Pipeline Reference & Single Source of Truth

The build system relies on a single shared versioning script: [`deploy/scripts/apply_version_bump.sh`](../deploy/scripts/apply_version_bump.sh).

| Pipeline | Trigger / Method | Role & Actions | Version Bumping | Git Tag Action | Destination |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`staging.yaml`** | Manual `gcloud builds submit` | Release candidate staging | Executes `apply_version_bump.sh` | **Tags & Pushes `v<VERSION>` to GitHub** (no commit to `main`) | **TestPyPI** |
| **`bump_version.yaml`** | Manual `gcloud builds submit` | Automated version bump PR generator | Executes `apply_version_bump.sh` | **Creates PR branch on Git** | N/A |
| **`release.yaml`** | Publish GitHub Release `v*` | Production release | **Read-only validation** (verifies committed versions match tag) | **NO** | **Official PyPI** |

> [!IMPORTANT]
> **Package Build Order:** Packages are published alphabetically (`packages/*`). This guarantees `datacommons-admin` is published **before** `datacommons-cli`, satisfying the `datacommons-admin>=VERSION` requirement on PyPI and TestPyPI.

---

## 4. Step-by-Step Release Walkthrough

### Step 1: Stage & Verify a Release Candidate (RC)

Execute this step to publish an RC to TestPyPI for staging verification without modifying `main`:

1. **Submit Staging Build:**
   Run `gcloud builds submit` targeting `deploy/staging.yaml` with your target RC version. (Optional: pass `_GITHUB_COMMIT="<SHA>"` to build off a specific commit SHA):
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

2. **Automated Container Actions (`staging.yaml`):**
   - Clones target commit directly from GitHub into a clean workspace.
   - Runs `apply_version_bump.sh "1.2.3rc1"`.
   - Creates a local container commit and force-pushes Git tag `v1.2.3rc1` to GitHub (*branch `main` remains untouched*).
   - Builds wheels and publishes packages to **TestPyPI**.

3. **Verification Checklist for Staging:**
   - [ ] **TestPyPI Package Check:** Confirm wheels exist at `https://test.pypi.org/project/datacommons-cli/1.2.3rc1/`.
   - [ ] **CLI Installation Test:** Run in a clean isolated terminal:
     ```bash
     uv tool install --force \
       --index-url https://test.pypi.org/simple/ \
       --extra-index-url https://pypi.org/simple/ \
       "datacommons-cli==1.2.3rc1"

     datacommons --version
     ```
   - [ ] **Scaffolding Template Test:** Initialize a test deployment:
     ```bash
     datacommons admin init \
       --project-id my-gcp-project \
       --instance-name test-rc-stack
     ```
     Verify that `test-rc-stack/terraform.tfvars` does **not** hardcode a stale `dcp_version`, allowing modules to resolve `1.2.3rc1` by default.

---

### Step 2: Open & Merge Production Version Bump PR

Once the RC is verified on staging:

1. **Submit Version Bump PR Builder:**
   ```bash
   gcloud builds submit \
     --config deploy/bump_version.yaml \
     --substitutions=_NEW_VERSION="1.2.3" \
     --project="datcom-ci" \
     .
   ```
2. **Review & Merge PR:**
   - Locate the auto-created PR (e.g. `chore: bump version to 1.2.3`) on GitHub.
   - Verify that `VERSION`, `pyproject.toml`, `__init__.py` files, and `infra/dcp/*.tf` are updated to `1.2.3`.
   - Approve and merge the PR into `main`.

---

### Step 3: Publish Production Release to PyPI

1. **Draft & Publish GitHub Release:**
   - Go to [GitHub Releases](https://github.com/datacommonsorg/datacommons/releases).
   - Click **Draft a new release**.
   - Tag: `v1.2.3` (Target: `main`).
   - Title: `v1.2.3`.
   - Paste release notes and click **Publish release**.

2. **Automated Production Execution (`release.yaml`):**
   - Cloud Build automatically triggers `deploy/release.yaml`.
   - Performs **read-only validation** that committed files match `1.2.3`.
   - Builds wheels and publishes packages to **Official PyPI**.

3. **Verification Checklist for Production:**
   - [ ] **PyPI Live Check:** Confirm `https://pypi.org/project/datacommons-cli/1.2.3/` is active.
   - [ ] **CLI Upgrade Test:**
     ```bash
     uv tool install --force "datacommons-cli==1.2.3"
     datacommons --version
     # Output: Data Commons CLI v1.2.3
     ```
   - [ ] **Lockstep Dependency Check:** Run `pip list | grep datacommons` to confirm `datacommons-cli` and `datacommons-admin` are both at `1.2.3`.

---

## 5. Troubleshooting & Safety Protocols

### What if a Release Candidate (RC) fails testing?
Do **not** edit tag `v1.2.3rc1`. Simply fix the issue on `main`, and submit a new staging build with the next increment (`1.2.3rc2`):
```bash
gcloud builds submit \
  --config deploy/staging.yaml \
  --substitutions=_TARGET_VERSION="1.2.3rc2" \
  --project="datcom-ci" \
  .
```

### What if `release.yaml` fails validation?
If `release.yaml` aborts with `ERROR: Release tag (1.2.3) does not match VERSION file`:
1. Check if the version bump PR was merged into `main` prior to creating the GitHub Release.
2. Delete the draft/tag on GitHub, merge the version bump PR, and re-publish tag `v1.2.3`.

### PyPI Version Immutability
PyPI files and version numbers are **immutable**. Once `1.2.3` is published to PyPI, it cannot be overwritten or deleted. If a critical bug is discovered after PyPI publication, immediately issue a patch release (`1.2.4`).
