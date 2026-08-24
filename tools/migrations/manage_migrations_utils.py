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

FILENAME_PATTERN = re.compile(r"^(\d{14})_([a-z0-9_]+)\.py$")
ISO_8601_UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
NAME_PATTERN = re.compile(r"^[a-z0-9_]+$")


def _resolve_default_migrations_dir() -> Path:
    """Resolves the default migrations directory via package discovery or monorepo fallback."""
    try:
        import datacommons_db.migrations.migration_scripts as mig_pkg

        if mig_pkg.__file__:
            return Path(mig_pkg.__file__).resolve().parent
    except (ImportError, AttributeError):
        pass

    # Fallback to repository layout if package is not installed in environment
    return (
        Path(__file__).resolve().parents[2]
        / "packages"
        / "datacommons-db"
        / "datacommons_db"
        / "migrations"
        / "migration_scripts"
    )


DEFAULT_MIGRATIONS_DIR = _resolve_default_migrations_dir()


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


def escape_docstring(text: str) -> str:
    """Escapes a text string for safe inclusion within triple-quoted docstrings.

    Args:
        text: Raw input string to be included in a docstring.

    Returns:
        Escaped string safe to embed inside triple quotes.
    """
    return text.replace("\\", "\\\\").replace('"', r'\"')


def generate_migration_content(description: str, creation_timestamp: str) -> str:
    """Generates boilerplate Python source code for a new SchemaMigration script.

    Args:
        description: Human-readable description string.
        creation_timestamp: UTC ISO-8601 formatted timestamp string.

    Returns:
        Formatted Python source code string.
    """
    current_year = datetime.datetime.now(datetime.UTC).year
    desc_literal = repr(description)
    safe_docstring = escape_docstring(description)

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
    """{safe_docstring}"""

    description: str = {desc_literal}
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


def find_migration_file(
    target: str | Path,
    migrations_dir: Path | None = None,
) -> Path:
    """Locates an existing migration file by name, prefix, or relative/absolute path.

    Args:
        target: Target identifier or Path (e.g. filename, change name, prefix, or path).
        migrations_dir: Directory containing migration scripts.

    Returns:
        Path to the matching migration script.

    Raises:
        FileNotFoundError: If migrations directory or matching file is not found.
        ValueError: If multiple matching files exist (ambiguous target).
    """
    target_dir = migrations_dir or DEFAULT_MIGRATIONS_DIR
    target_path = Path(target)

    # First, try direct path check
    if target_path.is_file():
        return target_path.resolve()

    if (target_dir / target_path).is_file():
        return (target_dir / target_path).resolve()

    if not target_dir.is_dir():
        raise FileNotFoundError(f"Migrations directory does not exist: {target_dir}")

    # Otherwise, try matching against all migration filenames

    # Clean target for matching
    target_name = target_path.name if isinstance(target, Path) else target.strip()
    cleaned_target = target_name[:-3] if target_name.endswith(".py") else target_name

    sanitized_target: str | None = None
    with contextlib.suppress(ValueError):
        sanitized_target = sanitize_name(cleaned_target)

    all_scripts = [
        f
        for f in target_dir.glob("*.py")
        if not f.name.startswith("_") and f.name != "__init__.py"
    ]

    # Match against scripts by:
    # 1. Full stem (e.g. '20260817000000_bootstrap')
    # 2. Timestamp prefix (e.g. '20260817000000')
    # 3. Change name (e.g. 'bootstrap' or sanitized 'Add-Node' -> 'add_node')
    matches: list[Path] = []
    for script in all_scripts:
        stem = script.stem
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
    file_path = find_migration_file(target, migrations_dir)

    filename = file_path.name
    match = FILENAME_PATTERN.match(filename)
    if not match:
        raise ValueError(
            f"Migration filename '{filename}' does not match expected convention "
            "'YYYYMMDDHHMMSS_<description>.py'"
        )

    change_name = match.group(2)
    new_prefix, new_iso = generate_utc_timestamps(target_dt)
    new_filename = f"{new_prefix}_{change_name}.py"
    new_path = file_path.parent / new_filename

    # Ensure target doesn't already exist if renamed
    if new_path != file_path and new_path.exists():
        raise FileExistsError(f"Target migration file already exists: {new_path.name}")

    content = file_path.read_text(encoding="utf-8")

    # Validate syntax of existing script before modification
    try:
        ast.parse(content, filename=str(file_path))
    except SyntaxError as e:
        raise ValueError(
            f"Target migration script '{file_path.name}' has syntax errors: {e}"
        ) from e

    # Substitute creation_timestamp attribute in memory
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

    # Write updated content and remove old file if renamed
    new_path.write_text(updated_content, encoding="utf-8")
    if new_path != file_path:
        file_path.unlink()

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

    # Collect and sort migration script files chronologically by filename
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
        # Extract description and timestamp attributes from script content via AST
        try:
            content = script.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(script))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Check for docstring if description attribute is absent
                    class_doc = ast.get_docstring(node)
                    if class_doc and not desc:
                        desc = class_doc.strip()

                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            if (
                                target.id == "description"
                                and isinstance(node.value, ast.Constant)
                                and isinstance(node.value.value, str)
                            ):
                                desc = node.value.value
                            elif (
                                target.id == "creation_timestamp"
                                and isinstance(node.value, ast.Constant)
                                and isinstance(node.value.value, str)
                            ):
                                creation_ts = node.value.value
                elif isinstance(node, ast.AnnAssign):
                    if (
                        isinstance(node.target, ast.Name)
                        and node.value
                        and isinstance(node.value, ast.Constant)
                        and isinstance(node.value.value, str)
                    ):
                        if node.target.id == "description":
                            desc = node.value.value
                        elif node.target.id == "creation_timestamp":
                            creation_ts = node.value.value
        except SyntaxError as e:
            desc = f"<syntax error: {e.msg}>"
        except (OSError, UnicodeDecodeError):
            desc = "<error reading file>"

        # Fallback: derive ISO timestamp from the 14-digit prefix if missing from source
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
