#!/bin/bash
set -e
# Ensure Mixer loads the feature flags config
if ! grep -q "feature_flags_path" /workspace/run.sh; then
  sed -i 's|"${MIXER_ARGS\[@\]}"|"${MIXER_ARGS[@]}" --feature_flags_path=/workspace/deploy/featureflags/custom.yaml|g' /workspace/run.sh
fi
exec /workspace/run.sh
