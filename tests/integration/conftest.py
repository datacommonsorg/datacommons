# Copyright 2026 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest
import requests
from datacommons_client import DataCommonsClient
from google.cloud import storage

# Ensure repository root is in Python sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.integration.core.cli_runner import DatacommonsCLI
from tests.integration.core.config_schema import TestManifest, load_test_manifest
from tests.integration.core.mcp_client import MCPClient
from tests.integration.core.permissions import PreflightPermissionChecker
from tests.integration.core.reporter import TestReporter
from tests.integration.core.resolver import resolve_dcp_target
from tests.integration.core.spanner_client import SpannerClient
from tests.integration.core.target import ArtifactConfig, DCPTarget

_GLOBAL_REPORTER: TestReporter | None = None
_SESSION_START_TIME: float = 0.0


def pytest_addoption(parser):
    """Register custom CLI options for integration tests."""
    parser.addoption(
        "--instance",
        action="store",
        default=None,
        help="DCP testbed instance name (e.g. testbed-1, testbed-2)",
    )
    parser.addoption(
        "--project",
        action="store",
        default="datcom-dcp",
        help="GCP Project ID (default: datcom-dcp)",
    )
    parser.addoption(
        "--workspace",
        action="store",
        default=None,
        help="Path to local terraform workspace (default: tests/testbed/workspaces/<instance>)",
    )
    parser.addoption(
        "--cli-source",
        action="store",
        default="local",
        help="Source of datacommons CLI: 'local', 'testpypi', 'pypi'",
    )
    parser.addoption(
        "--cli-version",
        action="store",
        default=None,
        help="Specific version tag when testing testpypi or pypi CLI",
    )
    parser.addoption(
        "--target-tag",
        action="store",
        default=None,
        help="Target release or image tag (e.g. latest, dcp-stable, v1.1.1RC3)",
    )
    parser.addoption(
        "--reuse-data",
        action="store_true",
        default=False,
        help="Skip ingestion if Spanner already contains test observations",
    )
    parser.addoption(
        "--workflow-timeout",
        action="store",
        type=int,
        default=2400,
        help="Timeout in seconds to wait for ingestion workflow (default: 2400s / 40min)",
    )
    parser.addoption(
        "--test-config",
        action="append",
        default=[],
        help="Path to declarative test manifest YAML. Can be passed multiple times or comma-separated.",
    )
    parser.addoption(
        "--report-output",
        action="store",
        default="test_results.json",
        help="Destination to save JSON test report (local path or GCS URI, e.g. gs://bucket/path/results.json). Default: test_results.json",
    )
    parser.addoption(
        "--report-json",
        action="store",
        default=None,
        help="(Deprecated: use --report-output) Local file path to write JSON test report",
    )
    parser.addoption(
        "--gcs-report-bucket",
        action="store",
        default=None,
        help="(Deprecated: use --report-output gs://bucket/...) Optional GCS bucket to upload report",
    )


def _format_config_display(config_paths: Any) -> str:
    """Extracts clean dataset names from paths or manifest files."""
    if not config_paths:
        return "unspecified"
    if isinstance(config_paths, str):
        config_paths = [p.strip() for p in config_paths.split(",") if p.strip()]

    names = []
    for c in config_paths:
        p = Path(c)
        if p.name in ("test_spec.yaml", "test_spec.yml"):
            names.append(p.parent.name)
        elif p.stem in ("test_spec", "spec"):
            names.append(p.parent.name or p.stem)
        else:
            names.append(p.stem)
    return "+".join(names)


def pytest_configure(config):
    """Initialize structured reporter at the start of the pytest session."""
    global _GLOBAL_REPORTER, _SESSION_START_TIME

    _SESSION_START_TIME = time.time()

    test_configs = config.getoption("--test-config") or []
    config_display = _format_config_display(test_configs)

    _GLOBAL_REPORTER = TestReporter(
        target_instance=config.getoption("--instance") or "unknown",
        target_project=config.getoption("--project") or "datcom-dcp",
        test_config=config_display,
        cli_source=config.getoption("--cli-source") or "local",
        cli_version=config.getoption("--cli-version"),
        target_tag=config.getoption("--target-tag"),
    )


