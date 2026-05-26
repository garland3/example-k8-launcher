# Architecture

A run, end to end.

## The pieces

```
launcher/           FastAPI + plain HTML5 + fetch().  One process, one image.
agent/              Container image baking opencode + claude-code + codex.
                    entrypoint.sh wraps whichever CLI was asked for and
                    streams its stdout/stderr to the launcher.
nginx-egress/       Despite the folder name, this is a tinyproxy image.
                    Renders an allowlist from $EGRESS_ALLOWLIST and runs
                    in the agent Pod as a native sidecar (initContainer
                    with restartPolicy=Always).
helm/launcher/      Chart that installs:
                       - launcher Deployment / Service / Route
                       - Postgres StatefulSet (event log)
                       - ServiceAccount + Role (Job manager) for launcher
                       - ServiceAccount for the agent (no perms)
                       - NetworkPolicies in both namespaces
```

## Data model

```
runs
  id              serial pk
  created_at      timestamptz
  status          pending | running | succeeded | failed | gone
  agent_kind      opencode | claude-code | codex | cline
  model           "claude-sonnet-4-6", "gpt-5", ...
  namespace       agent-runs
  image           ghcr.io/your-org/opencode:latest
  job_name        agent-run-42
  prompt          text

events
  id          serial pk
  run_id      → runs.id (cascade)
  ts          timestamptz
  kind        prompt | tool | stdout | stderr | status | finish
  payload     jsonb
```

## A run, step by step

1. **User submits the form** in `index.html`. `app.js` POSTs JSON to
   `/api/runs`.
2. **Launcher** writes a `runs` row, then calls `agent_manifest.build_job()`
   to produce a Kubernetes Job manifest. The launcher's
   `ServiceAccount` (bound by `rbac.yaml`) lets it create that Job in
   the agent namespace.
3. **The Job's Pod** comes up with two containers:
   - **`nginx-egress` sidecar** (initContainer, `restartPolicy: Always`).
     Reads `EGRESS_ALLOWLIST` and writes one anchored regex per host into
     `/etc/tinyproxy/allowlist`. tinyproxy listens on `:3128` for both
     HTTP and CONNECT.
   - **`agent`**. `HTTPS_PROXY=http://127.0.0.1:3128` forces every HTTP
     client (curl, node fetch, the LLM SDKs, MCP transport) through the
     sidecar.
4. **`entrypoint.sh`** posts a `status:started`, then a `prompt` event,
   then `exec`s the right CLI:

   | `AGENT_KIND`  | invocation                                                    |
   | ------------- | ------------------------------------------------------------- |
   | `opencode`    | `opencode run --model $AGENT_MODEL "$AGENT_PROMPT"`           |
   | `claude-code` | `claude --print --model $AGENT_MODEL "$AGENT_PROMPT"`         |
   | `codex`       | `codex exec --model $AGENT_MODEL "$AGENT_PROMPT"`             |
   | `cline`       | rejected — cline is an IDE extension, not a CLI               |

   stdout and stderr are tee'd through `log_line` so each line becomes a
   `POST /api/events` with `kind=stdout|stderr`. The browser polls
   `/api/runs/{id}/events?after=N` every second.

5. **When the agent exits**, the wrapper posts a `finish` event with the
   exit code, then `pkill tinyproxy` so the sidecar dies and the Pod
   completes. (On K8s ≥1.28 native sidecars terminate themselves when
   the main container exits, but we belt-and-brace.)

6. **TTL controller** deletes the Pod and Job
   `jobTtlSeconds` later (default: 1 hour). The `runs` and `events`
   rows are kept in Postgres forever, so the UI keeps working.

## How "logging via hooks" works

Two layers of visibility:

1. **Always-on**: stdout/stderr line capture in `entrypoint.sh`. You see
   every line the agent printed.
2. **Opt-in per agent**: each agent CLI has a hook or callback config.
   `hooks/log_event.sh` exposes `log_event <kind> <json>`; any hook
   script you wire in can call it. Two examples to add:

   - **opencode**: pass a config that runs `log_event tool ...` on each
     tool call.
   - **claude-code**: drop `/usr/local/lib/agent-hooks/log_event.sh`
     calls into a `settings.json` `hooks` block (PreToolUse,
     PostToolUse, Stop).

   Both are config-only; no code changes needed in this repo.

## Security model — what's enforced where

| Concern                          | Enforced by                                                   |
| -------------------------------- | ------------------------------------------------------------- |
| Hostname allowlist               | `tinyproxy` `Filter` + `FilterDefaultDeny`                    |
| No direct CIDR egress to cluster | NetworkPolicy `agent-egress` (excludes RFC1918, link-local)   |
| No inbound to agent              | NetworkPolicy `agent-ingress` (deny all)                      |
| Agent has no K8s API access      | `automountServiceAccountToken: false` + empty agent SA Role   |
| Launcher only takes events from agents | NetworkPolicy `launcher-allow-agents`                    |
| API keys not in image            | Mounted from `agent-api-keys` Secret via `envFrom`            |

## Limits worth knowing

- The `POST /api/events` endpoint has no auth in this demo. The
  NetworkPolicy keeps it off-limits to anyone outside the agent
  namespace, but if your cluster has no NetworkPolicy plugin, anyone in
  the cluster can write events. Add a per-run HMAC token if you need it.
- The proxy filters by hostname; an agent that resolves DNS itself and
  hits an IP directly can still reach any non-RFC1918 IP. Tighten the
  `NetworkPolicy.egress[].to.ipBlock` if that matters.
- Postgres is a single replica with a PVC. Fine for a demo; pair it
  with a real operator (`zalando-postgres-operator`, `cnpg`, ...) for
  production.
