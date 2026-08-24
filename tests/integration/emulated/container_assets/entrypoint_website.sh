#!/bin/bash
set -e
# Run the dynamic feature flags generator
python3 /workspace/generate_feature_flags.py

# Ensure Mixer loads the generated feature flags config
if ! grep -q "feature_flags_path" /workspace/run.sh; then
  sed -i 's|"${MIXER_ARGS\[@\]}"|"${MIXER_ARGS[@]}" --feature_flags_path=/workspace/deploy/featureflags/dcp.yaml|g' /workspace/run.sh
fi
exec /workspace/run.sh
