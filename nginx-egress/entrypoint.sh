#!/usr/bin/env bash
# Render the allowlist file from $EGRESS_ALLOWLIST (comma-separated)
# and exec tinyproxy in the foreground.
set -euo pipefail

: "${EGRESS_ALLOWLIST:?EGRESS_ALLOWLIST required (comma-separated hostnames)}"

cp /etc/tinyproxy/tinyproxy.conf.template /etc/tinyproxy/tinyproxy.conf

# Build the allowlist file (one host per line, anchored regex).
: > /etc/tinyproxy/allowlist
IFS=',' read -r -a hosts <<< "$EGRESS_ALLOWLIST"
for h in "${hosts[@]}"; do
  h=$(echo "$h" | tr -d '[:space:]')
  [[ -z "$h" ]] && continue
  # Anchor + escape dots so "api.openai.com" doesn't also match "apixopenai.com".
  echo "^$(echo "$h" | sed 's/\./\\./g')\$" >> /etc/tinyproxy/allowlist
done

echo "[egress] allowed hosts:" >&2
cat /etc/tinyproxy/allowlist >&2

exec tinyproxy -d -c /etc/tinyproxy/tinyproxy.conf
