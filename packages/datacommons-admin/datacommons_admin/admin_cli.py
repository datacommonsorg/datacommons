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

import click

from datacommons_admin.db.db_cli import init_db, migrate_db, seed_db
from datacommons_admin.ingest.ingest_cli import ingest
from datacommons_admin.init.init_cli import init


@click.group()
@click.option(
    "--project-id",
    default=None,
    help="GCP project ID used to locate the remote Terraform state bucket.",
)
@click.option(
    "--instance-name",
    default=None,
    help="DCP instance name (prefix) used to locate the remote Terraform state bucket.",
)
@click.option(
    "--tf-state-location",
    default=None,
    help="Exact GCS URI of the Terraform state file (gs://bucket/prefix/default.tfstate).",
)
@click.pass_context
def admin(
    ctx: click.Context,
    project_id: str | None,
    instance_name: str | None,
    tf_state_location: str | None,
) -> None:
    """Manage a Data Commons Platform instance in Google Cloud.

    Remote-state options select the deployed instance used by the requested
    admin command. They read state directly from GCS and do not create or
    update local Terraform files.
    """
    ctx.ensure_object(dict)
    ctx.obj["project_id"] = project_id
    ctx.obj["instance_name"] = instance_name
    ctx.obj["tf_state_location"] = tf_state_location


admin.add_command(init)
admin.add_command(init_db)
admin.add_command(seed_db)
admin.add_command(migrate_db)
admin.add_command(ingest)
