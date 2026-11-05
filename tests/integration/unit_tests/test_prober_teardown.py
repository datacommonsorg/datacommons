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

"""Unit tests for prober_runner.teardown_infra secret cleanup."""

from pathlib import Path
from unittest.mock import patch

from tests.integration.prober import prober_runner


def _secret_delete_calls(mock_run) -> list[list[str]]:
    return [
        c.args[0]
        for c in mock_run.call_args_list
        if c.args and c.args[0][:3] == ["gcloud", "secrets", "delete"]
    ]


def test_secret_deleted_even_when_provisioning_failed(tmp_path: Path) -> None:
    # instance_dir is None when provision_infra fails after init created the secret.
    with patch.object(prober_runner.subprocess, "run") as mock_run:
        prober_runner.teardown_infra(
            instance_dir=None,
            workspace_dir=tmp_path,
            skip_destroy=False,
            project_id="my-proj",
            instance_name="prober-abc",
        )
    assert _secret_delete_calls(mock_run) == [
        [
            "gcloud",
            "secrets",
            "delete",
            "prober-abc-dc-api-key",
            "--project=my-proj",
            "--quiet",
        ]
    ]


def test_secret_kept_when_skip_destroy(tmp_path: Path) -> None:
    with patch.object(prober_runner.subprocess, "run") as mock_run:
        prober_runner.teardown_infra(
            instance_dir=None,
            workspace_dir=tmp_path,
            skip_destroy=True,
            project_id="my-proj",
            instance_name="prober-abc",
        )
    assert _secret_delete_calls(mock_run) == []
