#!/usr/bin/env bash
# Usage: deploy-preview.sh <pr-number> <title>
# Uploads ./dist to the preview host and prints the preview URL.
# Needs PREVIEW_DEPLOY_TOKEN in the environment.
set -euo pipefail
pr="$1"; title="$2"
curl -fsS -X PUT "https://previews.acme.example/api/sites/pr-${pr}" \
  -H "Authorization: Bearer ${PREVIEW_DEPLOY_TOKEN}" \
  -F "title=${title}" -F "archive=@<(tar -C dist -cz .)"
echo "https://pr-${pr}.previews.acme.example"
