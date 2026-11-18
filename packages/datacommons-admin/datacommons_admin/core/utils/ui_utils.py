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


def _log_resolved_value(label: str, value: str, is_default: bool, indent: int = 2):
    """Logs a value with a bullet if default, or a green checkmark if from flag."""
    prefix = " " * indent
    padded_label = label.ljust(12)
    if is_default:
        click.echo(f"{prefix}- {padded_label}: {value} (Default)")
    else:
        click.secho(f"{prefix}✔", fg="green", nl=False)
        click.echo(f" {padded_label}: {value} (from flag)")


def _prompt(text: str, indent: int = 2, **kwargs):
    """Prints the cyan [?] prompt symbol and calls click.prompt."""
    click.secho(" " * indent + "[?]", fg="cyan", bold=True, nl=False)
    prompt_text = text if text.startswith(" ") else f" {text}"
    return click.prompt(prompt_text, **kwargs)


def _confirm(text: str, indent: int = 2, **kwargs):
    """Prints the cyan [?] prompt symbol and calls click.confirm."""
    click.secho(" " * indent + "[?]", fg="cyan", bold=True, nl=False)
    prompt_text = text if text.startswith(" ") else f" {text}"
    return click.confirm(prompt_text, **kwargs)
