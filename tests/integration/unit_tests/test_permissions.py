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

"""Unit tests for permissions.py (probe classification and the preflight run loop)."""

import json
import time
from collections.abc import Callable

import pytest
import requests
from google.api_core import exceptions as api_exceptions
from google.auth import exceptions as auth_exceptions

from tests.integration.core import permissions
from tests.integration.core.permissions import (
    PermissionCheck,
    PreflightPermissionChecker,
    ProbeOutcome,
    ProbeResult,
    StackServiceAccount,
    classify_exception,
    classify_http_response,
)
from tests.integration.core.target import DCPTarget

OK = ProbeResult(ProbeOutcome.OK)
RETRY = ProbeResult(ProbeOutcome.RETRY, "HTTP 403: denied")
FAIL = ProbeResult(ProbeOutcome.FAIL, "HTTP 404: not found")


def _response(status_code: int, text: str = "") -> requests.Response:
    resp = requests.Response()
    resp.status_code = status_code
    resp._content = text.encode()  # noqa: SLF001 - building a fake response
    return resp


def _iam_error_body(code: int, status: str) -> str:
    return json.dumps({"error": {"code": code, "status": status}})


def _sequence(*results: ProbeResult) -> Callable[[], ProbeResult]:
    """Returns a probe that yields results in order, repeating the last one."""
    calls = list(results)

    def probe() -> ProbeResult:
        return calls.pop(0) if len(calls) > 1 else calls[0]

    return probe


def _checker(
    *, interactive: bool = False, timeout_sec: float = 60
) -> PreflightPermissionChecker:
    target = DCPTarget(project_id="p", instance_name="prober-x", workspace_dir="/tmp/x")
    return PreflightPermissionChecker(
        target,
        timeout_sec=timeout_sec,
        poll_interval_sec=0,
        interactive=interactive,
    )


# =============================================================================
# Classification
# =============================================================================
@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (200, ProbeOutcome.OK),
        (403, ProbeOutcome.RETRY),
        (429, ProbeOutcome.RETRY),
        (500, ProbeOutcome.RETRY),
        (503, ProbeOutcome.RETRY),
        (400, ProbeOutcome.FAIL),
        (401, ProbeOutcome.FAIL),
        (404, ProbeOutcome.FAIL),
    ],
)
def test_classify_http_response(status_code: int, expected: ProbeOutcome) -> None:
    # Test: HTTP status mapping for HTTP-based probes.
    # Situation: A probe receives a response with the given status code.
    # Expectation: 200 is OK, propagation/transient statuses RETRY, the rest FAIL.
    result = classify_http_response(_response(status_code, "body"))
    assert result.outcome is expected
    if expected is not ProbeOutcome.OK:
        assert f"HTTP {status_code}" in result.detail


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            auth_exceptions.RefreshError(
                "Unable to acquire impersonated credentials",
                _iam_error_body(403, "PERMISSION_DENIED"),
            ),
            ProbeOutcome.RETRY,
        ),
        (
            auth_exceptions.RefreshError(
                "Unable to acquire impersonated credentials",
                _iam_error_body(400, "INVALID_ARGUMENT"),
            ),
            ProbeOutcome.FAIL,
        ),
        (
            auth_exceptions.RefreshError("PERMISSION_DENIED: no body"),
            ProbeOutcome.RETRY,
        ),
        (auth_exceptions.RefreshError("Reauthentication required"), ProbeOutcome.FAIL),
        # OAuth2 token endpoint bodies use a string "error" (expired user ADC).
        (
            auth_exceptions.RefreshError("invalid_grant", {"error": "invalid_grant"}),
            ProbeOutcome.FAIL,
        ),
        (
            auth_exceptions.RefreshError("invalid_grant", '{"error": "invalid_grant"}'),
            ProbeOutcome.FAIL,
        ),
        (auth_exceptions.RefreshError("x", "not json"), ProbeOutcome.FAIL),
        (api_exceptions.Forbidden("denied"), ProbeOutcome.RETRY),
        (api_exceptions.PermissionDenied("denied"), ProbeOutcome.RETRY),
        (api_exceptions.TooManyRequests("slow down"), ProbeOutcome.RETRY),
        (api_exceptions.ServiceUnavailable("unavailable"), ProbeOutcome.RETRY),
        (api_exceptions.DeadlineExceeded("timeout"), ProbeOutcome.RETRY),
        (auth_exceptions.TransportError("connection reset"), ProbeOutcome.RETRY),
        (requests.exceptions.ConnectionError("refused"), ProbeOutcome.RETRY),
        (api_exceptions.NotFound("missing"), ProbeOutcome.FAIL),
        (auth_exceptions.DefaultCredentialsError("no ADC"), ProbeOutcome.FAIL),
        (ValueError("unexpected"), ProbeOutcome.FAIL),
    ],
)
def test_classify_exception(error: Exception, expected: ProbeOutcome) -> None:
    # Test: Exception mapping for client-library and impersonation probes.
    # Situation: A probe raises the given exception.
    # Expectation: Permission/transient errors RETRY; everything else FAILs fast.
    result = classify_exception(error)
    assert result.outcome is expected
    assert type(error).__name__ in result.detail


