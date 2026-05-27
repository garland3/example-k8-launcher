"""Builds the Kubernetes Job manifest for a single agent run.

The shape is deliberately verbose so a reader can follow it top-to-bottom:

  - one Job
  - one Pod, restartPolicy=Never
  - shareProcessNamespace=true so the agent wrapper can `kill` the sidecar
    when it's done (keeps the Job from hanging)
  - a *native sidecar* (initContainer with restartPolicy=Always, K8s 1.28+
    / OpenShift 4.14+) running nginx as a forward proxy
  - the agent container, which talks out via HTTPS_PROXY=localhost:3128
"""
from __future__ import annotations

from .settings import settings


def build_job(
    *,
    run_id: int,
    agent_kind: str,
    model: str,
    image: str,
    prompt: str,
    namespace: str,
    extra_env: dict[str, str] | None = None,
) -> dict:
    name = f"agent-run-{run_id}"
    allowlist = settings.egress_allowlist

    env = [
        {"name": "RUN_ID", "value": str(run_id)},
        {"name": "AGENT_KIND", "value": agent_kind},
        {"name": "AGENT_MODEL", "value": model},
        {"name": "AGENT_PROMPT", "value": prompt},
        {"name": "LAUNCHER_URL", "value": settings.launcher_internal_url},
        # Force every HTTP client in the agent container through nginx.
        {"name": "HTTP_PROXY", "value": "http://127.0.0.1:3128"},
        {"name": "HTTPS_PROXY", "value": "http://127.0.0.1:3128"},
        {"name": "http_proxy", "value": "http://127.0.0.1:3128"},
        {"name": "https_proxy", "value": "http://127.0.0.1:3128"},
        # Never proxy callbacks to the launcher itself.
        {"name": "NO_PROXY", "value": "127.0.0.1,localhost,.svc,.cluster.local"},
        {"name": "no_proxy", "value": "127.0.0.1,localhost,.svc,.cluster.local"},
    ]
    for k, v in (extra_env or {}).items():
        env.append({"name": k, "value": v})

    # API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, ...) come from a Secret.
    env_from = [{"secretRef": {"name": settings.agent_api_keys_secret, "optional": True}}]

    nginx_sidecar = {
        "name": "nginx-egress",
        "image": settings.nginx_image,
        "imagePullPolicy": "IfNotPresent",
        # Native sidecar: starts before the main container, stays running.
        "restartPolicy": "Always",
        "env": [{"name": "EGRESS_ALLOWLIST", "value": allowlist}],
        "ports": [{"containerPort": 3128, "name": "proxy"}],
        "readinessProbe": {
            "tcpSocket": {"port": 3128},
            "initialDelaySeconds": 1,
            "periodSeconds": 2,
        },
        "resources": {
            "requests": {"cpu": "10m", "memory": "32Mi"},
            "limits": {"cpu": "200m", "memory": "128Mi"},
        },
    }

    agent_container = {
        "name": "agent",
        "image": image,
        "imagePullPolicy": "IfNotPresent",
        "env": env,
        "envFrom": env_from,
        "resources": {
            "requests": {"cpu": "100m", "memory": "256Mi"},
            "limits": {"cpu": "2", "memory": "2Gi"},
        },
    }

    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": name,
            "labels": {
                "app.kubernetes.io/name": "agent-run",
                "agent.launcher/run-id": str(run_id),
                "agent.launcher/kind": agent_kind,
            },
        },
        "spec": {
            "backoffLimit": 0,
            "ttlSecondsAfterFinished": settings.job_ttl_seconds,
            "activeDeadlineSeconds": settings.job_active_deadline_seconds,
            "template": {
                "metadata": {
                    "labels": {
                        "app.kubernetes.io/name": "agent-run",
                        "agent.launcher/run-id": str(run_id),
                    }
                },
                "spec": {
                    "serviceAccountName": settings.agent_service_account,
                    "restartPolicy": "Never",
                    "shareProcessNamespace": True,
                    "automountServiceAccountToken": False,
                    "initContainers": [nginx_sidecar],
                    "containers": [agent_container],
                },
            },
        },
    }
