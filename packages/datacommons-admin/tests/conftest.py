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
from click.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_tf_output_spanner():
    """Returns a mock JSON string representing Terraform outputs for DB commands."""
    return (
        '{"ingestion_service_url": {"value": "https://mock-helper"}, '
        '"ingestion_workflow_service_account_email": {"value": "mock-orch-sa@mock.com"}, '
        '"spanner_instance_id": {"value": "mock-instance"}, '
        '"spanner_database_id": {"value": "mock-db"}, '
        '"project_id": {"value": "mock-proj"}}'
    )


@pytest.fixture
def mock_tf_output_ingest():
    """Returns a mock JSON string representing Terraform outputs for Ingest commands."""
    return (
        '{"ingestion_prep_job_name": {"value": "projects/mock-proj/locations/us-central1/jobs/mock-job"}, '
        '"ingestion_workflow_service_account_email": {"value": "mock-orch-sa@mock.com"}, '
        '"project_id": {"value": "mock-proj"}, '
        '"region": {"value": "us-central1"}, '
        '"ingestion_workflow_name": {"value": "mock-workflow"}}'
    )
