# Copyright 2025 Google LLC.
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

from datacommons_api.core.logging import get_logger, setup_logging
from datacommons_api.api_cli import api as api_cli
from datacommons_schema.schema_cli import schema as schema_cli

setup_logging()
logger = get_logger(__name__)

@click.group()
def cli():
    """Datacommons CLI suite"""
    pass

# Add schema CLI commands to the main CLI
cli.add_command(api_cli)
cli.add_command(schema_cli)
