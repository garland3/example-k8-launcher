#!/usr/bin/env bash
# Helpers used by entrypoint.sh and by any agent hook script to push an
# event back to the launcher's POST /api/events endpoint.
#
# Usage:
#   source /usr/local/lib/agent-hooks/log_event.sh
#   log_event tool '{"name":"Read","args":{"path":"x"}}'
#   log_line stdout "some line"

# Don't proxy callbacks to the launcher. NO_PROXY is set by the manifest,
# but be explicit in case curl is built without that support.
_curl() {
  curl --silent --show-error --noproxy '*' \
    --max-time 5 \
    -H 'content-type: application/json' \
    "$@"
}

log_event() {
  local kind="$1"
  local payload="${2:-{}}"
  local body
  body=$(jq -nc \
    --argjson rid "${RUN_ID}" \
    --arg kind "$kind" \
    --argjson payload "$payload" \
    '{run_id:$rid, kind:$kind, payload:$payload}')
  _curl -X POST "${LAUNCHER_URL}/api/events" -d "$body" >/dev/null || true
}

log_line() {
  local kind="$1"
  local line="$2"
  local body
  body=$(jq -nc \
    --argjson rid "${RUN_ID}" \
    --arg kind "$kind" \
    --arg line "$line" \
    '{run_id:$rid, kind:$kind, payload:{line:$line}}')
  _curl -X POST "${LAUNCHER_URL}/api/events" -d "$body" >/dev/null || true
}

export -f log_event log_line _curl