# =============================================================================
# Run loop
# =============================================================================
def test_run_check_passes_immediately() -> None:
    # Test: Happy path.
    # Situation: The probe succeeds on the first call.
    # Expectation: The check passes and records elapsed time.
    result = _checker()._run_check(
        PermissionCheck(name="c", probe=_sequence(OK)),
        time.monotonic() + 60,
    )
    assert result.passed
    assert "Verified after" in result.details


def test_run_check_polls_until_propagated() -> None:
    # Test: IAM propagation is absorbed.
    # Situation: The probe returns RETRY twice, then OK.
    # Expectation: The check passes after polling.
    probe_calls = []

    def probe() -> ProbeResult:
        probe_calls.append(1)
        return RETRY if len(probe_calls) < 3 else OK

    result = _checker()._run_check(
        PermissionCheck(name="c", probe=probe), time.monotonic() + 60
    )
    assert result.passed
    assert len(probe_calls) == 3


def test_run_check_times_out_with_last_error_and_hint() -> None:
    # Test: A grant that never propagates.
    # Situation: The probe always returns RETRY and the deadline has passed.
    # Expectation: The check fails with the last error and the missing-role hint.
    result = _checker()._run_check(
        PermissionCheck(
            name="c",
            probe=_sequence(RETRY),
            required_role="roles/workflows.invoker",
        ),
        time.monotonic() - 1,
    )
    assert not result.passed
    assert "HTTP 403: denied" in result.details
    assert "roles/workflows.invoker" in result.details


def test_run_check_fail_does_not_poll() -> None:
    # Test: Non-retryable errors fail fast.
    # Situation: The probe returns FAIL.
    # Expectation: The check fails after exactly one probe call.
    probe_calls = []

    def probe() -> ProbeResult:
        probe_calls.append(1)
        return FAIL

    result = _checker()._run_check(
        PermissionCheck(name="c", probe=probe), time.monotonic() + 60
    )
    assert not result.passed
    assert len(probe_calls) == 1
    assert "HTTP 404" in result.details


def test_run_check_stops_polling_on_fail() -> None:
    # Test: A probe that changes from RETRY to FAIL while polling.
    # Situation: The probe returns RETRY, then FAIL.
    # Expectation: The check fails immediately with the FAIL detail.
    result = _checker()._run_check(
        PermissionCheck(name="c", probe=_sequence(RETRY, FAIL)),
        time.monotonic() + 60,
    )
    assert not result.passed
    assert "HTTP 404" in result.details


def test_fix_not_offered_when_not_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    # Test: Non-interactive runs (the scheduled prober) never change IAM.
    # Situation: A fixable check returns RETRY in a non-interactive run.
    # Expectation: No prompt is shown; the check just polls.
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("prompted"))
    result = _checker(interactive=False)._run_check(
        PermissionCheck(name="c", probe=_sequence(RETRY, OK), fix_command="grant"),
        time.monotonic() + 60,
    )
    assert result.passed


def test_declined_fix_fails_immediately(monkeypatch: pytest.MonkeyPatch) -> None:
    # Test: Declining an interactive fix.
    # Situation: A fixable check returns RETRY and the developer answers "n".
    # Expectation: The check fails right away with the fix command, without polling.
    monkeypatch.setattr("builtins.input", lambda _: "n")
    probe_calls = []

    def probe() -> ProbeResult:
        probe_calls.append(1)
        return RETRY

    result = _checker(interactive=True)._run_check(
        PermissionCheck(name="c", probe=probe, fix_command="grant"),
        time.monotonic() + 60,
    )
    assert not result.passed
    assert result.fix_command == "grant"
    assert len(probe_calls) == 1


