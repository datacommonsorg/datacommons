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

"""tools.migrations.manage_migrations_utils - Core Utilities for Migration Management.

Provides pure Python helper functions for creating, updating, resolving,
and discovering Spanner schema migration scripts in packages/datacommons-db.
"""

import ast
import contextlib
import datetime
import re
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MIGRATIONS_DIR = (
    REPO_ROOT
    / "packages"
    / "datacommons-db"
    / "datacommons_db"
    / "migrations"
    / "migration_scripts"
)

FILENAME_PATTERN = re.compile(r"^(\d{14})_([a-z0-9_]+)\.py$")
ISO_8601_UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
NAME_PATTERN = re.compile(r"^[a-z0-9_]+$")


@dataclass(frozen=True)
class MigrationInfo:
    """Metadata describing a discovered migration script.

    Attributes:
        index: 1-based chronological index.
        prefix_timestamp: 14-digit prefix timestamp (YYYYMMDDHHMMSS).
        creation_timestamp: UTC ISO-8601 timestamp string (YYYY-MM-DDTHH:MM:SSZ).
        filename: Migration script filename.
        file_path: Absolute path to the migration script.
        description: Human-readable description extracted from migration class.
    """

    index: int
    prefix_timestamp: str
    creation_timestamp: str
    filename: str
    file_path: Path
    description: str


def sanitize_name(raw_name: str) -> str:
    """Sanitizes and validates a migration change name into snake_case.

    Args:
        raw_name: Raw input name from user.

    Returns:
        Sanitized snake_case name string.

    Raises:
        ValueError: If the resulting name is empty or invalid.
    """
    cleaned = raw_name.strip().lower()
    # Replace whitespace and hyphens with underscores
    cleaned = re.sub(r"[\s\-]+", "_", cleaned)
    # Remove duplicate underscores
    cleaned = re.sub(r"_+", "_", cleaned)
    # Strip leading/trailing underscores
    cleaned = cleaned.strip("_")

    if not cleaned:
        raise ValueError("Migration name cannot be empty.")

    if not NAME_PATTERN.match(cleaned):
        raise ValueError(
            f"Invalid migration name '{raw_name}'. "
            "Name must contain only lowercase letters, digits, and underscores."
        )

    return cleaned


def get_utc_timestamps(
    target_dt: datetime.datetime | None = None,
) -> tuple[str, str]:
    """Generates the file prefix timestamp and ISO-8601 creation timestamp string.

    Args:
        target_dt: Optional specific datetime (defaults to current UTC time).

    Returns:
        Tuple of (filename_prefix_timestamp, iso_8601_creation_timestamp).
    """
    dt = target_dt or datetime.datetime.now(datetime.UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.UTC)
    else:
        dt = dt.astimezone(datetime.UTC)

    prefix_ts = dt.strftime("%Y%m%d%H%M%S")
    iso_ts = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return prefix_ts, iso_ts


def generate_migration_content(description: str, creation_timestamp: str) -> str:
    """Generates boilerplate Python source code for a new SchemaMigration script.

    Args:
        description: Human-readable description string.
        creation_timestamp: UTC ISO-8601 formatted timestamp string.

    Returns:
        Formatted Python source code string.
    """
    current_year = datetime.datetime.now(datetime.UTC).year
    escaped_desc = description.replace('"', '\\"')

    return f'''# Copyright {current_year} Google LLC.
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

from datacommons_db.clients.spanner_client import ExecutionStatus, SpannerClient
from datacommons_db.migrations.base import SchemaMigration


class Migration(SchemaMigration):
    """{description}"""

    description: str = "{escaped_desc}"
    creation_timestamp: str = "{creation_timestamp}"

    def upgrade(self, spanner_client: SpannerClient) -> None:
        """Executes forward schema changes to upgrade the database.

        Args:
            spanner_client: SpannerClient instance to execute DDL / DML.

        Raises:
            RuntimeError: If any DDL or DML operation fails.
        """
        # Example DDL execution:
        # result = spanner_client.execute_ddl([
        #     "CREATE TABLE ExampleTable (Id STRING(64) NOT NULL) PRIMARY KEY (Id)"
        # ])
        # if result.status != ExecutionStatus.SUCCESS:
        #     raise RuntimeError(f"Failed to apply migration: {{result.error_message}}")
        raise NotImplementedError(
            "Migration upgrade logic has not been implemented yet."
        )
'''


