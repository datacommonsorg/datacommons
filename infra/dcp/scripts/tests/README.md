# Terraform Infrastructure Script Testing

This directory contains tests for the Python tooling in `infra/dcp/scripts/`. **Prerequisite**: `terraform` (`>= 1.7.0`) must be installed on your `PATH`.

---

## `check_terraform.py`

The tests in [`test_check_terraform.py`](test_check_terraform.py) use a minimal, provider-free Terraform fixture (`fixtures/baseline/`) that runs offline without GCP credentials or provider downloads.

The main purpose of this suite is to **preview what `check_terraform.py` output looks like across different pass and failure scenarios** without having to manually introduce broken HCL into `infra/dcp/`, while also verifying script behavior in CI.

### Preview Scenarios Live

1. **Preview all scenarios at once**:
   Run with `-s -v` to stream the full CLI output for every test scenario to your terminal:
   ```bash
   uv run pytest -s -v infra/dcp/scripts/tests/test_check_terraform.py
   ```
   *(Omit `-s -v` to run the test suite quietly.)*

2. **Preview a single scenario**:
   List the available test function names with `--collect-only -q`, then pass any test name from that output to `-s -k <test_name>`:
   ```bash
   # List available scenario test names (e.g., ...::test_all_pass, ...::test_all_fail)
   uv run pytest infra/dcp/scripts/tests/test_check_terraform.py --collect-only -q

   # Run a specific scenario from that list
   uv run pytest -s infra/dcp/scripts/tests/test_check_terraform.py -k test_all_fail
   ```

### How It Works & Adding a Script Test

1. **Fixture Setup**: The `baseline_tf` fixture copies `fixtures/baseline/` into an isolated temporary directory (`tmp_path / "tf_project"`).
2. **Mutate or Add Modules**: Write test HCL to `(tf_dir / "main.tf")` or call `_create_test_module(tf_dir, "<module_name>", pass_test=...)` to generate a submodule with a `tests/unit.tftest.hcl` suite.
3. **Execute & Capture**: Call `code, out = _run_and_capture(capsys, ["<flags>"], tf_dir=tf_dir)` to run `main(args, tf_dir=tf_dir)`, echo the output for `pytest -s`, and capture stdout/stderr.
4. **Assert Behavioral Invariants**: Assert on the exit `code`, file mutations on disk, and key culprit/diagnostic lines in `out` (avoid brittle assertions on decorative borders or exact spacing).