def test_accepted_fix_then_polls(monkeypatch: pytest.MonkeyPatch) -> None:
    # Test: Accepting an interactive fix.
    # Situation: A fixable check returns RETRY, the developer accepts, the grant succeeds.
    # Expectation: The fix command runs and the check polls until OK.
    monkeypatch.setattr("builtins.input", lambda _: "y")
    ran = []

    class _Done:
        returncode = 0

    monkeypatch.setattr(
        permissions.subprocess,
        "run",
        lambda cmd, **_: ran.append(cmd) or _Done(),
    )
    result = _checker(interactive=True)._run_check(
        PermissionCheck(name="c", probe=_sequence(RETRY, OK), fix_command="grant"),
        time.monotonic() + 60,
    )
    assert result.passed
    assert ran == ["grant"]


def _stub_verify_all(
    monkeypatch: pytest.MonkeyPatch, checker: PreflightPermissionChecker
) -> None:
    """Stubs ADC and the caller GCS/Spanner probes so verify_all runs offline."""
    monkeypatch.setattr(permissions.google.auth, "default", lambda **_: (object(), "p"))
    monkeypatch.setattr(checker, "_probe_adc_refresh", lambda: OK)
    monkeypatch.setattr(checker, "_resolve_caller_email", lambda: "me@example.com")
    monkeypatch.setattr(checker, "_probe_gcs_write", lambda: OK)
    monkeypatch.setattr(checker, "_probe_spanner", lambda: OK)


def test_sa_check_skipped_when_impersonation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Test: Per-SA dependency between impersonation and the SA's own check.
    # Situation: The caller cannot impersonate the stack SA.
    # Expectation: The SA's own probe is never called and its result is a skip failure.
    checker = _checker()
    _stub_verify_all(monkeypatch, checker)
    monkeypatch.setattr(checker, "_probe_impersonation", lambda _sa: FAIL)
    sa_probe_calls = []
    sa = StackServiceAccount(
        label="Test SA",
        email="sa@p.iam.gserviceaccount.com",
        email_output="out",
        capability="do things",
        role="roles/x",
        probe=lambda _creds: sa_probe_calls.append(1) or OK,
    )
    monkeypatch.setattr(checker, "_stack_service_accounts", lambda: [sa])

    results = checker.verify_all()

    assert sa_probe_calls == []
    skipped = [r for r in results if r.name == "Test SA: can do things"]
    assert len(skipped) == 1
    assert not skipped[0].passed
    assert "cannot impersonate" in skipped[0].details


def test_verify_all_shares_one_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    # Test: One propagation budget for the whole phase.
    # Situation: The first check consumes the whole budget; a later check needs to wait.
    # Expectation: The later check fails without getting a fresh budget.
    checker = _checker(timeout_sec=0.2)
    _stub_verify_all(monkeypatch, checker)
    monkeypatch.setattr(checker, "_probe_gcs_write", _sequence(RETRY))
    monkeypatch.setattr(checker, "_probe_spanner", _sequence(RETRY, OK))
    monkeypatch.setattr(checker, "_stack_service_accounts", list)

    _adc_result, gcs_result, spanner_result = checker.verify_all()

    assert not gcs_result.passed
    assert not spanner_result.passed
    assert "propagation budget" in spanner_result.details


def test_verify_all_reports_missing_adc(monkeypatch: pytest.MonkeyPatch) -> None:
    # Test: Missing Application Default Credentials.
    # Situation: google.auth.default raises DefaultCredentialsError.
    # Expectation: One failed result telling the developer how to log in.
    def _raise(**_: object) -> None:
        raise auth_exceptions.DefaultCredentialsError("not found")

    monkeypatch.setattr(permissions.google.auth, "default", _raise)
    results = _checker().verify_all()
    assert len(results) == 1
    assert not results[0].passed
    assert "application-default login" in results[0].details


def test_verify_all_skips_emulated() -> None:
    # Test: Emulator runs skip GCP checks.
    # Situation: The target instance is "emulated".
    # Expectation: A single passing result without touching GCP.
    target = DCPTarget(
        project_id="default", instance_name="emulated", workspace_dir="/tmp/x"
    )
    results = PreflightPermissionChecker(target).verify_all()
    assert len(results) == 1
    assert results[0].passed


def test_accepted_fix_gets_a_fresh_propagation_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Test: A fix applied after the shared budget is spent.
    # Situation: The deadline has already passed; the developer accepts a fix.
    # Expectation: The new grant gets its own window, so RETRY then OK passes.
    monkeypatch.setattr("builtins.input", lambda _: "y")

    class _Done:
        returncode = 0

    monkeypatch.setattr(permissions.subprocess, "run", lambda *_, **__: _Done())
    result = _checker(interactive=True)._run_check(
        PermissionCheck(name="c", probe=_sequence(RETRY, RETRY, OK), fix_command="g"),
        time.monotonic() - 1,
    )
    assert result.passed


