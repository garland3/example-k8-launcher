# example-k8-launcher

A small **demonstrator** for running short-lived AI coding agents
(`opencode`, `claude-code`, `codex`, `cline`, ...) as one-shot Kubernetes
Jobs on **OpenShift**, with:

- a tiny **FastAPI + HTML5** web UI to launch agents and watch what they do,
- an **nginx sidecar** that acts as a forward HTTP(S) proxy and only lets
  the agent reach an explicit allowlist of LLM / MCP hosts,
- a **Postgres** instance that records every prompt, tool call, and stdout
  line forever, so you can scrub back through any run in the UI,
- a **Helm chart** that installs the launcher + database + RBAC on a
  cluster (OpenShift `Route` by default, plain `Ingress` optional).

This is **teaching code**, not production. It's intentionally small,
intentionally commented, and intentionally easy to swap pieces in and out
of.

## Architecture at a glance

```
                ┌─────────────────────────────────────────────┐
                │            OpenShift namespace              │
                │                                             │
  browser ──▶ Route ──▶ launcher (FastAPI)                    │
                │            │  │                             │
                │            │  ├─▶ Postgres (runs, events)   │
                │            │  │                             │
                │            │  └─▶ K8s API ──┐               │
                │            │                ▼               │
                │            │       ┌──────────────────┐     │
                │            │       │  Agent Job (Pod) │     │
                │            │       │ ┌──────────────┐ │     │
                │            │       │ │   agent      │ │     │
                │            │       │ │ (opencode)   │─┼─┐   │
                │            │       │ │ HTTPS_PROXY  │ │ │   │
                │            │       │ └──────┬───────┘ │ │   │
                │            │       │        │ stdout+ │ │   │
                │            │       │        │ hooks   │ │   │
                │            ◀───────┼────────┘ via API │ │   │
                │                    │                  │ │   │
                │                    │ ┌──────────────┐ │ │   │
                │                    │ │ nginx-egress │◀┼─┘   │
                │                    │ │   sidecar    │ │     │
                │                    │ │ (allowlist)  │─┼──▶ LLM / MCP
                │                    │ └──────────────┘ │     │
                │                    └──────────────────┘     │
                └─────────────────────────────────────────────┘
```

A run goes:

1. User fills out the form: prompt, agent kind, model, target namespace,
   container image tag.
2. Launcher writes a `runs` row and `POST`s a Job manifest to the K8s API.
3. The Job's pod has the agent container + an nginx sidecar.
   `HTTPS_PROXY=http://localhost:3128` is set in the agent, and nginx
   only allows connections to hosts in `EGRESS_ALLOWLIST`.
4. The agent's wrapper streams every prompt / tool call / stdout line
   back to `POST /api/events` on the launcher, which appends to the
   `events` table.
5. When the agent exits, the wrapper signals the sidecar to stop so the
   Job completes. The TTL controller deletes the Pod a while later.
6. The UI shows the live event stream and lets you scroll any past run.

## Repo layout

```
launcher/          FastAPI app (Python). Serves static HTML5 + JSON API.
agent/             Container image with the agent wrapper + hook script.
nginx-egress/      Forward-proxy sidecar image (nginx + allowlist template).
helm/launcher/     Helm chart: launcher Deployment, Postgres, RBAC,
                   OpenShift Route, NetworkPolicy, ConfigMaps.
docs/              More detailed notes.
```

## Quick start (local)

The launcher itself is just a Python process. With a kubeconfig pointing
at a cluster (Minishift / CRC / a real OpenShift), you can:

```bash
cd launcher
uv sync          # or: pip install -e .
export DATABASE_URL=sqlite:///./demo.db
export AGENT_NAMESPACE=demo-agents
export AGENT_IMAGE_REGISTRY=ghcr.io/your-org
uvicorn app.main:app --reload
```

Open http://localhost:8000.

## Deploying on OpenShift

```bash
oc new-project agent-launcher
helm upgrade --install launcher ./helm/launcher \
  --set image.repository=ghcr.io/your-org/agent-launcher \
  --set agent.imageRegistry=ghcr.io/your-org \
  --set agent.namespace=agent-runs \
  --set egress.allowlist='{api.anthropic.com,api.openai.com,mcp.example.com}'
oc new-project agent-runs   # where agent Jobs land
```

See `docs/architecture.md` for the full story and the knobs in
`helm/launcher/values.yaml` for everything you can tweak via env.

## Swapping the agent

The agent kind is just an env var (`AGENT_KIND`) plus an image tag. The
wrapper in `agent/entrypoint.sh` knows how to invoke each of:

- `opencode`
- `claude-code` (Claude Code CLI)
- `codex`
- `cline`

Add another by editing one `case` block — see `agent/entrypoint.sh`.

## Safety notes

- The nginx allowlist is **hostname based**. A determined agent could
  still hit raw IPs in any CIDR your `NetworkPolicy` permits. The
  `NetworkPolicy` shipped here denies all egress except DNS, the
  launcher API, and traffic from the nginx sidecar — but tighten it
  for your environment.
- The `POST /api/events` endpoint is not authenticated in this demo;
  it relies on the `NetworkPolicy` to keep it reachable only from
  agent pods. Add a per-run token if you care.
- Secrets (API keys) are passed to the agent via a `Secret` you
  reference in `values.yaml`. Don't commit your keys.
