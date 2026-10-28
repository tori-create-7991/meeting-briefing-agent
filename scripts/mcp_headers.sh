#!/usr/bin/env bash
# Claude Code headersHelper for the Cloud Run MCP front (mcp-front).
#
# Prints one JSON object of request headers: the Authorization header with a
# Google ID token, which Cloud Run IAM checks against roles/run.invoker.
# Claude Code runs this on connect and on reconnect, does not cache the
# result, and runs it again after a 401/403 (the token expires after an
# hour), so nothing here needs to cache or refresh. It must finish within
# 10 seconds.
#
# Register it by absolute path, in user scope (see docs/deploy.md):
#   mcp_headers.sh [--account EMAIL] [--impersonate SA_EMAIL] [--gcloud PATH]
#
#   --account      gcloud account whose token is sent. It must be listed in
#                  invoker_members. Default: the active gcloud account.
#   --impersonate  send a token for this service account instead, with the
#                  MCP server's origin (from CLAUDE_CODE_MCP_SERVER_URL) as
#                  the audience. Needs roles/iam.serviceAccountTokenCreator
#                  on that service account.
#   --gcloud       gcloud binary. Default: PATH, then common install
#                  locations, since helpers may run without the login
#                  shell's PATH (mise, Homebrew).
#
# gcloud also needs Python 3.10+. Unless CLOUDSDK_PYTHON is set, a suitable
# python3 is looked up the same way, because the system python3 on macOS is
# too old for current gcloud.
set -euo pipefail

account=""
impersonate=""
gcloud_bin=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --account) account=${2:?--account needs an email}; shift 2 ;;
    --impersonate) impersonate=${2:?--impersonate needs a service account email}; shift 2 ;;
    --gcloud) gcloud_bin=${2:?--gcloud needs a path}; shift 2 ;;
    *) echo "mcp_headers.sh: unknown argument: $1" >&2; exit 2 ;;
  esac
done

find_gcloud() {
  if command -v gcloud >/dev/null 2>&1; then
    command -v gcloud
    return
  fi
  local found=""
  for candidate in \
    "$HOME"/.local/share/mise/installs/gcloud/*/bin/gcloud \
    /opt/homebrew/bin/gcloud \
    /usr/local/bin/gcloud \
    "$HOME"/google-cloud-sdk/bin/gcloud; do
    # The mise glob sorts by version name; keep the last match.
    if [ -x "$candidate" ]; then found=$candidate; fi
  done
  if [ -z "$found" ]; then
    echo "mcp_headers.sh: gcloud not found; pass --gcloud /path/to/gcloud" >&2
    return 1
  fi
  echo "$found"
}

supports_gcloud() {
  "$1" -c 'import sys; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1
}

find_python() {
  if command -v python3 >/dev/null 2>&1 && supports_gcloud "$(command -v python3)"; then
    command -v python3
    return
  fi
  local found=""
  for candidate in \
    "$HOME"/.local/share/mise/installs/python/*/bin/python3 \
    /opt/homebrew/bin/python3 \
    /usr/local/bin/python3; do
    if [ -x "$candidate" ] && supports_gcloud "$candidate"; then found=$candidate; fi
  done
  # Nothing suitable: leave it to gcloud's own lookup and error message.
  [ -n "$found" ] && echo "$found"
  return 0
}

if [ -z "$gcloud_bin" ]; then
  gcloud_bin=$(find_gcloud)
fi
if [ -z "${CLOUDSDK_PYTHON:-}" ]; then
  python_bin=$(find_python)
  if [ -n "$python_bin" ]; then
    export CLOUDSDK_PYTHON=$python_bin
  fi
fi

args=(auth print-identity-token)
if [ -n "$account" ]; then
  args+=(--account "$account")
fi
if [ -n "$impersonate" ]; then
  url=${CLAUDE_CODE_MCP_SERVER_URL:?CLAUDE_CODE_MCP_SERVER_URL is not set; --impersonate only works as a headersHelper}
  audience=$(printf '%s' "$url" | sed -E 's#^(https?://[^/]+).*#\1#')
  args+=(--impersonate-service-account "$impersonate" --audiences "$audience")
fi

token=$("$gcloud_bin" "${args[@]}")
if [ -z "$token" ]; then
  echo "mcp_headers.sh: gcloud returned an empty token" >&2
  exit 1
fi
printf '{"Authorization": "Bearer %s"}\n' "$token"