@pytest.mark.parametrize("failure", ["nonzero", "eof"])
def test_fix_that_cannot_be_applied_fails_immediately(
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    # Test: The fix command fails, or stdin closes at the prompt.
    # Situation: A fixable check returns RETRY in an interactive run.
    # Expectation: The check fails right away and reports the fix command.
    class _Failed:
        returncode = 1

    def _eof(_: str) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", _eof if failure == "eof" else lambda _: "y")
    monkeypatch.setattr(permissions.subprocess, "run", lambda *_, **__: _Failed())
    result = _checker(interactive=True)._run_check(
        PermissionCheck(name="c", probe=_sequence(RETRY, OK), fix_command="grant"),
        time.monotonic() + 60,
    )
    assert not result.passed
    assert result.fix_command == "grant"


def test_verify_all_stops_when_adc_cannot_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Test: Expired or revoked developer ADC.
    # Situation: ADC loads, but refreshing it raises an OAuth2 invalid_grant error.
    # Expectation: One clear failure with the login hint; no other checks run.
    class _BrokenCreds:
        def refresh(self, _request: object) -> None:
            raise auth_exceptions.RefreshError(
                "invalid_grant",
                {"error": "invalid_grant"},
            )

    monkeypatch.setattr(
        permissions.google.auth,
        "default",
        lambda **_: (_BrokenCreds(), "p"),
    )
    checker = _checker()
    monkeypatch.setattr(checker, "_probe_gcs_write", lambda: pytest.fail("ran"))
    results = checker.verify_all()
    assert len(results) == 1
    assert not results[0].passed
    assert "application-default login" in results[0].details


@pytest.mark.parametrize(
    ("email", "member"),
    [
        (
            "prober@p.iam.gserviceaccount.com",
            "serviceAccount:prober@p.iam.gserviceaccount.com",
        ),
        ("dev@example.com", "user:dev@example.com"),
        ("", None),
    ],
)
def test_member_spec_and_fix_availability(email: str, member: str | None) -> None:
    # Test: Fix commands are built for the resolved ADC identity.
    # Situation: The caller email is a service account, a user, or unknown.
    # Expectation: The member type matches, and no fix is offered when unknown.
    checker = _checker()
    checker.caller_email = email
    assert checker._member_spec() == member
    fix = checker._gcs_check().fix_command
    if member:
        assert f"--member='{member}'" in fix
    else:
        assert fix is None


class _FakeCreds:
    token = "fake-access-token"

    def __init__(self, email: str) -> None:
        self.service_account_email = email


def test_resolve_caller_email_from_service_account() -> None:
    # Test: Service account / Compute (refreshed) ADC.
    # Situation: Credentials expose service_account_email.
    # Expectation: That email is returned without calling tokeninfo.
    checker = _checker()
    checker._credentials = _FakeCreds("sa@p.iam.gserviceaccount.com")
    assert checker._resolve_caller_email() == "sa@p.iam.gserviceaccount.com"


@pytest.mark.parametrize(
    ("status_code", "body", "expected"),
    [
        (200, '{"email": "dev@example.com"}', "dev@example.com"),
        (400, '{"error": "invalid_token"}', ""),
    ],
)
def test_resolve_caller_email_from_tokeninfo(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    body: str,
    expected: str,
) -> None:
    # Test: User ADC (or Compute still reporting "default").
    # Situation: tokeninfo returns the email, or rejects the token.
    # Expectation: The email is returned, or "" so no fix is offered.
    checker = _checker()
    checker._credentials = _FakeCreds("default")
    monkeypatch.setattr(
        permissions.requests,
        "post",
        lambda *_, **__: _response(status_code, body),
    )
    assert checker._resolve_caller_email() == expected


def test_gcs_probe_maps_forbidden_to_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    # Test: The GCS probe wrapper classifies real client-library errors.
    # Situation: The upload raises api_core Forbidden (a 403 on the bucket).
    # Expectation: The probe returns RETRY so preflight waits for propagation.
    class _Blob:
        def upload_from_string(self, *_: object, **__: object) -> None:
            raise api_exceptions.Forbidden("denied")

    class _Bucket:
        def blob(self, _: str) -> _Blob:
            return _Blob()

    class _Client:
        def bucket(self, _: str) -> _Bucket:
            return _Bucket()

    monkeypatch.setattr(permissions.storage, "Client", lambda **_: _Client())
    assert _checker()._probe_gcs_write().outcome is ProbeOutcome.RETRY
