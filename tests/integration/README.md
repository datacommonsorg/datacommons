# Data Commons Platform (DCP) — Integration Test Suite

A modular, data-driven end-to-end integration test harness for the Data Commons Platform (DCP).

It exercises all core components of the platform across 4 execution stages:
1. **Ingestion (`suites/01_ingestion/`):** CLI initialization, Spanner Node graph & observation seeding, and Cloud Workflows / Dataflow verification.
2. **Postprocessing (`suites/02_postprocessing/`):** Statistical Variable Group (SVG) hierarchy trees and Spanner vector embeddings semantic search.
3. **Serving API (`suites/03_serving_api/`):** Python SDK (`datacommons-client`), `/v2/observation` (point & series), `/v2/node`, and SDMX 3.0 REST endpoints.
4. **AI Agent & MCP (`04_mcp_agent/`):** Model Context Protocol (MCP) JSON-RPC 2.0 tool execution (`search_indicators`, etc.).

---

## 🚀 Quick Start

### 1. Run Tests for a Single Dataset Against a Testbed (e.g. `testbed-1`)
```bash
uv run python tests/integration/run_e2e_tests.py \
    --instance testbed-1 \
    --test-config foobar_wages \
    --reuse-data
```

### 2. Run Composed Multi-Dataset Tests
You can combine multiple dataset specs directly on the CLI:
```bash
uv run python tests/integration/run_e2e_tests.py \
    --instance testbed-1 \
    --test-config foobar_wages \
    --test-config foobar_education \
    --reuse-data
```

### 3. Run a Specific Stage / Suite
```bash
# Run only Serving API suite:
uv run python tests/integration/run_e2e_tests.py \
    --instance testbed-1 \
    --test-config foobar_wages \
    --suite 03_serving_api \
    --reuse-data

# Run only Ingestion suite:
uv run python tests/integration/run_e2e_tests.py \
    --instance testbed-1 \
    --test-config foobar_wages \
    --suite 01_ingestion
```

---

## 📊 Structured Reporting & GCS Publishing

The runner automatically generates structured JSON reports with timestamp-sorted, context-rich filenames:
`YYYYMMDDTHHMMSSZ_<instance>_<datasets>_<commit>_<status>.json`

### Output to a Local Directory:
```bash
uv run python tests/integration/run_e2e_tests.py \
    --instance testbed-1 \
    --test-config foobar_wages \
    --report-output ./test_reports/ \
    --reuse-data
```

### Output Directly to Google Cloud Storage (`gs://`):
```bash
uv run python tests/integration/run_e2e_tests.py \
    --instance testbed-1 \
    --test-config foobar_wages \
    --report-output gs://testbed-1-dc-artifacts-datcom-dcp/integration_tests/ \
    --reuse-data
```

---

## 🎛️ CLI Package Testing (Local / TestPyPI / PyPI)

### Test Local CLI Development Source
```bash
uv run python tests/integration/run_e2e_tests.py \
    --instance testbed-1 \
    --test-config foobar_wages \
    --cli-source local
```

### Test Candidate CLI Package from TestPyPI
```bash
uv run python tests/integration/run_e2e_tests.py \
    --instance testbed-1 \
    --test-config foobar_wages \
    --cli-source testpypi \
    --cli-version 1.1.2rc1
```

---

## 📁 Directory Architecture

```
tests/integration/
├── README.md                      # This documentation
├── run_e2e_tests.py               # Master CLI & programmatic runner
├── conftest.py                    # Pytest lifecycle hooks & dynamic parameterization
│
├── test_data/                     # Benchmark datasets & self-contained test specs
│   ├── foobar_wages/              # FooBar Wages CSV, MCF, config.json, test_spec.yaml
│   └── foobar_education/          # FooBar Education CSV, MCF, config.json, test_spec.yaml
│
├── suites/                        # Generic, dataset-agnostic test suites
│   ├── 01_ingestion/              # CLI Ingestion & Cloud Spanner graph verification
│   ├── 02_postprocessing/         # SVG hierarchy trees & vector embeddings
│   ├── 03_serving_api/            # datacommons-client (/v2/node, /v2/observation) & SDMX 3.0
│   └── 04_mcp_agent/              # Model Context Protocol (MCP) tool execution
│
├── core/                          # Runtime test execution engines
│   ├── target.py                  # DCPTarget and ArtifactConfig dataclasses
│   ├── resolver.py                # Discovers live endpoints & deployed images from Terraform
│   ├── cli_runner.py              # Subprocess DatacommonsCLI runner (local/testpypi/pypi)
│   ├── spanner_client.py          # Direct Cloud Spanner query client
│   ├── permissions.py             # Preflight IAM TokenCreator, GCS & Spanner verification
│   ├── mcp_client.py              # JSON-RPC 2.0 MCP client
│   ├── config_schema.py           # Typed manifest schemas, loader, and multi-spec merger
│   └── reporter.py                # Structured JSON reporter & timestamped GCS uploader
│
├── unit_tests/                    # Fast local unit tests (no GCP/network required)
│   └── test_config_schema.py      # Schema parsing, loader, and multi-manifest merge tests
│
└── tools/                         # Developer utilities
    └── synthesizer.py             # Auto-generates test_spec.yaml from raw dataset folders
```
