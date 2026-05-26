"""Thin wrapper around the kubernetes client.

We try in-cluster config first (the launcher Pod's ServiceAccount), then
fall back to the user's local kubeconfig so the same code works for
`uvicorn --reload` on a laptop.
"""
from __future__ import annotations

from kubernetes import client, config
from kubernetes.client.exceptions import ApiException


def _load() -> None:
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()


_loaded = False


def batch_api() -> client.BatchV1Api:
    global _loaded
    if not _loaded:
        _load()
        _loaded = True
    return client.BatchV1Api()


def create_job(namespace: str, manifest: dict) -> str:
    api = batch_api()
    obj = api.create_namespaced_job(namespace=namespace, body=manifest)
    return obj.metadata.name


def get_job_status(namespace: str, name: str) -> str:
    api = batch_api()
    try:
        job = api.read_namespaced_job_status(name=name, namespace=namespace)
    except ApiException as exc:
        if exc.status == 404:
            return "gone"
        raise
    s = job.status
    if s.succeeded:
        return "succeeded"
    if s.failed:
        return "failed"
    if s.active:
        return "running"
    return "pending"
