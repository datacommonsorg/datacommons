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
def admin() -> None:
    """Manage a Data Commons Platform instance in Google Cloud"""


admin.add_command(init)
admin.add_command(init_db)
admin.add_command(seed_db)
admin.add_command(migrate_db)
admin.add_command(ingest)
