#!/usr/bin/env bash
# Claude Code headersHelper for the Cloud Run MCP front: prints the
# Authorization header with the caller's Google ID token. Cloud Run IAM
# checks it against roles/run.invoker.
set -euo pipefail

token=$(gcloud auth print-identity-token)
printf '{"Authorization": "Bearer %s"}\n' "$token"
