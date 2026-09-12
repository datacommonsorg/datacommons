#!/bin/bash
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Entrypoint for the preprocessor image.
#
# Ported from website/build/cdc_data/run.sh. The contract with callers (env
# vars, run modes, output layout) is deliberately unchanged so the Cloud Run job
# in infra/dcp can switch images without a config change. The only difference is
# how the importer is invoked: the package is installed into the image's venv,
# so there is no directory to cd into.

set -e

# Check for required variables.

if [[ $DC_API_KEY == "" ]]; then
  echo "DC_API_KEY not specified."
  exit 1
fi

if [[ $INPUT_DIR == "" ]]; then
    echo "INPUT_DIR not specified."
    exit 1
fi

if [[ $OUTPUT_DIR == "" ]]; then
    echo "OUTPUT_DIR not specified."
    exit 1
fi

# TODO: Once the Custom DC code paths are removed from the preprocessor, this
# should accept only "dcpbridge" and the "customdc" default should go away.
if [[ $DATA_RUN_MODE != "" ]]; then
    if [[ $DATA_RUN_MODE != "schemaupdate" && $DATA_RUN_MODE != "dcpbridge" ]]; then
      echo "DATA_RUN_MODE must be either empty, 'schemaupdate', or 'dcpbridge'"
      exit 1
    fi
    echo "DATA_RUN_MODE=$DATA_RUN_MODE"
else
  DATA_RUN_MODE="customdc"
fi

echo "INPUT_DIR=$INPUT_DIR"
echo "OUTPUT_DIR=$OUTPUT_DIR"

# Paths based off of OUTPUT_DIR.
DC_OUTPUT_DIR=$OUTPUT_DIR/datacommons

if [[ $USE_SQLITE == "true" ]]; then
    # Set SQLITE_PATH for sqlite imports.
    # This is used by the preprocessor.
    export SQLITE_PATH=$DC_OUTPUT_DIR/datacommons.db
    echo "SQLITE_PATH=$SQLITE_PATH"
fi

# Run the preprocessor.
python3 -m datacommons_preprocessor.stats.main \
    --input_dir=$INPUT_DIR \
    --output_dir=$DC_OUTPUT_DIR \
    --mode=$DATA_RUN_MODE \
    "$@"

echo "Data loading complete."
