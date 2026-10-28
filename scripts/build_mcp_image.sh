#!/usr/bin/env bash
# Build the MCP front image with Cloud Build and push it to Artifact Registry.
# Usage: scripts/build_mcp_image.sh PROJECT_ID REGION TAG
set -euo pipefail

if [ "$#" -ne 3 ]; then
  echo "usage: $0 PROJECT_ID REGION TAG" >&2
  exit 2
fi
project_id=$1
region=$2
tag=$3
image="${region}-docker.pkg.dev/${project_id}/meeting-briefing/mcp-front:${tag}"

cd "$(dirname "$0")/.."
gcloud builds submit --project "$project_id" --region "$region" --tag "$image" .
echo "$image"
