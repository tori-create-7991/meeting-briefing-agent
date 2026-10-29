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
# Created by infra/main (build.tf): the build runs as mcp-builder and stages
# its source and logs in the build bucket.
builder="mcp-builder@${project_id}.iam.gserviceaccount.com"
bucket="gs://${project_id}-build"

cd "$(dirname "$0")/.."
gcloud builds submit --project "$project_id" --region "$region" --tag "$image" \
  --service-account "projects/${project_id}/serviceAccounts/${builder}" \
  --gcs-source-staging-dir "${bucket}/source" \
  --gcs-log-dir "${bucket}/logs" \
  .
echo "$image"
