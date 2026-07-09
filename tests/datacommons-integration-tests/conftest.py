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

import pytest

"""Pytest configuration and option definitions for local integration tests.

NOTE: The filename 'conftest.py' is a special, mandatory name reserved by pytest.
Pytest automatically detects and loads this file to register shared fixtures and
custom command-line options for all tests in this directory. Do not rename it.
"""


def pytest_addoption(parser):
    parser.addoption(
        "--services-image",
        default=None,
        help="Override default serving services container image",
    )
    parser.addoption(
        "--helper-image", default=None, help="Override default helper service image"
    )
    parser.addoption(
        "--ingestion-image",
        default=None,
        help="Override default Java ingestion loader image",
    )
    parser.addoption(
        "--keep-containers",
        action="store_true",
        help="Do not tear down containers on completion/failure",
    )
    parser.addoption(
        "--generate-golden",
        action="store_true",
        help="Regenerate golden files for responses/tables rather than asserting",
    )


@pytest.fixture(scope="session")
def keep_containers(request):
    return request.config.getoption("--keep-containers")


@pytest.fixture(scope="session")
def services_image(request):
    return request.config.getoption("--services-image")


@pytest.fixture(scope="session")
def helper_image(request):
    return request.config.getoption("--helper-image")


@pytest.fixture(scope="session")
def ingestion_image(request):
    return request.config.getoption("--ingestion-image")


@pytest.fixture(scope="session")
def generate_golden(request):
    return request.config.getoption("--generate-golden")
