#!/usr/bin/env bash
# Package the agent for Agent Runtime (python_spec / inline source).
# Output: dist/agent_source.tar.gz with requirements.txt and the
# meeting_briefing_agent package at the archive root.
set -euo pipefail

cd "$(dirname "$0")/.."
out=dist/agent_source
rm -rf "$out" dist/agent_source.tar.gz
mkdir -p "$out"

uv export --frozen --no-dev --no-hashes --no-emit-project --no-header \
  > "$out/requirements.txt"
cp -R src/meeting_briefing_agent "$out/"
find "$out" -name '__pycache__' -type d -prune -exec rm -rf {} +

COPYFILE_DISABLE=1 tar -czf dist/agent_source.tar.gz -C "$out" .
echo "wrote dist/agent_source.tar.gz"
