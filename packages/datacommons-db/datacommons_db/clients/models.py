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

"""Data models and result types for database clients."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class ExecutionStatus(StrEnum):
    """Status of a Spanner database operation."""

    SUCCESS = "SUCCESS"
    ERROR = "ERROR"


@dataclass(frozen=True)
class DdlResult:
    """Result of a DDL statement execution.

    Attributes:
        status: Execution status enum (SUCCESS or ERROR).
        error_message: Error message string if execution failed, None otherwise.
    """

    status: ExecutionStatus
    error_message: str | None = None


@dataclass(frozen=True)
class DmlResult:
    """Result of a DML statement execution inside a read-write transaction.

    Attributes:
        status: Execution status enum (SUCCESS or ERROR).
        rows_affected: Number of rows modified by the DML statement (0 on failure).
        error_message: Error message string if execution failed, None otherwise.
    """

    status: ExecutionStatus
    rows_affected: int = 0
    error_message: str | None = None


@dataclass(frozen=True)
class QueryResult:
    """Result of a snapshot read query.

    Attributes:
        status: Execution status enum (SUCCESS or ERROR).
        rows: List of rows where each row is a list of column values ([] on failure).
        error_message: Error message string if execution failed, None otherwise.
    """

    status: ExecutionStatus
    rows: list[list[Any]] = field(default_factory=list)
    error_message: str | None = None


@dataclass(frozen=True)
class LockState:
    """State of a row in the IngestionLock table.

    Attributes:
        exists: Whether a row with the given lock ID exists.
        owner: The workflow or process ID holding the lock, or None if unlocked.
        acquired_at: The timestamp when the lock was acquired, or None if unlocked.
    """

    exists: bool
    owner: str | None = None
    acquired_at: datetime | None = None
