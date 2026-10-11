# Testing & Previewing `check_terraform.py`

This directory contains hermetic unit tests for `check_terraform.py`.

The tests use a minimal, cloud-free Terraform fixture (`fixtures/baseline/`) that runs in `<0.1s` without GCP credentials or provider downloads.

You can use these tests to **preview the exact CLI output** for any check failure or pass scenario while modifying `check_terraform.py`.

---

## Preview Scenarios Live

Use `pytest -s -k <scenario>` to print the authentic CLI output directly to your screen for any scenario.

Common examples:
- **All checks pass (multiple unit modules pass)**:
  ```bash
  uv run pytest -s infra/dcp/scripts/tests/test_check_terraform.py -k test_all_pass
  ```
- **Formatting failure (targeted `--fmt`)**:
  ```bash
  uv run pytest -s infra/dcp/scripts/tests/test_check_terraform.py -k test_fmt_fails
  ```
- **Validation init failure (targeted `--validate`)**:
  ```bash
  uv run pytest -s infra/dcp/scripts/tests/test_check_terraform.py -k test_validate_init_fails
  ```
- **Validation command failure (targeted `--validate`)**:
  ```bash
  uv run pytest -s infra/dcp/scripts/tests/test_check_terraform.py -k test_validate_cmd_fails
  ```
- **Unit test failure (targeted `--test` with mixed pass/fail)**:
  ```bash
  uv run pytest -s infra/dcp/scripts/tests/test_check_terraform.py -k test_unit_test_fails_mixed
  ```
- **Compound failure (formatting fails, validation fails, all unit modules fail)**:
  ```bash
  uv run pytest -s infra/dcp/scripts/tests/test_check_terraform.py -k test_all_fail
  ```

To list all available test scenarios:
```bash
uv run pytest infra/dcp/scripts/tests/test_check_terraform.py --collect-only -q
```

---

## Running Tests

Run all tests:
```bash
uv run pytest infra/dcp/scripts/tests/test_check_terraform.py
```

Run all tests with output streaming:
```bash
uv run pytest -s infra/dcp/scripts/tests/test_check_terraform.py
```

---

## How It Works

1. Each test copies `fixtures/baseline/` into a temporary directory (`tmp_path`).
2. The test applies an isolated mutation (e.g. bad indentation, invalid syntax, or assertion mismatch).
3. It invokes `main([], tf_dir=tmp_path)` and captures the output.
4. Running with `-s` streams the exact colored terminal output to your screen.
