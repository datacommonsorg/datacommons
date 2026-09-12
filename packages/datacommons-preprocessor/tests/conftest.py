# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Shared pytest configuration for the preprocessor test suite."""

from pathlib import Path

import pytest

# Package root, i.e. the directory containing `tests/`.
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _run_from_package_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """Runs every test with the package root as the working directory.

    Several golden config fixtures under tests/stats/test_data/runner/config/
    embed working-directory-relative paths such as
    "tests/stats/test_data/runner/input/...". In the import repo these resolved
    because run_test.sh invoked pytest from inside simple/. Here pytest runs from
    the workspace root, so pin the working directory explicitly rather than
    rewriting the fixtures.

    This is also what keeps the suite order-independent: without it, a test that
    changes the working directory leaks into every test that runs after it.
    """
    monkeypatch.chdir(_PACKAGE_ROOT)
