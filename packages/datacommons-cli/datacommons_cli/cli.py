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

import os

import click

from datacommons_admin.admin_cli import admin as admin_cli

from . import version


def get_logo_color():
    """Determine the best logo color based on terminal capabilities"""
    colorterm = os.environ.get("COLORTERM", "").lower()
    if colorterm in ("truecolor", "24bit"):
        return (7, 81, 179)

    term = os.environ.get("TERM", "").lower()
    if "256color" in term or colorterm:
        return 26  # Royal blue color index in 256-color palette

    return "blue"


class CustomGroup(click.Group):
    """Custom click.Group to preserve logo formatting and newlines in help text"""

    def format_help_text(self, ctx, formatter):
        if self.help:
            formatter.write_paragraph()
            with formatter.indentation():
                for line in self.help.splitlines():
                    if line:
                        formatter.write(f"{' ' * formatter.current_indent}{line}\n")
                    else:
                        formatter.write("\n")


def cli_help() -> str:
    """Return help string for the CLI"""
    logo = (
        "    ██████╗   ██████╗\n"
        "    ██╔══██╗ ██╔════╝\n"
        "    ██║  ██║ ██║     \n"
        "    ██║  ██║ ██║     \n"
        "    ██████╔╝ ╚██████╗\n"
        "    ╚═════╝   ╚═════╝"
    )
    styled_logo = click.style(logo, fg=get_logo_color(), bold=True)
    version_str = click.style(f"v{version.__version__}", fg="bright_black")
    return f"{styled_logo}\n\nData Commons CLI {version_str}"


@click.group(cls=CustomGroup, help=cli_help())
@click.version_option(version=version.__version__, prog_name="Data Commons CLI")
def cli():
    """Data Commons CLI"""
    pass


# Add admin CLI commands to the main CLI
cli.add_command(admin_cli)
