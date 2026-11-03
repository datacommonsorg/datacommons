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

"""Preflight permission checks that run once before any integration test.

Preflight verifies that every identity the run depends on right after deploy
has the access it needs. Grants created by the same `terraform apply` can take
several minutes to propagate, so checks that fail with a retryable error are
polled until they pass or a shared deadline expires.

Coverage rule:
  * Caller: valid Application Default Credentials (ADC), plus access to the
    resources used during setup and ingestion (the artifacts bucket, Spanner,
    and impersonating each stack service account the harness acts as). Serving
    endpoints are called much later and are not checked here.
  * Stack service accounts: each Terraform-created SA whose grants are used
    within the first minutes after deploy. One probe per SA stands in for that
    SA's other grants from the same apply.
  * Not checked: SAs first used later (serving, preprocessing, Dataflow, helper,
    postprocessing). By then, preflight plus the early ingestion stages have
    absorbed IAM propagation.
  * Preflight must never require more access than the tests themselves need.

All probes use ADC, the same identity the CLI uses.
"""

import contextlib
import json
import logging
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

import google.auth
import requests
from google.api_core import exceptions as api_exceptions
from google.auth import exceptions as auth_exceptions
from google.auth import impersonated_credentials
from google.auth.credentials import Credentials
from google.auth.transport.requests import AuthorizedSession, Request
from google.cloud import spanner, storage

from tests.integration.core.target import DCPTarget

if TYPE_CHECKING:
    from google.cloud.spanner_v1.database import Database

logger = logging.getLogger(__name__)

CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
WORKFLOW_EXECUTIONS_API = "https://workflowexecutions.googleapis.com/v1"
ADC_LOGIN_HINT = "Run 'gcloud auth application-default login'."

# Google documents IAM propagation as typically ~2 minutes and occasionally 7+.
PROPAGATION_TIMEOUT_SEC = 420.0
POLL_INTERVAL_SEC = 15.0
REQUEST_TIMEOUT_SEC = 10
DETAIL_MAX_CHARS = 200

# Statuses where waiting may help: permission still propagating, rate limiting,
# or a transient server-side error.
_RETRYABLE_HTTP_STATUSES = frozenset({403, 429, 500, 502, 503, 504})


class ProbeOutcome(Enum):
    OK = "ok"
    RETRY = "retry"
    FAIL = "fail"


@dataclass
class ProbeResult:
    outcome: ProbeOutcome
    detail: str = ""
    # True only for permission denials, the one RETRY cause a fix can address.
    denied: bool = False


@dataclass
class PermissionCheck:
    """A single 'identity can do X' assertion, proven by a read-only probe."""

    name: str
    probe: Callable[[], ProbeResult]
    # Only caller checks carry a fix. A missing grant on a Terraform-created
    # service account is a Terraform bug and must never be patched here.
    fix_command: str | None = None
    # Role that should grant this access, shown if the check never passes.
    required_role: str | None = None


@dataclass
class PermissionCheckResult:
    passed: bool
    name: str
    details: str
    fix_command: str | None = None


@dataclass(frozen=True)
class StackServiceAccount:
    """A Terraform-created service account the run uses right after deploy."""

    label: str
    email: str
    email_output: str
    capability: str
    role: str
    # Called with the SA's impersonated credentials, so it always runs as the SA.
    probe: Callable[[Credentials], ProbeResult]


def _truncate(text: str) -> str:
    return text[:DETAIL_MAX_CHARS]


def _refresh_error_status(error: auth_exceptions.RefreshError) -> int | None:
    """Extracts the HTTP status from a RefreshError, if it carries one.

    google-auth raises RefreshError(message, response_body) without a status
    attribute. IAM Credentials bodies look like {"error": {"code": 403, ...}},
    while OAuth2 token bodies look like {"error": "invalid_grant", ...}.
    """
    for arg in error.args[1:]:
        body = arg
        if isinstance(arg, (str, bytes)):
            try:
                body = json.loads(arg)
            except ValueError:
                continue
        err = body.get("error") if isinstance(body, dict) else None
        code = err.get("code") if isinstance(err, dict) else None
        if isinstance(code, int):
            return code
    if "PERMISSION_DENIED" in str(error):
        return 403
    return None


