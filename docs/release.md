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
* **Output**: Publishes all non-experimental packages to **TestPyPI**.

### Production Release
* **Configuration**: [release.yaml](/deploy/release.yaml)
* **Trigger**: Pushing an official release tag matching `v*` (e.g., `v1.2.3`, *no `rc` suffix*).
* **Output**: Publishes all non-experimental packages to **Official PyPI**.

---

## 3. Release Workflows

### Step 1: Bump Version & Prepare PR

#### Recommended: Automated via Cloud Build
Trigger the Cloud Build job to automatically create a version-bump branch and GitHub Pull Request:
```bash
gcloud builds submit \
  --config deploy/bump_version.yaml \
  --substitutions=_NEW_VERSION="<new_version>" \
  --project="datcom-ci" \
  .
```
1. Go to GitHub and locate the auto-created PR (e.g., `chore: bump version to <new_version>`).
2. Review, approve, and merge the PR into `main`.

#### Alternative: Manual Local Bump (Not Recommended)
1. Update the version string in [VERSION](../VERSION) (e.g., `1.2.3`).
2. Run `uv lock && uv sync` to update the lockfile and sync package installations.
3. Commit `VERSION` and `uv.lock`, push to a new branch, and create a Pull Request against `main`.

### Step 2: Cut a Release
Once the version PR is merged into `main`:

#### Staging Release (TestPyPI)
Create and push an `rc` tag to automatically run the staging pipeline:
```bash
git tag v1.2.3rc1
git push origin v1.2.3rc1
```

#### Production Release (Official PyPI)
Once the version-bump Pull Request is merged into `main`, a draft release will be automatically created on GitHub with compiled release notes:
1. Go to [GitHub Releases](https://github.com/datacommonsorg/datacommons/releases).
2. Locate the auto-drafted release (e.g., `v1.2.3`) matching the newly bumped version.
3. Click **Edit** (pencil icon), review the generated release notes, and click **Publish release** to tag the repository and trigger the production publishing pipeline.

> [!WARNING]
> The tag published via the GitHub Release (or git command line) must match the version configured in the [VERSION](../VERSION) file to prevent deployment failures or version mismatches.
