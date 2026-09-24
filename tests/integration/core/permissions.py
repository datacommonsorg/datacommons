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

import contextlib
import logging
import shlex
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass

from google.cloud import spanner, storage

from tests.integration.core.target import DCPTarget

logger = logging.getLogger(__name__)


@dataclass
class PermissionCheckResult:
    passed: bool
    name: str
    details: str
    fix_command: str | None = None


def _poll_until_success(
    check_fn: Callable[[], bool],
    timeout_sec: float = 30.0,
    interval_sec: float = 2.0,
) -> bool:
    """Polls check_fn periodically until it returns True or timeout expires."""
    deadline = time.time() + timeout_sec
    attempt = 1
    while time.time() < deadline:
        time.sleep(interval_sec)
        try:
            if check_fn():
                logger.debug("Verification passed on attempt %d", attempt)
                return True
        except Exception:
            logger.debug("Verification attempt %d raised exception", attempt, exc_info=True)
        attempt += 1
    return False


class PreflightPermissionChecker:
    """Verifies all required GCP and IAM permissions before integration tests execute."""

    def __init__(self, target: DCPTarget):
        self.target = target
        self.current_user = self._get_current_user()
        self.member_spec = self._compute_member_spec()

    def _get_current_user(self) -> str:
        try:
            return (
                subprocess.check_output(
                    ["gcloud", "config", "get-value", "account"],
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
        except Exception:
            return ""

    def _compute_member_spec(self) -> str:
        if not self.current_user:
            return "current identity"
        member_type = (
            "serviceAccount" if "gserviceaccount.com" in self.current_user else "user"
        )
        return f"{member_type}:{self.current_user}"

    def prompt_and_fix(self, result: PermissionCheckResult) -> bool:
        """Interactively prompts the user to apply the fix command if running in a terminal."""
        if not result.fix_command:
            return False

        print(f"\n⚠️  Permission Issue Detected: {result.name}")
        print(f"   {result.details}")
        print(f"   Recommended fix command:\n     {result.fix_command}")

        try:
            choice = (
                input("\nWould you like to automatically apply this fix now? [Y/n]: ")
                .strip()
                .lower()
            )
            if choice not in ("", "y", "yes"):
                return False

            print(f"   Executing: {result.fix_command}...")
            res = subprocess.run(
                shlex.split(result.fix_command),
                text=True,
                check=False,
            )
            if res.returncode != 0:
                print("   ❌ Failed to grant permission automatically.")
                return False

            print("   ✔ Permission successfully granted!")
            print("   ⏳ Waiting for GCP IAM policy propagation...")

            # Re-verify based on permission name
            if result.name == "Service Account Impersonation":
                return _poll_until_success(self._can_impersonate_workflow_sa)
            if result.name == "Spanner Access":
                return _poll_until_success(self._can_access_spanner)
            if result.name == "GCS Bucket Access":
                return _poll_until_success(self._can_write_gcs_bucket)

            return True
        except Exception:
            return False

    def verify_all(self) -> list[PermissionCheckResult]:
        """Runs all permission checks and interactively offers fixes for any failures."""
        if self.target.instance_name == "emulated":
            print("\n[Preflight] Running on local emulator (Skipping GCP IAM checks).")
            return [
                PermissionCheckResult(
                    passed=True,
                    name="Emulated Permissions",
                    details="Skipped on local emulator",
                )
            ]

        print(
            f"\n[Preflight] Running permission checks for user: '{self.current_user}'..."
        )

        checks = [
            self.check_service_account_impersonation,
            self.check_gcs_bucket_access,
            self.check_spanner_access,
        ]

        results = []
        for check in checks:
            res = check()
            if not res.passed and sys.stdin.isatty() and self.prompt_and_fix(res):
                res.passed = True
            results.append(res)

        return results

    # =========================================================================
    # 1. Service Account Impersonation
    # =========================================================================
    def _can_impersonate_workflow_sa(self) -> bool:
        """Helper that attempts to print an access token impersonating the workflow SA."""
        sa_email = self.target.workflow_sa_email
        if not sa_email:
            return False
        res = subprocess.run(
            [
                "gcloud",
                "auth",
                "print-access-token",
                f"--impersonate-service-account={sa_email}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return res.returncode == 0 and bool(res.stdout.strip())

    def check_service_account_impersonation(self) -> PermissionCheckResult:
        """Verifies TokenCreator role on the Workflow Service Account."""
        sa_email = self.target.workflow_sa_email
        if not sa_email:
            return PermissionCheckResult(
                passed=False,
                name="Service Account Impersonation",
                details="Workflow Service Account email could not be resolved from Terraform workspace (missing output 'ingestion_workflow_service_account_email').",
            )

        if self._can_impersonate_workflow_sa():
            print(f"  ✔ TokenCreator IAM permission verified on {sa_email}")
            return PermissionCheckResult(
                passed=True,
                name="Service Account Impersonation",
                details=f"Impersonation verified for {sa_email}",
            )

        # Attempt automatic grant if user has admin privileges
        if self.current_user:
            grant_cmd = [
                "gcloud",
                "iam",
                "service-accounts",
                "add-iam-policy-binding",
                sa_email,
                f"--member={self.member_spec}",
                "--role=roles/iam.serviceAccountTokenCreator",
                f"--project={self.target.project_id}",
                "--quiet",
            ]
            res = subprocess.run(grant_cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0:
                print(f"  ✔ Automatically granted TokenCreator IAM role on {sa_email}")
                print("  ⏳ Waiting for GCP IAM policy propagation...")
                if _poll_until_success(self._can_impersonate_workflow_sa):
                    print("  ✔ IAM propagation confirmed.")
                    return PermissionCheckResult(
                        passed=True,
                        name="Service Account Impersonation",
                        details=f"Automatically granted TokenCreator role to {self.member_spec}",
                    )

        fix_cmd = (
            f"gcloud iam service-accounts add-iam-policy-binding '{sa_email}' "
            f"--member='{self.member_spec}' "
            f"--role='roles/iam.serviceAccountTokenCreator' "
            f"--project='{self.target.project_id}'"
        )
        return PermissionCheckResult(
            passed=False,
            name="Service Account Impersonation",
            details=f"Identity '{self.member_spec}' lacks TokenCreator role on '{sa_email}'",
            fix_command=fix_cmd,
        )

    # =========================================================================
    # 2. GCS Bucket Access
    # =========================================================================
    def _can_write_gcs_bucket(self) -> bool:
        """Helper that verifies read/write capability to the artifacts bucket."""
        bucket_raw = (
            self.target.gcs_bucket
            or f"dcp-{self.target.instance_name}-{self.target.project_id}"
        )
        bucket_name = bucket_raw.replace("gs://", "").strip().split("/")[0]
        if not bucket_name:
            return False

        client = storage.Client(project=self.target.project_id)
        bucket = client.bucket(bucket_name)
        probe_blob = bucket.blob(".test_permission_probe")
        try:
            probe_blob.upload_from_string("probe", timeout=10)
            return True
        finally:
            with contextlib.suppress(Exception):
                probe_blob.delete(timeout=10)

    def check_gcs_bucket_access(self) -> PermissionCheckResult:
        """Verifies read/write access to the testbed GCS bucket."""
        bucket_raw = (
            self.target.gcs_bucket
            or f"dcp-{self.target.instance_name}-{self.target.project_id}"
        )
        bucket_name = bucket_raw.replace("gs://", "").strip().split("/")[0]

        if not bucket_name:
            return PermissionCheckResult(
                passed=False,
                name="GCS Bucket Access",
                details="Artifacts GCS bucket could not be resolved from Terraform workspace (missing output 'storage_artifacts_bucket_name').",
            )

        try:
            if self._can_write_gcs_bucket():
                print(f"  ✔ GCS bucket write access verified on gs://{bucket_name}")
                return PermissionCheckResult(
                    passed=True,
                    name="GCS Bucket Access",
                    details=f"Write access verified for gs://{bucket_name}",
                )
        except Exception as e:
            logger.debug("GCS check failed: %s", e)

        fix_cmd = (
            f"gcloud storage buckets add-iam-policy-binding 'gs://{bucket_name}' "
            f"--member='{self.member_spec}' "
            f"--role='roles/storage.objectAdmin' "
            f"--project='{self.target.project_id}'"
        )
        return PermissionCheckResult(
            passed=False,
            name="GCS Bucket Access",
            details=f"Cannot write to GCS bucket 'gs://{bucket_name}'",
            fix_command=fix_cmd,
        )

    # =========================================================================
    # 3. Spanner Access
    # =========================================================================
    def _can_access_spanner(self) -> bool:
        """Helper that verifies query and databaseAdmin capability on Spanner."""
        if not self.target.spanner_instance or not self.target.spanner_database:
            return False
        client = spanner.Client(project=self.target.project_id)
        inst = client.instance(self.target.spanner_instance)
        db = inst.database(self.target.spanner_database)
        with db.snapshot() as snapshot:
            results = snapshot.execute_sql("SELECT 1")
            list(results)
        client.database_admin_api.get_database_ddl(database=db.name)
        return True

    def check_spanner_access(self) -> PermissionCheckResult:
        """Verifies Spanner database access and schema administration permissions."""
        if not self.target.spanner_instance or not self.target.spanner_database:
            return PermissionCheckResult(
                passed=False,
                name="Spanner Access",
                details="Spanner instance or database could not be resolved from Terraform workspace (missing output 'spanner_instance_id' or 'spanner_database_id').",
            )

        try:
            if self._can_access_spanner():
                print(
                    f"  ✔ Spanner databaseAdmin & databaseUser access verified on {self.target.spanner_instance}/{self.target.spanner_database}"
                )
                return PermissionCheckResult(
                    passed=True,
                    name="Spanner Access",
                    details=f"Verified on {self.target.spanner_instance}",
                )
        except Exception as e:
            logger.debug("Initial Spanner check failed: %s", e)

        # Attempt auto-grant if user has IAM admin privileges
        if self.current_user:
            for role in ("roles/spanner.databaseAdmin", "roles/spanner.databaseUser"):
                grant_cmd = [
                    "gcloud",
                    "spanner",
                    "instances",
                    "add-iam-policy-binding",
                    self.target.spanner_instance,
                    f"--member={self.member_spec}",
                    f"--role={role}",
                    f"--project={self.target.project_id}",
                    "--quiet",
                ]
                res = subprocess.run(grant_cmd, capture_output=True, text=True, check=False)
                if res.returncode == 0:
                    print(f"  ✔ Automatically granted {role} on {self.target.spanner_instance}")

            print("  ⏳ Waiting for GCP IAM policy propagation...")
            if _poll_until_success(self._can_access_spanner):
                print("  ✔ Spanner IAM propagation confirmed.")
                return PermissionCheckResult(
                    passed=True,
                    name="Spanner Access",
                    details=f"Verified on {self.target.spanner_instance}",
                )

        fix_cmd = (
            f"gcloud spanner instances add-iam-policy-binding '{self.target.spanner_instance}' "
            f"--member='{self.member_spec}' "
            f"--role='roles/spanner.databaseAdmin' "
            f"--project='{self.target.project_id}' && "
            f"gcloud spanner instances add-iam-policy-binding '{self.target.spanner_instance}' "
            f"--member='{self.member_spec}' "
            f"--role='roles/spanner.databaseUser' "
            f"--project='{self.target.project_id}'"
        )
        return PermissionCheckResult(
            passed=False,
            name="Spanner Access",
            details=f"Cannot administer or query Spanner instance '{self.target.spanner_instance}'",
            fix_command=fix_cmd,
        )
