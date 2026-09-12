# Deployment and Release Operational Cheatsheet

This directory contains Google Cloud Build configuration files and automation scripts for releasing the Data Commons Platform (DCP).

> **Platform Specification**: For the complete end-to-end release lifecycle, PEP 440 release candidate conventions, PyPI immutability rules, and recovery procedures, refer to the [DCP Release and Versioning Guide](../docs/release.md).

---

## 1. Cloud Build Pipelines

### Stage 1: Stage a Release Candidate (RC) in TestPyPI
Submit `deploy/staging.yaml` to bump versions in-container, cross-tag release container images and the Dataflow template, push Git tag `vX.Y.ZrcN`, and publish candidate wheels to TestPyPI:

```bash
gcloud builds submit \
  --config deploy/staging.yaml \
  --substitutions=_TARGET_VERSION="1.1.2rc1",_DEFAULT_SOURCE_TAG="1.1.1",_SERVICES_TAG="1574ed3-79627f8-e265a1d" \
  --project="datcom-ci" \
  .
```

**Common Substitutions:**
| Parameter | Required | Description |
| :--- | :--- | :--- |
| `_TARGET_VERSION` | Yes | Target candidate version tag (for example, `1.1.2rc1`). |
| `_DEFAULT_SOURCE_TAG` | Yes | Baseline source tag inherited by container images unless overridden. |
| `_SERVICES_TAG` | No | Source commit SHA or tag for `datacommons-services`. |
| `_PREPROCESSOR_TAG` | No | Source tag for `datacommons-data` (preprocessor). |
| `_POSTPROCESSOR_TAG` | No | Source tag for `datacommons-aggregation-helper` (postprocessor). |
| `_INGESTION_HELPER_TAG` | No | Source tag for `datacommons-ingestion-helper`. |
| `_DATAFLOW_TEMPLATE_TAG` | No | Source tag for Dataflow Flex Template spec in GCS. |

---

### Stage 2: Open Automated Version Bump PR
Once the candidate is verified on TestPyPI, submit `deploy/bump_version.yaml` to promote candidate container tags to production tags and open an automated PR against `main`:

```bash
gcloud builds submit \
  --config deploy/bump_version.yaml \
  --substitutions=_NEW_VERSION="1.1.2",_PROMOTED_CANDIDATE_TAG="1.1.2rc1" \
  --project="datcom-ci" \
  .
```

**Common Substitutions:**
| Parameter | Required | Description |
| :--- | :--- | :--- |
| `_NEW_VERSION` | Yes | Production target version (for example, `1.1.2`). |
| `_PROMOTED_CANDIDATE_TAG` | Yes | Verified candidate tag to promote (for example, `1.1.2rc1`). |

---

### Stage 3: Production Release Publish
When the version bump PR is merged into `main`, draft and publish a GitHub Release with tag `vX.Y.Z`. The Cloud Build trigger `dcp-production-deployment` in `datcom-ci` executes `deploy/release.yaml` automatically to validate committed files and publish wheels to PyPI.

---

## 2. Release Automation Scripts (`deploy/scripts/`)

| Script | Purpose |
| :--- | :--- |
| `apply_version_bump.py` | Updates root `VERSION`, `packages/*/VERSION`, `pyproject.toml` dependency pins, and `infra/dcp/variables.tf`. |
| `tag_release_artifacts.py` | Cross-tags all 5 container images and stages the rendered Dataflow Flex Template JSON spec in GCS. |
| `validate_release_version.py` | Pre-publish validator asserting that all version files match the Git tag and remote container artifacts exist. |
| `publish_packages.py` | Builds wheels in an isolated sandbox, validates imports and CLI execution, and uploads packages to PyPI or TestPyPI. |

---

## 3. Local Pre-Flight Checks

Run these commands locally before initiating Cloud Build runs:

```bash
# Validate that all version files match a target tag
uv run deploy/scripts/validate_release_version.py v1.1.2

# Dry-run wheel packaging, sandbox installation, and CLI smoke test
uv run deploy/scripts/publish_packages.py --dry-run
```