INTEGRATION_FIXTURES = {
    "expected_node_spec",
    "expected_edge_spec",
    "specialization_edge_spec",
    "indicator_spec",
    "node_query_spec",
    "point_obs_spec",
    "series_obs_spec",
    "sdmx_data_spec",
    "sdmx_avail_spec",
    "mcp_tool_spec",
}


def pytest_generate_tests(metafunc):
    """Dynamically parameterizes test functions from the active test manifest YAMLs."""
    # Skip parameterization if the test doesn't request any manifest-driven fixture (e.g. unit tests)
    if not any(f in metafunc.fixturenames for f in INTEGRATION_FIXTURES):
        return

    config_paths = metafunc.config.getoption("--test-config")
    if not config_paths:
        pytest.exit(
            "\n❌ Error: --test-config is required.\n"
            "Please specify one or more dataset names or manifest YAMLs, for example:\n"
            "  --test-config=foobar_wages\n"
            "  --test-config=foobar_wages --test-config=foobar_education\n",
            returncode=1,
        )
    manifest = load_test_manifest(config_paths)
    if _GLOBAL_REPORTER is not None and manifest.name:
        _GLOBAL_REPORTER.report.test_config = manifest.name

    # 1. Spanner Nodes
    if "expected_node_spec" in metafunc.fixturenames:
        nodes = (
            manifest.ingestion.spanner_expectations.expected_nodes
            if manifest.stages.ingestion
            else []
        )
        if nodes:
            metafunc.parametrize(
                "expected_node_spec", nodes, ids=[n.subject_id for n in nodes]
            )
        else:
            metafunc.parametrize("expected_node_spec", [None], ids=["disabled"])

    # 2. Spanner Edges
    if "expected_edge_spec" in metafunc.fixturenames:
        edges = (
            manifest.ingestion.spanner_expectations.expected_edges
            if manifest.stages.ingestion
            else []
        )
        if edges:
            metafunc.parametrize(
                "expected_edge_spec",
                edges,
                ids=[f"{e.subject_id}->{e.predicate}->{e.object_id}" for e in edges],
            )
        else:
            metafunc.parametrize("expected_edge_spec", [None], ids=["disabled"])

    # 3. SVG Hierarchy
    if "specialization_edge_spec" in metafunc.fixturenames:
        spec_edges = (
            manifest.postprocessing.svg_hierarchy.expected_specialization_edges
            if manifest.stages.postprocessing
            else []
        )
        if spec_edges:
            metafunc.parametrize(
                "specialization_edge_spec",
                spec_edges,
                ids=[
                    f"{s.subject_id}->specializationOf->{s.parent_svg}"
                    for s in spec_edges
                ],
            )
        else:
            metafunc.parametrize("specialization_edge_spec", [None], ids=["disabled"])

    # 4. Indicator Resolutions (Embeddings)
    if "indicator_spec" in metafunc.fixturenames:
        indicators = (
            manifest.postprocessing.indicator_resolutions
            if manifest.stages.postprocessing
            else []
        )
        if indicators:
            metafunc.parametrize(
                "indicator_spec", indicators, ids=[s.query for s in indicators]
            )
        else:
            metafunc.parametrize("indicator_spec", [None], ids=["disabled"])

    # 5. Serving API Nodes
    if "node_query_spec" in metafunc.fixturenames:
        nodes = manifest.serving_api.nodes if manifest.stages.serving_api else []
        if nodes:
            metafunc.parametrize(
                "node_query_spec", nodes, ids=[n.node_dcid for n in nodes]
            )
        else:
            metafunc.parametrize("node_query_spec", [None], ids=["disabled"])

    # 6. Point Observations
    if "point_obs_spec" in metafunc.fixturenames:
        point_obs = (
            manifest.serving_api.point_observations
            if manifest.stages.serving_api
            else []
        )
        if point_obs:
            metafunc.parametrize(
                "point_obs_spec",
                point_obs,
                ids=[f"{s.observation_about}-{s.variables}" for s in point_obs],
            )
        else:
            metafunc.parametrize("point_obs_spec", [None], ids=["disabled"])

    # 7. Series Observations
    if "series_obs_spec" in metafunc.fixturenames:
        series_obs = (
            manifest.serving_api.series_observations
            if manifest.stages.serving_api
            else []
        )
        if series_obs:
            metafunc.parametrize(
                "series_obs_spec",
                series_obs,
                ids=[f"{s.variables}" for s in series_obs],
            )
        else:
            metafunc.parametrize("series_obs_spec", [None], ids=["disabled"])

    # 8. SDMX Data Queries
    if "sdmx_data_spec" in metafunc.fixturenames:
        data_queries = (
            manifest.serving_api.sdmx_3_0.data_queries
            if (manifest.stages.serving_api and manifest.stages.sdmx)
            else []
        )
        if data_queries:
            metafunc.parametrize(
                "sdmx_data_spec",
                data_queries,
                ids=[
                    s.constraints.get("variableMeasured", f"sdmx_data_{i}")
                    for i, s in enumerate(data_queries)
                ],
            )
        else:
            metafunc.parametrize("sdmx_data_spec", [None], ids=["disabled"])

    # 9. SDMX Availability Queries
    if "sdmx_avail_spec" in metafunc.fixturenames:
        avail_queries = (
            manifest.serving_api.sdmx_3_0.availability_queries
            if (manifest.stages.serving_api and manifest.stages.sdmx)
            else []
        )
        if avail_queries:
            metafunc.parametrize(
                "sdmx_avail_spec",
                avail_queries,
                ids=[
                    s.constraints.get("variableMeasured", f"sdmx_avail_{i}")
                    for i, s in enumerate(avail_queries)
                ],
            )
        else:
            metafunc.parametrize("sdmx_avail_spec", [None], ids=["disabled"])

    # 10. MCP Tool Calls
    if "mcp_tool_spec" in metafunc.fixturenames:
        tool_calls = manifest.mcp_agent.tool_calls if manifest.stages.mcp_agent else []
        if tool_calls:
            metafunc.parametrize(
                "mcp_tool_spec",
                tool_calls,
                ids=[
                    f"{t.tool_name}-{t.arguments.get('query', '')}" for t in tool_calls
                ],
            )
        else:
            metafunc.parametrize("mcp_tool_spec", [None], ids=["disabled"])