def create_migration_file(
    name: str,
    description: str | None = None,
    migrations_dir: Path | None = None,
    target_dt: datetime.datetime | None = None,
) -> tuple[Path, str, str]:
    """Creates a new timestamped migration script file from template.

    Args:
        name: Name of the migration change.
        description: Optional human-readable description string.
        migrations_dir: Directory to place the script in (defaults to datacommons-db migration_scripts).
        target_dt: Optional specific datetime (defaults to current UTC time).

    Returns:
        Tuple of (created_file_path, iso_creation_timestamp, resolved_description).

    Raises:
        ValueError: If name is invalid.
        FileExistsError: If target migration file already exists.
    """
    target_dir = migrations_dir or DEFAULT_MIGRATIONS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    sanitized = sanitize_name(name)
    desc = (
        description.strip()
        if description and description.strip()
        else sanitized.replace("_", " ").capitalize()
    )

    prefix_ts, iso_ts = get_utc_timestamps(target_dt)
    filename = f"{prefix_ts}_{sanitized}.py"
    target_file = target_dir / filename

    if target_file.exists():
        raise FileExistsError(
            f"Migration file '{filename}' already exists in {target_dir}"
        )

    content = generate_migration_content(desc, iso_ts)
    target_file.write_text(content, encoding="utf-8")

    return target_file, iso_ts, desc


def find_migration_file(target: str, migrations_dir: Path | None = None) -> Path:
    """Locates an existing migration file by name, prefix, or relative/absolute path.

    Args:
        target: Target identifier (e.g. filename, change name, prefix, or path).
        migrations_dir: Directory containing migration scripts.

    Returns:
        Path to the matching migration script.

    Raises:
        FileNotFoundError: If migrations directory or matching file is not found.
        ValueError: If multiple matching files exist (ambiguous target).
    """
    target_dir = migrations_dir or DEFAULT_MIGRATIONS_DIR
    target_path = Path(target)

    # 1. Direct path check
    if target_path.is_file():
        return target_path.resolve()

    if (target_dir / target).is_file():
        return (target_dir / target).resolve()

    if not target_dir.is_dir():
        raise FileNotFoundError(f"Migrations directory does not exist: {target_dir}")

    # Clean target for matching
    cleaned_target = target.strip()
    if cleaned_target.endswith(".py"):
        cleaned_target = cleaned_target[:-3]

    sanitized_target: str | None = None
    with contextlib.suppress(ValueError):
        sanitized_target = sanitize_name(cleaned_target)

    all_scripts = [
        f
        for f in target_dir.glob("*.py")
        if not f.name.startswith("_") and f.name != "__init__.py"
    ]

    matches: list[Path] = []
    for script in all_scripts:
        stem = script.stem  # e.g. "20260817000000_bootstrap"
        match = FILENAME_PATTERN.match(script.name)
        if stem == cleaned_target:
            matches.append(script)
        elif match:
            prefix, change_name = match.group(1), match.group(2)
            if cleaned_target in (prefix, change_name) or (
                sanitized_target and change_name == sanitized_target
            ):
                matches.append(script)

    if not matches:
        raise FileNotFoundError(
            f"No migration script found matching '{target}' in {target_dir}"
        )

    if len(matches) > 1:
        match_names = ", ".join(m.name for m in matches)
        raise ValueError(
            f"Ambiguous target '{target}'. Matches multiple migration files: {match_names}. "
            "Please specify the full filename."
        )

    return matches[0]


