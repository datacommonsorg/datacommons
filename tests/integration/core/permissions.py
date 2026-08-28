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
import shlex
import subprocess
import sys
from dataclasses import dataclass

from google.cloud import spanner, storage

from tests.integration.core.target import DCPTarget


@dataclass
class PermissionCheckResult:
    passed: bool
    name: str
    details: str
    fix_command: str | None = None


class PreflightPermissionChecker:
    """Verifies all required GCP and IAM permissions before integration tests execute."""

    def __init__(self, target: DCPTarget):
        self.target = target
        self.current_user = self._get_current_user()

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

    def prompt_and_fix(self, result: PermissionCheckResult) -> bool:
        """Interactively prompts the user to apply the fix command if running in terminal."""
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
            if choice in ("", "y", "yes"):
                print(f"   Executing: {result.fix_command}...")
                res = subprocess.run(
                    shlex.split(result.fix_command),
                    text=True,
                    check=False,
                )
                if res.returncode == 0:
                    print("   ✔ Permission successfully granted!")
                    return True
                print("   ❌ Failed to grant permission automatically.")
        except Exception:
            pass
        return False

    def verify_all(self) -> list[PermissionCheckResult]:
        """Runs all permission checks and interactively offers fixes for any failures."""
        results = []
        print(
            f"\n[Preflight] Running permission checks for user: '{self.current_user}'..."
        )

        # 1. Check Service Account Impersonation (TokenCreator)
        sa_res = self.check_service_account_impersonation()
        if not sa_res.passed and sys.stdin.isatty() and self.prompt_and_fix(sa_res):
            sa_res.passed = True
        results.append(sa_res)

        # 2. Check GCS Bucket Access
        gcs_res = self.check_gcs_bucket_access()
        if not gcs_res.passed and sys.stdin.isatty() and self.prompt_and_fix(gcs_res):
            gcs_res.passed = True
        results.append(gcs_res)

        # 3. Check Spanner Database Access
        spanner_res = self.check_spanner_access()
        if (
            not spanner_res.passed
            and sys.stdin.isatty()
            and self.prompt_and_fix(spanner_res)
        ):
            spanner_res.passed = True
        results.append(spanner_res)

        return results

    def check_service_account_impersonation(self) -> PermissionCheckResult:
        """Verifies TokenCreator role on the Workflow Service Account."""
        sa_email = self.target.workflow_sa_email
        if not sa_email:
            return PermissionCheckResult(
                passed=False,
                name="Service Account Impersonation",
                details="Workflow Service Account email could not be resolved from Terraform workspace (missing output 'ingestion_workflow_service_account_email').",
            )

        # 1. Directly test token creation / impersonation capability
        # This handles project-level roles (roles/owner, roles/iam.serviceAccountTokenCreator)
        # as well as resource-level service account IAM bindings accurately.
        try:
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
            if res.returncode == 0 and res.stdout.strip():
                print(f"  ✔ TokenCreator IAM permission verified on {sa_email}")
                return PermissionCheckResult(
                    passed=True,
                    name="Service Account Impersonation",
                    details=f"Impersonation verified for {sa_email}",
                )
        except Exception:
            pass

        member_type = (
            "serviceAccount"
            if (self.current_user and "gserviceaccount.com" in self.current_user)
            else "user"
        )
        member_spec = (
            f"{member_type}:{self.current_user}"
            if self.current_user
            else "current identity"
        )

        # Try to automatically grant if user/SA has admin rights
        if self.current_user:
            grant_cmd = [
                "gcloud",
                "iam",
                "service-accounts",
                "add-iam-policy-binding",
                sa_email,
                f"--member={member_spec}",
                "--role=roles/iam.serviceAccountTokenCreator",
                f"--project={self.target.project_id}",
                "--quiet",
            ]
            try:
                res = subprocess.run(
                    grant_cmd, capture_output=True, text=True, check=False
                )
                if res.returncode == 0:
                    print(
                        f"  ✔ Automatically granted TokenCreator IAM role on {sa_email}"
                    )
                    print("  ⏳ Waiting for GCP IAM policy propagation...")
                    import time

                    # Poll token creation until IAM propagation completes.
                    # Maximum bound: 120 seconds (10 attempts x (2s sleep + 10s timeout)).
                    # In practice, IAM propagation usually succeeds within 4-6 seconds.
                    max_attempts = 10
                    poll_interval_sec = 2.0
                    for attempt in range(1, max_attempts + 1):
                        time.sleep(poll_interval_sec)
                        test_tok = subprocess.run(
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
                        if test_tok.returncode == 0 and test_tok.stdout.strip():
                            print(
                                f"  ✔ IAM propagation confirmed on attempt {attempt}."
                            )
                            return PermissionCheckResult(
                                passed=True,
                                name="Service Account Impersonation",
                                details=f"Automatically granted TokenCreator role to {member_spec}",
                            )
            except Exception:
                pass

        fix_cmd = (
            f"gcloud iam service-accounts add-iam-policy-binding '{sa_email}' "
            f"--member='{member_spec}' "
            f"--role='roles/iam.serviceAccountTokenCreator' "
            f"--project='{self.target.project_id}'"
        )
        return PermissionCheckResult(
            passed=False,
            name="Service Account Impersonation",
            details=f"Identity '{member_spec}' lacks TokenCreator role on '{sa_email}'",
            fix_command=fix_cmd,
        )

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

        member_type = (
            "serviceAccount"
            if (self.current_user and "gserviceaccount.com" in self.current_user)
            else "user"
        )
        member_spec = (
            f"{member_type}:{self.current_user}"
            if self.current_user
            else "current identity"
        )

        try:
            client = storage.Client(project=self.target.project_id)
            bucket = client.bucket(bucket_name)

            # Write and delete a probe file
            probe_blob = bucket.blob(".test_permission_probe")
            try:
                probe_blob.upload_from_string("probe", timeout=10)
            finally:
                with contextlib.suppress(Exception):
                    probe_blob.delete(timeout=10)

            print(f"  ✔ GCS bucket write access verified on gs://{bucket_name}")
            return PermissionCheckResult(
                passed=True,
                name="GCS Bucket Access",
                details=f"Write access verified for gs://{bucket_name}",
            )
        except Exception as e:
            fix_cmd = (
                f"gcloud storage buckets add-iam-policy-binding 'gs://{bucket_name}' "
                f"--member='{member_spec}' "
                f"--role='roles/storage.objectAdmin' "
                f"--project='{self.target.project_id}'"
            )
            return PermissionCheckResult(
                passed=False,
                name="GCS Bucket Access",
                details=f"Cannot write to GCS bucket 'gs://{bucket_name}': {e}",
                fix_command=fix_cmd,
            )

    def check_spanner_access(self) -> PermissionCheckResult:
        """Verifies Spanner database read permissions."""
        if not self.target.spanner_instance or not self.target.spanner_database:
            return PermissionCheckResult(
                passed=False,
                name="Spanner Access",
                details="Spanner instance or database could not be resolved from Terraform workspace (missing output 'spanner_instance_id' or 'spanner_database_id').",
            )

        member_type = (
            "serviceAccount"
            if (self.current_user and "gserviceaccount.com" in self.current_user)
            else "user"
        )
        member_spec = (
            f"{member_type}:{self.current_user}"
            if self.current_user
            else "current identity"
        )

        try:
            client = spanner.Client(project=self.target.project_id)
            inst = client.instance(self.target.spanner_instance)
            db = inst.database(self.target.spanner_database)
            with db.snapshot() as snapshot:
                results = snapshot.execute_sql("SELECT 1")
                list(results)
            print(
                f"  ✔ Spanner read access verified on {self.target.spanner_instance}/{self.target.spanner_database}"
            )
            return PermissionCheckResult(
                passed=True,
                name="Spanner Access",
                details=f"Verified on {self.target.spanner_instance}",
            )
        except Exception as e:
            fix_cmd = (
                f"gcloud spanner instances add-iam-policy-binding '{self.target.spanner_instance}' "
                f"--member='{member_spec}' "
                f"--role='roles/spanner.databaseUser' "
                f"--project='{self.target.project_id}'"
            )
            return PermissionCheckResult(
                passed=False,
                name="Spanner Access",
                details=f"Cannot query Spanner: {e}",
                fix_command=fix_cmd,
            )