def pytest_runtest_logreport(report):
    """Records individual test results in the global reporter."""
    global _GLOBAL_REPORTER
    if _GLOBAL_REPORTER is None:
        return

    if report.when == "call":
        error_msg = str(report.longrepr) if report.failed else None
        _GLOBAL_REPORTER.add_result(
            nodeid=report.nodeid,
            outcome=report.outcome,
            duration=report.duration,
            error_message=error_msg,
        )
    elif report.when == "setup" and report.skipped:
        _GLOBAL_REPORTER.add_result(
            nodeid=report.nodeid,
            outcome="skipped",
            duration=report.duration,
            error_message=str(report.longrepr) if hasattr(report, "longrepr") else None,
        )


def pytest_sessionfinish(session, exitstatus):
    """Saves structured report locally or uploads to GCS."""
    global _GLOBAL_REPORTER, _SESSION_START_TIME
    if _GLOBAL_REPORTER is None:
        return

    _GLOBAL_REPORTER.report.duration_seconds = time.time() - _SESSION_START_TIME

    # Determine report destination (local path or GCS URI)
    dest = (
        session.config.getoption("--report-output")
        or session.config.getoption("--report-json")
        or "test_results.json"
    )
    saved_location = _GLOBAL_REPORTER.save_report(dest)

    # Legacy GCS bucket flag support
    gcs_bucket = session.config.getoption("--gcs-report-bucket")
    if gcs_bucket and not dest.startswith("gs://"):
        _GLOBAL_REPORTER.save_report(f"gs://{gcs_bucket}/")

    # Print clean machine-readable summary block
    summary = _GLOBAL_REPORTER.to_dict()
    print("\n" + "=" * 80)
    print("DCP TEST EXECUTION SUMMARY")
    print("=" * 80)
    print(
        json.dumps(
            {
                "status": summary["status"],
                "summary": summary["summary"],
                "metadata": summary["metadata"],
                "report_location": saved_location,
            },
            indent=2,
        )
    )
    print("=" * 80 + "\n")


