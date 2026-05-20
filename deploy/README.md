# Deployment Guide

This repository uses **Google Cloud Build** for CI/CD, with two distinct deployment tiers.

## 1. Staging (Release Candidates)
- **Trigger**: Pushing a tag matching `v*` (specifically `rc` tags like `v1.1.3rc1`).
- **Config**: `deploy/staging.yaml`
- **Output**:
  - **PyPI**: All `datacommons-*` packages (TestPyPI) versioned to `X.Y.ZrcN`.
- **Purpose**: Verifying packages on TestPyPI before publishing to pypi.org.

### How to Create a Staging Release
Run the helper script to automatically find the next available RC version and push the tag:
```bash
python3 scripts/create_staging_tag.py
```
Or manually:
```bash
git tag vX.Y.Z.rcN
git push upstream vX.Y.Z.rcN
```

## 2. Production Release
- **Trigger**: Pushing a tag matching `v*` that is **NOT** an `rc` (e.g., `v1.1.3`).
- **Config**: `deploy/release.yaml`
- **Output**:
  - **PyPI**: All `datacommons-*` packages (Official PyPI) versioned to `X.Y.Z`.
- **Purpose**: Official public release to PyPI.

### Production Release Process
The process to release to production is a 2-step workflow: **Prepare** (Version Bump) -> **Release** (Tag & Deploy).

#### Step 1: Version Bump (Prepare)
Run this script to calculate the next version, update `pyproject.toml`, and create a PR.

```bash
python3 scripts/create_release_pr.py
# Follow the interactive prompt (Major/Minor/Patch)
```

1.  This triggers a Cloud Build job (`deploy/bump_version.yaml`).
2.  A Pull Request will be created (e.g., `chore: bump version to 1.1.4`).
3.  **Review and Merge** this PR into `main`.

#### Step 2: Deploy (Release)
Once the version bump is merged, create the official release to trigger deployment.

**Using GitHub UI (Recommended)**
1.  Go to [Draft a New Release](https://github.com/datacommonsorg/agent-toolkit/releases/new).
2.  **Choose a tag**: Create a new tag matching your bumped version (e.g., `v1.1.4`).
    *   *Critical: Must match the version you just merged into `pyproject.toml`.*
3.  **Target**: `main`.
4.  **Release title**: `v1.1.4`.
5.  **Description**: Generate release notes.
6.  Click **Publish release**.

**Or Manual Git Tag**
```bash
git checkout main
git pull
git tag v1.1.4
git push origin v1.1.4
```