def update_migration_file(
    target: str | Path,
    migrations_dir: Path | None = None,
    target_dt: datetime.datetime | None = None,
) -> tuple[Path, Path, str]:
    """Re-timestamps an existing migration script file and renames it.

    Args:
        target: Target identifier or Path to the existing migration script.
        migrations_dir: Directory containing migration scripts.
        target_dt: Optional specific datetime (defaults to current UTC time).

    Returns:
        Tuple of (old_file_path, new_file_path, new_iso_timestamp).

    Raises:
        FileNotFoundError: If target file is not found.
        ValueError: If file is malformed or creation_timestamp is not found.
        FileExistsError: If new target filename already exists.
    """
    file_path = (
        target
        if isinstance(target, Path)
        else find_migration_file(target, migrations_dir)
    )

    filename = file_path.name
    match = FILENAME_PATTERN.match(filename)
    if not match:
        raise ValueError(
            f"Migration filename '{filename}' does not match expected convention "
            "'YYYYMMDDHHMMSS_<description>.py'"
        )

    change_name = match.group(2)
    new_prefix, new_iso = get_utc_timestamps(target_dt)
    new_filename = f"{new_prefix}_{change_name}.py"
    new_path = file_path.parent / new_filename

    content = file_path.read_text(encoding="utf-8")

    # Replace creation_timestamp attribute
    ts_pattern = re.compile(
        r'(creation_timestamp\s*(?::\s*str)?\s*=\s*["\'])[^"\']+(["\'])'
    )
    if not ts_pattern.search(content):
        raise ValueError(
            f"Could not find 'creation_timestamp' attribute in {file_path.name}"
        )

    updated_content = ts_pattern.sub(rf"\g<1>{new_iso}\g<2>", content)

    # Validate syntax of updated content
    try:
        ast.parse(updated_content, filename=str(new_path))
    except SyntaxError as e:
        raise ValueError(f"Updated migration script has syntax errors: {e}") from e

    # If new filename is different from old filename, ensure target doesn't already exist
    if new_path != file_path and new_path.exists():
        raise FileExistsError(f"Target migration file already exists: {new_path.name}")

    # Write updated content and rename if needed
    if new_path != file_path:
        file_path.unlink()
    new_path.write_text(updated_content, encoding="utf-8")

    return file_path, new_path, new_iso


def discover_migrations(
    migrations_dir: Path | None = None,
) -> list[MigrationInfo]:
    """Discovers all migration scripts in chronological order with metadata.

    Args:
        migrations_dir: Directory containing migration scripts.

    Returns:
        List of MigrationInfo dataclass instances sorted chronologically.
    """
    target_dir = migrations_dir or DEFAULT_MIGRATIONS_DIR
    if not target_dir.is_dir():
        return []

    script_files = sorted(
        [
            f
            for f in target_dir.glob("*.py")
            if not f.name.startswith("_") and f.name != "__init__.py"
        ],
        key=lambda f: f.name,
    )

    results: list[MigrationInfo] = []
    for idx, script in enumerate(script_files, start=1):
        filename = script.name
        match = FILENAME_PATTERN.match(filename)
        prefix = match.group(1) if match else "INVALID"

        desc = ""
        creation_ts = ""
        try:
            content = script.read_text(encoding="utf-8")
            desc_match = re.search(
                r'description\s*(?::\s*str)?\s*=\s*["\']([^"\']+)["\']', content
            )
            if desc_match:
                desc = desc_match.group(1)

            ts_match = re.search(
                r'creation_timestamp\s*(?::\s*str)?\s*=\s*["\']([^"\']+)["\']',
                content,
            )
            if ts_match:
                creation_ts = ts_match.group(1)
        except (OSError, UnicodeDecodeError):
            desc = "<error reading file>"

        if not creation_ts and match:
            p = match.group(1)
            creation_ts = f"{p[:4]}-{p[4:6]}-{p[6:8]}T{p[8:10]}:{p[10:12]}:{p[12:14]}Z"

        results.append(
            MigrationInfo(
                index=idx,
                prefix_timestamp=prefix,
                creation_timestamp=creation_ts,
                filename=filename,
                file_path=script,
                description=desc,
            )
        )

    return results
