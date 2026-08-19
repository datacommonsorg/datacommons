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
                    result.fix_command, shell=True, text=True, check=False
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
        if not sa_email or not self.current_user:
            return PermissionCheckResult(
                passed=True,
                name="Service Account Impersonation",
                details="Skipped (SA or user account not resolved)",
            )

        cmd = [
            "gcloud",
            "iam",
            "service-accounts",
            "get-iam-policy",
            sa_email,
            f"--project={self.target.project_id}",
            f"--filter=bindings.role=roles/iam.serviceAccountTokenCreator AND bindings.members=user:{self.current_user}",
            "--format=value(bindings.role)",
        ]

        try:
            out = (
                subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
            )
            if "roles/iam.serviceAccountTokenCreator" in out:
                print(f"  ✔ TokenCreator IAM role verified on {sa_email}")
                return PermissionCheckResult(
                    passed=True,
                    name="Service Account Impersonation",
                    details=f"Verified for {self.current_user} on {sa_email}",
                )
        except Exception:
            pass

        # Try to automatically grant if user has admin rights
        grant_cmd = [
            "gcloud",
            "iam",
            "service-accounts",
            "add-iam-policy-binding",
            sa_email,
            f"--member=user:{self.current_user}",
            "--role=roles/iam.serviceAccountTokenCreator",
            f"--project={self.target.project_id}",
            "--quiet",
        ]
        try:
            res = subprocess.run(grant_cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0:
                print(f"  ✔ Automatically granted TokenCreator IAM role on {sa_email}")
                return PermissionCheckResult(
                    passed=True,
                    name="Service Account Impersonation",
                    details="Automatically granted TokenCreator role",
                )
        except Exception:
            pass

        fix_cmd = (
            f"gcloud iam service-accounts add-iam-policy-binding '{sa_email}' "
            f"--member='user:{self.current_user}' "
            f"--role='roles/iam.serviceAccountTokenCreator' "
            f"--project='{self.target.project_id}'"
        )
        return PermissionCheckResult(
            passed=False,
            name="Service Account Impersonation",
            details=f"User '{self.current_user}' lacks TokenCreator role on '{sa_email}'",
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
                passed=True, name="GCS Bucket Access", details="Skipped"
            )

        try:
            client = storage.Client(project=self.target.project_id)
            bucket = client.bucket(bucket_name)

            # Write and delete a probe file
            probe_blob = bucket.blob(".test_permission_probe")
            probe_blob.upload_from_string("probe", timeout=10)
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
                f"--member='user:{self.current_user}' "
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
                passed=True, name="Spanner Access", details="Skipped"
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
                f"--member='user:{self.current_user}' "
                f"--role='roles/spanner.databaseUser' "
                f"--project='{self.target.project_id}'"
            )
            return PermissionCheckResult(
                passed=False,
                name="Spanner Access",
                details=f"Cannot query Spanner: {e}",
                fix_command=fix_cmd,
            )
