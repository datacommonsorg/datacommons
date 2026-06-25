#!/bin/bash
# Copyright 2026 Google LLC
# Script to wait for local emulators and perform initial GCS seeding.

set -e

echo "Waiting for GCS Emulator (port 9099) to start..."
count=0
until curl -s http://localhost:9099/ > /dev/null || [ $count -eq 60 ]; do
  sleep 0.5
  count=$((count + 1))
done

if [ $count -eq 60 ]; then
  echo "ERROR: GCS Emulator failed to start on port 9099."
  exit 1
fi


echo "Seeding GCS emulator bucket and dummy catalog..."
curl -s -X POST "http://localhost:9099/storage/v1/b?project=test-project" \
  -H "Content-Type: application/json" \
  -d '{"name": "test-bucket"}' > /dev/null

curl -s -X POST "http://localhost:9099/upload/storage/v1/b/test-bucket/o?uploadType=media&name=output/datacommons/nl/embeddings/custom_catalog.yaml" \
  -H "Content-Type: application/x-yaml" \
  -d "version: '1'
models: {}
indexes: {}" > /dev/null


echo "Emulators initialized successfully."
