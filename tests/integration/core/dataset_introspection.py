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

"""Reads facts about test datasets (provenances, locally declared DCIDs) from their source files."""

import json
import re
from collections.abc import Iterable
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]

# Namespace prefixes accepted by the simple importer for DCID references.
_DCID_PREFIXES = ("dcid:", "dcs:", "schema:")

# Matches MCF node declarations: "Node: dcid:X", "Node: X", "dcid: \"X\"", "dcid: dcid:X".
_MCF_DCID_LINE = re.compile(r"^\s*(?:Node|dcid)\s*:\s*(.+?)\s*$")


def _strip_dcid(value: str) -> str:
    value = value.strip().strip('"').strip()
    for prefix in _DCID_PREFIXES:
        if value.startswith(prefix):
            return value[len(prefix) :].strip()
    return value


def _resolve_dir(dataset_dir: str | Path) -> Path:
    path = Path(dataset_dir)
    return path if path.is_absolute() else _REPO_ROOT / path


def _has_observation_entity_column(file_config: dict) -> bool:
    """True if the file's observations carry an observationAbout entity.

    Files without columnMappings use the default layout (entity in the first
    column). Files with columnMappings must map observationAbout; multi-entity
    files (e.g. sourceCountry/destinationCountry only) do not.
    """
    mappings = file_config.get("columnMappings")
    if not mappings:
        return True
    return any(_strip_dcid(key) == "observationAbout" for key in mappings)


def observation_entity_provenances(dataset_dirs: Iterable[str | Path]) -> set[str]:
    """Returns provenance IDs of input files whose observations have an observationAbout entity.

    These are the files for which the importer can generate proxy entity nodes.
    Supports both `inputFiles` shapes accepted by the simple importer: a list of
    per-file configs and a dict keyed by file pattern. IDs are returned without
    namespace prefixes, matching Observation.provenance.
    """
    provenances: set[str] = set()
    for dataset_dir in dataset_dirs:
        config_path = _resolve_dir(dataset_dir) / "config.json"
        if not config_path.is_file():
            continue
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)

        input_files = config.get("inputFiles", [])
        file_configs = (
            input_files.values() if isinstance(input_files, dict) else input_files
        )
        for file_config in file_configs:
            if not isinstance(file_config, dict) or not file_config.get("provenance"):
                continue
            if _has_observation_entity_column(file_config):
                provenances.add(_strip_dcid(file_config["provenance"]))
    return provenances


def declared_mcf_dcids(dataset_dirs: Iterable[str | Path]) -> set[str]:
    """Returns every DCID declared as a node in the datasets' *.mcf files."""
    dcids: set[str] = set()
    for dataset_dir in dataset_dirs:
        for mcf_path in sorted(_resolve_dir(dataset_dir).glob("*.mcf")):
            with open(mcf_path, encoding="utf-8") as f:
                for line in f:
                    match = _MCF_DCID_LINE.match(line)
                    if match:
                        dcid = _strip_dcid(match.group(1))
                        if dcid:
                            dcids.add(dcid)
    return dcids
