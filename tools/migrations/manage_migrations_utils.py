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

Provides pure Python helper functions for creating and validating
Spanner schema migration scripts in packages/datacommons-db.
"""

import ast
import datetime
import json
import re
from importlib import resources
from pathlib import Path

FILENAME_PATTERN = re.compile(r"^(\d{14})_([a-z0-9_]+)\.py$")
ISO_8601_UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
NAME_PATTERN = re.compile(r"^[a-z0-9_]+$")


def get_default_migrations_dir() -> Path:
    """Resolves the default migrations directory.

    Searches upward from the current file and working directory to locate the
    local source tree migration scripts before falling back to package discovery.
    """
    rel_migration_path = (
        Path("packages")
        / "datacommons-db"
        / "datacommons_db"
        / "migrations"
        / "migration_scripts"
    )

    # Search upward from this file and current working directory
    search_origins = [Path(__file__).resolve(), Path.cwd().resolve()]
    for origin in search_origins:
        for parent in [origin, *origin.parents]:
            candidate = parent / rel_migration_path
            if candidate.is_dir():
                return candidate

    # Fallback to imported package path if running in a non-standard environment
    try:
        import datacommons_db.migrations.migration_scripts as mig_pkg

        if mig_pkg.__file__:
            return Path(mig_pkg.__file__).resolve().parent
    except (ImportError, AttributeError):
        pass

    # Default fallback path relative to repository layout
    return Path(__file__).resolve().parents[2] / rel_migration_path


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


def generate_utc_timestamps(
    target_dt: datetime.datetime | None = None,
) -> tuple[str, str]:
    """Generates the file prefix timestamp and ISO-8601 creation timestamp string.

    Args:
        target_dt: Optional specific datetime (defaults to current UTC time).

    Returns:
        Tuple of (filename_prefix_timestamp, iso_8601_creation_timestamp).
    """
    dt = target_dt or datetime.datetime.now(datetime.UTC)
    # Ensure datetime is timezone-aware and normalized to UTC
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
    current_year = str(datetime.datetime.now(datetime.UTC).year)
    desc_literal = json.dumps(description)

    template_text = (
        resources.files("tools.migrations.templates")
        .joinpath("migration_template.py")
        .read_text(encoding="utf-8")
    )
    content = template_text.replace("2026 Google LLC", f"{current_year} Google LLC")
    content = content.replace('"__DESCRIPTION__"', desc_literal)
    return content.replace('"__CREATION_TIMESTAMP__"', f'"{creation_timestamp}"')


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
    target_dir = migrations_dir or get_default_migrations_dir()
    target_dir.mkdir(parents=True, exist_ok=True)

    sanitized = sanitize_name(name)
    desc = (
        description.strip()
        if description and description.strip()
        else sanitized.replace("_", " ").capitalize()
    )

    prefix_ts, iso_ts = generate_utc_timestamps(target_dt)
    filename = f"{prefix_ts}_{sanitized}.py"
    target_file = target_dir / filename

    if target_file.exists():
        raise FileExistsError(
            f"Migration file '{filename}' already exists in {target_dir}"
        )

    content = generate_migration_content(desc, iso_ts)

    # Validate syntax before writing to disk
    try:
        ast.parse(content, filename=str(target_file))
    except SyntaxError as e:
        raise ValueError(f"Generated migration script has syntax errors: {e}") from e

    target_file.write_text(content, encoding="utf-8")

    return target_file, iso_ts, desc