def classify_http_response(response: requests.Response) -> ProbeResult:
    """Maps an HTTP probe response to a probe outcome."""
    if response.status_code == 200:
        return ProbeResult(ProbeOutcome.OK)
    detail = f"HTTP {response.status_code}: {_truncate(response.text)}"
    if response.status_code in _RETRYABLE_HTTP_STATUSES:
        return ProbeResult(
            ProbeOutcome.RETRY,
            detail,
            denied=response.status_code == 403,
        )
    return ProbeResult(ProbeOutcome.FAIL, detail)


def classify_exception(error: Exception) -> ProbeResult:
    """Maps an exception raised by a probe to a probe outcome."""
    detail = f"{type(error).__name__}: {_truncate(str(error))}"
    if isinstance(error, auth_exceptions.RefreshError):
        status = _refresh_error_status(error)
        # google-auth marks transient token-endpoint failures retryable, and
        # metadata-server timeouts surface as a RefreshError caused by a
        # TransportError.
        retryable = (
            error.retryable
            or isinstance(error.__cause__, auth_exceptions.TransportError)
            or status in _RETRYABLE_HTTP_STATUSES
        )
        return ProbeResult(
            ProbeOutcome.RETRY if retryable else ProbeOutcome.FAIL,
            detail,
            denied=status == 403,
        )
    if isinstance(error, api_exceptions.Forbidden):
        return ProbeResult(ProbeOutcome.RETRY, detail, denied=True)
    # TooManyRequests covers ResourceExhausted, and ServerError covers every
    # 5xx/DeadlineExceeded.
    retryable_types = (
        api_exceptions.TooManyRequests,
        api_exceptions.ServerError,
        auth_exceptions.TransportError,
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
    )
    if isinstance(error, retryable_types):
        return ProbeResult(ProbeOutcome.RETRY, detail)
    return ProbeResult(ProbeOutcome.FAIL, detail)