@pytest.fixture(scope="session")
def test_manifest(request) -> TestManifest:
    """Provides active TestManifest dataclass to tests."""
    config_path = request.config.getoption("--test-config")
    if not config_path:
        pytest.exit("Error: --test-config is required.", returncode=1)
    return load_test_manifest(config_path)


@pytest.fixture(scope="session")
def dcp_target(request, test_manifest) -> DCPTarget:
    """Provides resolved DCP target environment context to all tests."""
    artifacts = ArtifactConfig(
        cli_source=request.config.getoption("--cli-source"),
        cli_version=request.config.getoption("--cli-version"),
        target_tag=request.config.getoption("--target-tag"),
    )

    instance_opt = request.config.getoption("--instance")
    if instance_opt in ("local", "emulated"):
        from tests.integration.emulated.manager import EmulatedStackManager

        reuse_data_opt = request.config.getoption("--reuse-data", False)
        manager = EmulatedStackManager()
        target = manager.start(test_manifest, artifacts, reuse_data=reuse_data_opt)
        if _GLOBAL_REPORTER is not None:
            _GLOBAL_REPORTER.set_artifacts(asdict(target.artifacts))
            if target.artifacts.target_tag:
                _GLOBAL_REPORTER.report.target_tag = target.artifacts.target_tag
        yield target
        if not request.config.getoption("--reuse-data"):
            manager.stop()
        return

    target = resolve_dcp_target(
        instance=instance_opt,
        project=request.config.getoption("--project"),
        workspace=request.config.getoption("--workspace"),
        artifacts=artifacts,
    )

    if _GLOBAL_REPORTER is not None:
        _GLOBAL_REPORTER.set_artifacts(asdict(target.artifacts))
        if target.artifacts.target_tag:
            _GLOBAL_REPORTER.report.target_tag = target.artifacts.target_tag

    # Preflight Permission Checks
    checker = PreflightPermissionChecker(target)
    results = checker.verify_all()
    failed = [r for r in results if not r.passed]
    if failed:
        print("\n❌ [Preflight] Permission Checks Failed:")
        for f in failed:
            print(f"  • {f.name}: {f.details}")
            if f.fix_command:
                print(f"    Fix: {f.fix_command}")
        pytest.exit(
            "Preflight GCP permission checks failed. See instructions above.",
            returncode=1,
        )

    return target


@pytest.fixture(scope="session")
def dcp_cli(dcp_target: DCPTarget) -> DatacommonsCLI:
    """Provides DatacommonsCLI runner configured for the target workspace."""
    return DatacommonsCLI(
        workspace_dir=dcp_target.workspace_dir,
        artifacts=dcp_target.artifacts,
    )


@pytest.fixture(scope="session")
def spanner_client(dcp_target: DCPTarget) -> SpannerClient:
    """Provides direct Cloud Spanner client."""
    return SpannerClient(
        project_id=dcp_target.project_id,
        instance_id=dcp_target.spanner_instance,
        database_id=dcp_target.spanner_database,
    )


