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

"""Unit tests for dataset_introspection.py."""

import json

from tests.integration.core.dataset_introspection import (
    declared_mcf_dcids,
    observation_entity_provenances,
)


def test_provenances_from_real_datasets():
    """Reads provenance IDs (prefix stripped) from the checked-in test datasets."""
    assert observation_entity_provenances(
        ["tests/integration/test_data/foobar_wages"]
    ) == {
        "FooBarWages",
        "FooBarGenderWageGap",
    }
    assert observation_entity_provenances(
        [
            "tests/integration/test_data/foobar_wages",
            "tests/integration/test_data/foobar_education",
        ]
    ) == {"FooBarWages", "FooBarGenderWageGap", "FooBarCustomEducation"}


def test_provenances_dict_shaped_input_files(tmp_path):
    """Supports the dict-keyed inputFiles shape and skips files without provenance."""
    (tmp_path / "config.json").write_text(
        json.dumps(
            {
                "inputFiles": {
                    "a.csv": {"provenance": "dcid:ProvA"},
                    "b.csv": {"provenance": "ProvB"},
                    "c.csv": {},
                }
            }
        )
    )
    assert observation_entity_provenances([tmp_path]) == {"ProvA", "ProvB"}


def test_provenances_missing_config(tmp_path):
    assert observation_entity_provenances([tmp_path]) == set()


def test_declared_mcf_dcids_real_dataset():
    """Declared nodes include local schema (wagesAnnual) but not referenced remote ones (Person)."""
    dcids = declared_mcf_dcids(["tests/integration/test_data/foobar_wages"])
    assert {
        "average_annual_wage",
        "gender_wage_gap",
        "FooBarGroup",
        "wagesAnnual",
    } <= dcids
    assert "Person" not in dcids
    assert "country/USA" not in dcids


def test_declared_mcf_dcids_syntax_variants(tmp_path):
    (tmp_path / "nodes.mcf").write_text(
        "Node: dcid:A\n"
        "typeOf: dcid:Place\n"
        "containedInPlace: dcid:country/USA\n"
        "\n"
        "Node: B\n"
        'dcid: "C"\n'
        "\n"
        "Node: dcs:D\n"
    )
    assert declared_mcf_dcids([tmp_path]) == {"A", "B", "C", "D"}


def test_provenances_exclude_multi_entity_files():
    """Multi-entity files (no observationAbout mapping) are out of scope."""
    assert (
        observation_entity_provenances(["tests/integration/test_data/financial_trade"])
        == set()
    )


def test_provenances_default_layout_without_column_mappings(tmp_path):
    """Files without columnMappings use the default layout (entity in column 0)."""
    (tmp_path / "config.json").write_text(
        json.dumps({"inputFiles": {"a.csv": {"provenance": "ProvA"}}})
    )
    assert observation_entity_provenances([tmp_path]) == {"ProvA"}
