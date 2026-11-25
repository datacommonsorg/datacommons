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
"""Finds and waits for the preprocessor's ingestion report."""

import json
import time
from collections.abc import Callable

import click
from google.cloud import storage

# Workflow execution states after which no report will appear.
_DONE_STATES = {"SUCCEEDED", "FAILED", "CANCELLED"}

# How long `ingest start --wait` waits for the report.
WAIT_TIMEOUT_SECONDS = 30 * 60


def report_uri(bucket: str, artifacts_path: str, execution_id: str) -> str:
    """Returns where the preprocessor writes the report for workflow execution `execution_id`.

    The workflow runs the preprocessor with OUTPUT_DIR=gs://<bucket>/<artifacts
    path>, and the preprocessor writes its report under
    <OUTPUT_DIR>/datacommons/preprocessor_reports/<execution ID>/.
    """
    return (
        f"gs://{bucket}/{artifacts_path.strip('/')}/datacommons/"
        f"preprocessor_reports/{execution_id}/ingestion_report.json"
    )


def read_report(uri: str, project_id: str | None = None) -> dict | None:
    """Returns the report at `uri`, or None if it doesn't exist yet."""
    bucket_name, blob_name = uri.removeprefix("gs://").split("/", 1)
    blob = storage.Client(project=project_id).bucket(bucket_name).blob(blob_name)
    if not blob.exists():
        return None
    return json.loads(blob.download_as_text())


def wait_for_report(
    uri: str,
    get_state: Callable[[], str],
    *,
    project_id: str | None = None,
    timeout: float = WAIT_TIMEOUT_SECONDS,
    interval: float = 15,
) -> dict:
    """Polls `uri` until the report appears, and returns it.

    `get_state()` returns the workflow execution state. It is read before the
    report, so a run that ended before the read has already written any report
    it was going to write.

    Raises:
      click.ClickException: If the run ends without a report, or on timeout.
    """
    deadline = time.monotonic() + timeout
    while True:
        state = get_state()
        report = read_report(uri, project_id)
        if report is not None:
            return report
        if state in _DONE_STATES:
            raise click.ClickException(
                f"The workflow execution is {state} and wrote no report at {uri}."
            )
        if time.monotonic() >= deadline:
            raise click.ClickException(
                f"Timed out after {timeout / 60:.0f} minutes waiting for the "
                f"report at {uri}."
            )
        time.sleep(interval)
