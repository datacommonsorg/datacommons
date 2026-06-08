# Release Guide

This repository implements lockstep versioning and automated CI/CD workflows using Google Cloud Build to publish package distributions to PyPI and TestPyPI.

---

## 1. Lockstep Versioning

All tracked packages (`packages/datacommons-admin` and `packages/datacommons-cli`) and the root project share the identical version number. 

Version changes are managed via automated inline replacements in:
* `__version__` within package `version.py` files (`packages/*/datacommons_*/version.py`).
* `version` within the root [pyproject.toml](../pyproject.toml).

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
Run a manual Cloud Build job to create the automated version-bump branch and Pull Request:

```bash
gcloud builds submit \
  --config deploy/bump_version.yaml \
  --substitutions=_NEW_VERSION="<new_version>" \
  --project="datcom-ci" \
  .
```

1. Review the generated Pull Request (e.g., `chore: bump version to <new_version>`).
2. Approve and merge the PR into `main`.

### Step 2: Cut a Release
Once the version PR is merged into `main`:

#### Staging Release (TestPyPI)
Create and push an `rc` tag to automatically run the staging pipeline:
```bash
git tag v1.2.3rc1
git push origin v1.2.3rc1
```

#### Production Release (Official PyPI)
Publish a new release on GitHub to automatically tag the repository and publish to PyPI:
1. Go to [GitHub Releases](https://github.com/datacommonsorg/datacommons/releases) and click **Draft a new release**.
2. Click **Choose a tag**, type your new version tag (e.g., `v1.2.3`), and select **Create new tag on publish**.
3. Set target to `main`, set the Release title to your version tag (e.g., `v1.2.3`), click **Generate release notes** to automatically populate the description, and click **Publish release**.