class PreflightPermissionChecker:
    """Verifies caller and stack service account access before tests execute."""

    def __init__(
        self,
        target: DCPTarget,
        timeout_sec: float = PROPAGATION_TIMEOUT_SEC,
        poll_interval_sec: float = POLL_INTERVAL_SEC,
        interactive: bool | None = None,
    ) -> None:
        self.target = target
        self.timeout_sec = timeout_sec
        self.poll_interval_sec = poll_interval_sec
        self.interactive = sys.stdin.isatty() if interactive is None else interactive
        self.caller_email = ""
        self._credentials: Credentials | None = None
        self._sa_credentials: dict[str, Credentials] = {}
        self._storage_client: storage.Client | None = None
        self._spanner_client: spanner.Client | None = None
        self._spanner_db: Database | None = None

    # =========================================================================
    # Phase orchestration
    # =========================================================================
    def verify_all(self) -> list[PermissionCheckResult]:
        """Runs every check against one shared propagation deadline."""
        if self.target.instance_name == "emulated":
            print("\n[Preflight] Running on local emulator (Skipping GCP IAM checks).")
            return [
                PermissionCheckResult(
                    passed=True,
                    name="Emulated Permissions",
                    details="Skipped on local emulator",
                ),
            ]

        try:
            self._credentials, _ = google.auth.default(scopes=[CLOUD_PLATFORM_SCOPE])
        except auth_exceptions.DefaultCredentialsError as e:
            return [
                PermissionCheckResult(
                    passed=False,
                    name="Caller: Application Default Credentials",
                    details=f"{e}. {ADC_LOGIN_HINT}",
                ),
            ]

        # IAM propagation is measured from the apply, not per check, so every
        # check shares one deadline.
        deadline = time.monotonic() + self.timeout_sec
        print("\n[Preflight] Caller")
        adc_result = self._run_check(
            PermissionCheck(
                name="Caller: can refresh Application Default Credentials",
                probe=self._probe_adc_refresh,
            ),
            deadline,
        )
        if not adc_result.passed:
            return [adc_result]
        self.caller_email = self._resolve_caller_email()
        print(
            f"  Identity: {self.caller_email or 'unknown (no fixes will be offered)'}"
        )

        results = [
            adc_result,
            self._run_check(self._gcs_check(), deadline),
            self._run_check(self._spanner_check(), deadline),
        ]
        stack_sas = self._stack_service_accounts()
        can_impersonate: dict[str, bool] = {}
        for sa in stack_sas:
            res = self._run_check(self._impersonation_check(sa), deadline)
            can_impersonate[sa.label] = res.passed
            results.append(res)

        for sa in stack_sas:
            print(f"[Preflight] {sa.label}: {sa.email or 'unresolved'}")
            check = self._capability_check(sa)
            if can_impersonate[sa.label]:
                results.append(self._run_check(check, deadline))
            else:
                detail = f"skipped because the caller cannot impersonate {sa.label}"
                results.append(self._fail(check, detail))

        return results

    def _run_check(
        self, check: PermissionCheck, deadline: float
    ) -> PermissionCheckResult:
        """Probes once, offers a fix if allowed, then polls RETRY until deadline."""
        start = time.monotonic()
        result = check.probe()

        if result.denied and check.fix_command and self.interactive:
            if not self._offer_fix(check, result):
                return self._fail(check, result.detail)
            # The fix is a brand-new grant, so give it a full propagation window.
            deadline = max(deadline, time.monotonic() + self.timeout_sec)
            result = check.probe()

        announced = False
        while result.outcome is ProbeOutcome.RETRY:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            if not announced:
                print(
                    f"  ⏳ {check.name}: waiting up to {int(remaining)}s for IAM "
                    f"propagation ({result.detail})",
                )
                announced = True
            time.sleep(min(self.poll_interval_sec, remaining))
            result = check.probe()

        if result.outcome is ProbeOutcome.OK:
            elapsed = int(time.monotonic() - start)
            print(f"  ✔ {check.name} (ready after {elapsed}s)")
            return PermissionCheckResult(
                passed=True,
                name=check.name,
                details=f"Verified after {elapsed}s",
            )

        detail = result.detail
        if result.outcome is ProbeOutcome.RETRY:
            detail = f"still failing when the propagation budget ran out: {detail}"
            if check.required_role:
                detail += (
                    f". Expected grant: {check.required_role}. Either it is "
                    "missing, or IAM propagation is unusually slow"
                )
        return self._fail(check, detail)

    def _fail(self, check: PermissionCheck, detail: str) -> PermissionCheckResult:
        print(f"  ✘ {check.name}: {detail}")
        return PermissionCheckResult(
            passed=False,
            name=check.name,
            details=detail,
            fix_command=check.fix_command,
        )

    def _offer_fix(self, check: PermissionCheck, result: ProbeResult) -> bool:
        """Prompts to run the fix. Returns True only if it was applied successfully."""
        print(f"\n⚠️  Permission issue: {check.name}")
        print(f"   {result.detail}")
        print(f"   Recommended fix command:\n     {check.fix_command}")
        try:
            choice = input("\nApply this fix now? [Y/n]: ").strip().lower()
        except EOFError:
            return False
        if choice not in ("", "y", "yes"):
            return False
        res = subprocess.run(check.fix_command, shell=True, text=True, check=False)
        if res.returncode != 0:
            print("   ❌ Failed to apply the fix.")
            return False
        print("   ✔ Fix applied. Waiting for IAM propagation...")
        return True

    # =========================================================================
    # Identity helpers
    # =========================================================================
    def _probe_adc_refresh(self) -> ProbeResult:
        """Refreshes ADC once so broken credentials fail clearly and early."""
        try:
            self._credentials.refresh(Request())
        except Exception as e:  # noqa: BLE001 - classified into RETRY/FAIL
            result = classify_exception(e)
            if result.outcome is ProbeOutcome.FAIL:
                result.detail = f"{result.detail}. {ADC_LOGIN_HINT}"
            return result
        return ProbeResult(ProbeOutcome.OK)

    def _resolve_caller_email(self) -> str:
        """Returns the (already refreshed) ADC identity's email, or "" if unknown."""
        creds = self._credentials
        # Service account and Compute/Cloud Run credentials expose the email;
        # Compute reports "default" until its first refresh.
        email = getattr(creds, "service_account_email", "")
        if email and email != "default":
            return email
        # User credentials: gcloud's ADC login includes the userinfo.email scope.
        try:
            resp = requests.post(
                TOKENINFO_URL,
                data={"access_token": creds.token},
                timeout=REQUEST_TIMEOUT_SEC,
            )
            if resp.ok:
                return resp.json().get("email", "")
        except requests.RequestException:
            logger.debug("Could not resolve ADC caller email", exc_info=True)
        return ""

    def _member_spec(self) -> str | None:
        if not self.caller_email:
            return None
        member_type = (
            "serviceAccount"
            if self.caller_email.endswith("gserviceaccount.com")
            else "user"
        )
        return f"{member_type}:{self.caller_email}"

    def _impersonated(self, sa_email: str) -> Credentials:
        """Returns cached impersonated credentials; google-auth refreshes them."""
        if sa_email not in self._sa_credentials:
            self._sa_credentials[sa_email] = impersonated_credentials.Credentials(
                source_credentials=self._credentials,
                target_principal=sa_email,
                target_scopes=[CLOUD_PLATFORM_SCOPE],
            )
        return self._sa_credentials[sa_email]

    # =========================================================================
    # Caller checks
    # =========================================================================
    def _bucket_name(self) -> str:
        bucket_raw = (
            self.target.gcs_bucket
            or f"dcp-{self.target.instance_name}-{self.target.project_id}"
        )
        return bucket_raw.replace("gs://", "").strip().split("/")[0]

    def _gcs_check(self) -> PermissionCheck:
        bucket_name = self._bucket_name()
        member = self._member_spec()
        fix = (
            f"gcloud storage buckets add-iam-policy-binding 'gs://{bucket_name}' "
            f"--member='{member}' --role='roles/storage.objectAdmin' "
            f"--project='{self.target.project_id}'"
            if member
            else None
        )
        return PermissionCheck(
            name=f"Caller: can write to gs://{bucket_name}",
            probe=self._probe_gcs_write,
            fix_command=fix,
            required_role="roles/storage.objectAdmin",
        )

    def _probe_gcs_write(self) -> ProbeResult:
        try:
            if self._storage_client is None:
                self._storage_client = storage.Client(
                    project=self.target.project_id,
                    credentials=self._credentials,
                )
            bucket = self._storage_client.bucket(self._bucket_name())
            blob = bucket.blob(".test_permission_probe")
            blob.upload_from_string("probe", timeout=REQUEST_TIMEOUT_SEC)
        except Exception as e:  # noqa: BLE001 - classified into RETRY/FAIL
            return classify_exception(e)
        # Cleanup is best effort and must not change the write verdict.
        with contextlib.suppress(Exception):
            blob.delete(timeout=REQUEST_TIMEOUT_SEC)
        return ProbeResult(ProbeOutcome.OK)

    def _spanner_check(self) -> PermissionCheck:
        instance = self.target.spanner_instance
        member = self._member_spec()
        fix = (
            f"gcloud spanner instances add-iam-policy-binding '{instance}' "
            f"--member='{member}' --role='roles/spanner.databaseAdmin' "
            f"--project='{self.target.project_id}' && "
            f"gcloud spanner instances add-iam-policy-binding '{instance}' "
            f"--member='{member}' --role='roles/spanner.databaseUser' "
            f"--project='{self.target.project_id}'"
            if member and instance
            else None
        )
        return PermissionCheck(
            name=(
                "Caller: can query and administer Spanner "
                f"{instance}/{self.target.spanner_database}"
            ),
            probe=self._probe_spanner,
            fix_command=fix,
            required_role="roles/spanner.databaseAdmin and roles/spanner.databaseUser",
        )

    def _probe_spanner(self) -> ProbeResult:
        if not self.target.spanner_instance or not self.target.spanner_database:
            return ProbeResult(
                ProbeOutcome.FAIL,
                "Missing Terraform output 'spanner_instance_id' or 'spanner_database_id'",
            )
        try:
            if self._spanner_db is None:
                self._spanner_client = spanner.Client(
                    project=self.target.project_id,
                    credentials=self._credentials,
                )
                self._spanner_db = self._spanner_client.instance(
                    self.target.spanner_instance,
                ).database(self.target.spanner_database)
            db = self._spanner_db
            # Turn off per-call client retries (which default to up to an hour)
            # so the run loop owns retrying and each probe is normally bounded
            # by the request timeout.
            with db.snapshot() as snapshot:
                list(
                    snapshot.execute_sql(
                        "SELECT 1",
                        retry=None,
                        timeout=REQUEST_TIMEOUT_SEC,
                    ),
                )
            self._spanner_client.database_admin_api.get_database_ddl(
                database=db.name,
                retry=None,
                timeout=REQUEST_TIMEOUT_SEC,
            )
        except Exception as e:  # noqa: BLE001 - classified into RETRY/FAIL
            return classify_exception(e)
        return ProbeResult(ProbeOutcome.OK)

    def _impersonation_check(self, sa: StackServiceAccount) -> PermissionCheck:
        member = self._member_spec()
        fix = (
            f"gcloud iam service-accounts add-iam-policy-binding '{sa.email}' "
            f"--member='{member}' --role='roles/iam.serviceAccountTokenCreator' "
            f"--project='{self.target.project_id}'"
            if member and sa.email
            else None
        )
        return PermissionCheck(
            name=f"Caller: can impersonate {sa.label}",
            probe=lambda: self._probe_impersonation(sa),
            fix_command=fix,
            required_role="roles/iam.serviceAccountTokenCreator",
        )

    def _probe_impersonation(self, sa: StackServiceAccount) -> ProbeResult:
        if not sa.email:
            return ProbeResult(
                ProbeOutcome.FAIL,
                f"Missing Terraform output '{sa.email_output}'",
            )
        try:
            self._impersonated(sa.email).refresh(Request())
        except Exception as e:  # noqa: BLE001 - classified into RETRY/FAIL
            return classify_exception(e)
        return ProbeResult(ProbeOutcome.OK)

    # =========================================================================
    # Stack service accounts
    # =========================================================================
    def _stack_service_accounts(self) -> list[StackServiceAccount]:
        """Stack SAs the run uses right after deploy (see coverage rule)."""
        return [
            StackServiceAccount(
                label="Workflow SA",
                email=self.target.workflow_sa_email,
                email_output="ingestion_workflow_service_account_email",
                capability="invoke workflows",
                role="roles/workflows.invoker",
                probe=self._probe_workflow_invoker,
            ),
        ]

    def _capability_check(self, sa: StackServiceAccount) -> PermissionCheck:
        return PermissionCheck(
            name=f"{sa.label}: can {sa.capability}",
            probe=lambda: sa.probe(self._impersonated(sa.email)),
            required_role=sa.role,
        )

    def _probe_workflow_invoker(self, sa_credentials: Credentials) -> ProbeResult:
        """Lists executions as the workflow SA.

        executions.list is granted by the same roles/workflows.invoker binding
        as the executions.create call that 'datacommons admin ingest start' makes.
        """
        if not self.target.workflow_id:
            return ProbeResult(
                ProbeOutcome.FAIL,
                "Missing Terraform output 'ingestion_workflow_id'",
            )
        url = f"{WORKFLOW_EXECUTIONS_API}/{self.target.workflow_id}/executions"
        try:
            response = AuthorizedSession(sa_credentials).get(
                url,
                params={"pageSize": 1},
                timeout=REQUEST_TIMEOUT_SEC,
            )
        except Exception as e:  # noqa: BLE001 - classified into RETRY/FAIL
            return classify_exception(e)
        return classify_http_response(response)
