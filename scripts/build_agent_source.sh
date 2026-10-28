#!/usr/bin/env bash
# Package the agent for Agent Runtime (python_spec / inline source).
# Output:
# - dist/agent_source.tar.gz: requirements.txt and the meeting_briefing_agent
#   package at the archive root
# - dist/class_methods.json: the callable methods Agent Runtime exposes
set -euo pipefail

cd "$(dirname "$0")/.."
out=dist/agent_source
rm -rf "$out" dist/agent_source.tar.gz dist/class_methods.json
mkdir -p "$out"

uv export --frozen --no-dev --no-hashes --no-emit-project --no-header \
  > "$out/requirements.txt"
cp -R src/meeting_briefing_agent "$out/"
find "$out" -name '__pycache__' -type d -prune -exec rm -rf {} +

COPYFILE_DISABLE=1 tar -czf dist/agent_source.tar.gz -C "$out" .
uv run --frozen python scripts/gen_class_methods.py > dist/class_methods.json
echo "wrote dist/agent_source.tar.gz and dist/class_methods.json"
