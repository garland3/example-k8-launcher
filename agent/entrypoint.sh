#!/usr/bin/env bash
# Wrapper around whichever agent CLI was requested.
#
# Responsibilities:
#   1. Tell the launcher we've started.
#   2. Run the agent with the user's prompt.
#   3. Tee stdout/stderr line-by-line to POST /api/events.
#   4. Tell the launcher we've finished (with status + exit code).
#   5. Stop the nginx-egress sidecar so the Pod can complete.
#
# Required env (set by the launcher's Job manifest):
#   RUN_ID, AGENT_KIND, AGENT_MODEL, AGENT_PROMPT, LAUNCHER_URL
#   HTTP(S)_PROXY        - point at the in-pod nginx
#   *_API_KEY            - from the agent-api-keys Secret
set -uo pipefail

: "${RUN_ID:?RUN_ID required}"
: "${AGENT_KIND:?AGENT_KIND required}"
: "${AGENT_PROMPT:?AGENT_PROMPT required}"
: "${LAUNCHER_URL:?LAUNCHER_URL required}"

# shellcheck source=hooks/log_event.sh
source /usr/local/lib/agent-hooks/log_event.sh

log_event status '{"state":"started","kind":"'"${AGENT_KIND}"'","model":"'"${AGENT_MODEL:-}"'"}'
log_event prompt "$(jq -nc --arg p "$AGENT_PROMPT" '{prompt:$p}')"

# Pipe both stdout and stderr through line-by-line loggers.
run_agent() {
  case "$AGENT_KIND" in
    opencode)
      opencode run --model "${AGENT_MODEL:-}" "$AGENT_PROMPT"
      ;;
    claude-code)
      # --print runs non-interactively and exits.
      claude --print --model "${AGENT_MODEL:-}" "$AGENT_PROMPT"
      ;;
    codex)
      codex exec --model "${AGENT_MODEL:-}" "$AGENT_PROMPT"
      ;;
    cline)
      echo "cline is a VS Code extension; no CLI mode supported in this demo" >&2
      return 64
      ;;
    *)
      echo "unknown AGENT_KIND: $AGENT_KIND" >&2
      return 64
      ;;
  esac
}

# Run agent, streaming both streams as separate event kinds.
# Using process substitution so each line is logged as it appears.
run_agent \
  > >(while IFS= read -r line; do log_line stdout "$line"; done) \
  2> >(while IFS= read -r line; do log_line stderr "$line"; done)
rc=$?

if [[ $rc -eq 0 ]]; then
  log_event finish '{"status":"succeeded","exit_code":0}'
else
  log_event finish "$(jq -nc --argjson rc "$rc" '{status:"failed",exit_code:$rc}')"
fi

# Native sidecars (K8s 1.28+) terminate automatically when the main
# container exits, but we ask nicely anyway in case we're on an older
# cluster with shareProcessNamespace=true.
pkill -TERM tinyproxy 2>/dev/null || true

exit "$rc"
