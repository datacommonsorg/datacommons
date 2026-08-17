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

"""Live validation script for MigrationRunner against a real Cloud Spanner instance.

Usage:
    uv run python packages/datacommons-db/scripts/test_live_migration.py \
        [--project-id datcom-website-dev] \
        [--instance-id dcp-testing] \
        [--database-id dev-juliawu-dc-db] \
        [--dry-run]
"""

import argparse
import logging
import sys

import google.auth
import google.auth.exceptions
import google.auth.transport.requests
from datacommons_db.clients import ExecutionStatus, SpannerClient
from datacommons_db.migrations import MigrationRunner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("live_migration_test")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test MigrationRunner against a live Cloud Spanner instance."
    )
    parser.add_argument(
        "--project-id",
        default="datcom-website-dev",
        help="GCP Project ID (default: datcom-website-dev)",
    )
    parser.add_argument(
        "--instance-id",
        default="dcp-testing",
        help="Cloud Spanner Instance ID (default: dcp-testing)",
    )
    parser.add_argument(
        "--database-id",
        default="dev-juliawu-dc-db",
        help="Cloud Spanner Database ID (default: dev-juliawu-dc-db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only inspect current version and pending migrations without applying changes.",
    )
    return parser.parse_args()


def check_gcp_auth() -> None:
    """Verify that Google Cloud Application Default Credentials (ADC) are valid."""
    print("[0/6] Checking Google Cloud Authentication...")
    try:
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        request = google.auth.transport.requests.Request()
        credentials.refresh(request)
        print("  ✓ Google Cloud credentials are valid.")
    except google.auth.exceptions.DefaultCredentialsError:
        print("\n  ✗ Google Cloud Application Default Credentials not found.")
        print("    Please run: gcloud auth application-default login\n")
        sys.exit(1)
    except google.auth.exceptions.RefreshError as e:
        print(f"\n  ✗ Google Cloud credentials expired or invalid: {e}")
        print("    Please run: gcloud auth application-default login\n")
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        print(f"\n  ✗ Authentication check failed: {e}")
        print(
            "    Please ensure you have authenticated via: gcloud auth application-default login\n"
        )
        sys.exit(1)


def run_live_test(
    project_id: str,
    instance_id: str,
    database_id: str,
    *,
    dry_run: bool = False,
) -> None:
    print("\n" + "=" * 80)
    print("MIGRATION RUNNER LIVE INSTANCE VALIDATION")
    print("=" * 80)
    print(f"Target Project:  {project_id}")
    print(f"Target Instance: {instance_id}")
    print(f"Target Database: {database_id}")
    print(f"Dry Run Mode:    {dry_run}")
    print("=" * 80 + "\n")

    # 0. Check Google Cloud Authentication
    check_gcp_auth()

    # 1. Initialize SpannerClient
    print("\n[1/6] Initializing SpannerClient...")
    try:
        client = SpannerClient(
            project_id=project_id,
            instance_id=instance_id,
            database_id=database_id,
        )
        print("  ✓ SpannerClient initialized successfully.")
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ Failed to initialize SpannerClient: {e}")
        sys.exit(1)

    # 2. Initialize MigrationRunner & Test Discovery
    print("\n[2/6] Initializing MigrationRunner & Discovering Migrations...")
    try:
        runner = MigrationRunner(spanner_client=client)
        print(f"  ✓ Discovered {len(runner.migrations)} migration(s):")
        for m in runner.migrations:
            print(
                f"    - Version {m.source_version} -> {m.target_version}: {m.description}"
            )
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ Migration discovery/validation failed: {e}")
        sys.exit(1)

    # 3. Test validate_migrations explicitly
    print("\n[3/6] Testing MigrationRunner.validate_migrations()...")
    try:
        validated = MigrationRunner.validate_migrations(runner.migrations)
        print(f"  ✓ Validated {len(validated)} migration(s) into contiguous order.")
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ Validation failed: {e}")
        sys.exit(1)

    # 4. Test get_current_version() on live Spanner database
    print("\n[4/6] Querying current schema version from live database...")
    try:
        schema_version_table_exists = client.table_exists("SchemaVersion")
        print(f"  - SchemaVersion table exists: {schema_version_table_exists}")

        current_version = runner.get_current_version()
        print(f"  ✓ Current schema version on live DB: {current_version}")
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ Failed to query current version: {e}")
        sys.exit(1)

    # 5. Test get_pending_migrations()
    print("\n[5/6] Checking pending migrations...")
    try:
        pending = runner.get_pending_migrations(current_version=current_version)
        if pending:
            print(f"  ✓ Found {len(pending)} pending migration(s) to apply:")
            for m in pending:
                print(
                    f"    - {m.source_version} -> {m.target_version}: {m.description}"
                )
        else:
            print("  ✓ No pending migrations. Database is up-to-date.")
    except Exception as e:  # noqa: BLE001
        print(f"  ✗ Failed to get pending migrations: {e}")
        sys.exit(1)

    # 6. Apply migrations (if not dry-run and pending exist)
    print("\n[6/6] Executing MigrationRunner.run_migrations()...")
    if dry_run:
        print("  [DRY RUN] Skipping migration execution.")
    elif not pending:
        print("  Database is already up to date. No execution needed.")
    else:
        try:
            applied = runner.run_migrations()
            print(f"  ✓ Successfully applied {len(applied)} migration(s)!")

            # Verify new version after application
            new_version = runner.get_current_version()
            print(f"  ✓ Updated schema version on live DB: {new_version}")

            # Query rows in SchemaVersion table to inspect timestamps
            print("\n  SchemaVersion Table Records:")
            records_res = client.execute_query(
                "SELECT Version, AppliedTimestamp, Description FROM SchemaVersion ORDER BY AppliedTimestamp DESC"
            )
            if records_res.status == ExecutionStatus.SUCCESS:
                for row in records_res.rows:
                    print(f"    - Version {row[0]}: applied at {row[1]} ({row[2]})")
            else:
                print(f"    (Could not fetch rows: {records_res.error_message})")
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ Migration execution failed: {e}")
            sys.exit(1)

    print("\n" + "=" * 80)
    print("LIVE VALIDATION COMPLETED SUCCESSFULLY")
    print("=" * 80 + "\n")


def main() -> None:
    args = parse_args()
    run_live_test(
        project_id=args.project_id,
        instance_id=args.instance_id,
        database_id=args.database_id,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