@pytest.fixture(scope="session")
def auth_headers() -> dict:
    """Provides default HTTP headers with GCP Cloud Run identity token if authenticated."""
    headers = {"X-Use-Multi-Entity-Schema": "true"}
    try:
        token = (
            subprocess.check_output(
                ["gcloud", "auth", "print-identity-token"],
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
            .decode()
            .strip()
        )
        if token:
            headers["Authorization"] = f"Bearer {token}"
    except Exception:
        pass
    return headers


@pytest.fixture(scope="session")
def dc_client(dcp_target: DCPTarget, auth_headers: dict):
    """Provides official datacommons-client Client connected to target testbed."""
    if not dcp_target.serving_url:
        pytest.skip("Serving URL not configured for target instance.")

    orig_session_request = requests.Session.request
    orig_requests_get = requests.get

    def patched_session_request(self, method, url, *args, **kwargs):
        if dcp_target.serving_url in str(url):
            h = kwargs.get("headers", {}) or {}
            h.update(auth_headers)
            kwargs["headers"] = h
        return orig_session_request(self, method, url, *args, **kwargs)

    def patched_get(url, *args, **kwargs):
        if dcp_target.serving_url in str(url):
            h = kwargs.get("headers", {}) or {}
            h.update(auth_headers)
            kwargs["headers"] = h
        return orig_requests_get(url, *args, **kwargs)

    requests.Session.request = patched_session_request
    requests.get = patched_get

    try:
        url = f"{dcp_target.serving_url}/core/api/v2"
        yield DataCommonsClient(url=url)
    except Exception as e:
        pytest.skip(f"datacommons-client not initialized: {e}")
    finally:
        requests.Session.request = orig_session_request
        requests.get = orig_requests_get


@pytest.fixture(scope="session")
def mcp_client(dcp_target: DCPTarget, auth_headers: dict) -> MCPClient:
    """Provides client for executing MCP tools against {serving_url}/mcp."""
    if not dcp_target.serving_url:
        pytest.skip("Serving URL not configured for target instance.")
    mcp_url = f"{dcp_target.serving_url}/mcp"
    return MCPClient(mcp_url=mcp_url, auth_headers=auth_headers)


@pytest.fixture(scope="session")
def seeded_testbed(dcp_target, dcp_cli, spanner_client, test_manifest, request):
    """
    Guarantees the test dataset is ingested and indexed before any test runs.
    Runs ONCE per test session across all suites.
    """
    reuse = request.config.getoption("--reuse-data")
    if reuse:
        count = spanner_client.count_observations()
        if count > 0:
            print(
                f"\n[Data Setup] Reusing {count} existing observations in Spanner. Skipping ingestion!"
            )
            return dcp_target

    if dcp_target.instance_name in ("local", "emulated"):
        return dcp_target

    if not test_manifest.stages.ingestion:
        print(
            "\n[Data Setup] Ingestion stage disabled in manifest. Skipping data seeding."
        )
        return dcp_target

    # 1. Upload Test Dataset files to GCS Bucket (per import subdirectory declared in manifest)
    repo_root = Path(__file__).resolve().parents[2]
    bucket_raw = (
        dcp_target.gcs_bucket
        or f"dcp-{dcp_target.instance_name}-{dcp_target.project_id}"
    )
    bucket_clean = bucket_raw.replace("gs://", "").strip().split("/")[0]

    import_names = []
    dataset_dirs = test_manifest.ingestion.dataset_dirs
    if not dataset_dirs:
        raise ValueError(
            f"❌ Error: Test manifest '{test_manifest.name}' has no ingestion.dataset_dirs defined."
        )

    if bucket_clean:
        try:
            storage_client = storage.Client(project=dcp_target.project_id)
            bucket = storage_client.bucket(bucket_clean)

            for d in dataset_dirs:
                import_dir = repo_root / d if not Path(d).is_absolute() else Path(d)
                if import_dir.exists() and import_dir.is_dir():
                    import_name = import_dir.name
                    import_names.append(import_name)
                    print(
                        f"\n[Data Setup] Uploading import '{import_name}' to gs://{bucket_clean}/ingestion/input/{import_name}/..."
                    )
                    for file_path in import_dir.glob("*"):
                        if file_path.is_file() and not file_path.name.startswith("."):
                            blob = bucket.blob(
                                f"ingestion/input/{import_name}/{file_path.name}"
                            )
                            blob.upload_from_filename(str(file_path))
                            print(f"    ✔ Uploaded {file_path.name}")
        except Exception as e:
            print(f"    [Warning] Could not upload datasets to GCS: {e}")

    return dcp_target
