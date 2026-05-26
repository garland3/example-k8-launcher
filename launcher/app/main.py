from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .agent_manifest import build_job
from .db import get_session, init_db
from .k8s import create_job, get_job_status
from .models import Event, Run
from .settings import settings

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="agent-launcher", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ---------------------------------------------------------------------------
# Static HTML5 pages (no template engine — plain files + fetch())
# ---------------------------------------------------------------------------


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/runs/{run_id}", include_in_schema=False)
async def run_page(run_id: int) -> FileResponse:  # noqa: ARG001 - rendered client-side
    return FileResponse(STATIC_DIR / "run.html")


# ---------------------------------------------------------------------------
# API: launch + list + inspect runs
# ---------------------------------------------------------------------------


class LaunchRequest(BaseModel):
    agent_kind: str = Field("opencode", description="opencode|claude-code|codex|cline")
    model: str = Field("claude-sonnet-4-6")
    prompt: str
    namespace: str | None = None
    image: str | None = None


class LaunchResponse(BaseModel):
    run_id: int
    job_name: str


@app.post("/api/runs", response_model=LaunchResponse)
async def launch_run(
    body: LaunchRequest, session: AsyncSession = Depends(get_session)
) -> LaunchResponse:
    namespace = body.namespace or settings.agent_namespace
    image = body.image or (
        f"{settings.agent_image_registry}/{body.agent_kind}:{settings.agent_image_tag}"
    )

    run = Run(
        status="pending",
        agent_kind=body.agent_kind,
        model=body.model,
        namespace=namespace,
        image=image,
        prompt=body.prompt,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    manifest = build_job(
        run_id=run.id,
        agent_kind=body.agent_kind,
        model=body.model,
        image=image,
        prompt=body.prompt,
        namespace=namespace,
    )

    try:
        job_name = create_job(namespace, manifest)
    except Exception as exc:  # surface k8s errors to the UI
        run.status = "failed"
        session.add(Event(run_id=run.id, kind="status", payload={"error": str(exc)}))
        await session.commit()
        raise HTTPException(status_code=500, detail=f"failed to create Job: {exc}") from exc

    run.job_name = job_name
    run.status = "running"
    session.add(Event(run_id=run.id, kind="status", payload={"job": job_name, "state": "created"}))
    await session.commit()
    return LaunchResponse(run_id=run.id, job_name=job_name)


@app.get("/api/runs")
async def list_runs(session: AsyncSession = Depends(get_session)) -> list[dict[str, Any]]:
    rows = (await session.execute(select(Run).order_by(Run.id.desc()).limit(100))).scalars().all()
    return [
        {
            "id": r.id,
            "created_at": r.created_at.isoformat(),
            "status": r.status,
            "agent_kind": r.agent_kind,
            "model": r.model,
            "namespace": r.namespace,
            "job_name": r.job_name,
        }
        for r in rows
    ]


@app.get("/api/runs/{run_id}")
async def get_run(run_id: int, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    run = await session.get(Run, run_id)
    if not run:
        raise HTTPException(404, "run not found")
    # Refresh k8s status if it's still running.
    if run.status == "running" and run.job_name:
        try:
            live = get_job_status(run.namespace, run.job_name)
            if live in ("succeeded", "failed", "gone"):
                run.status = live
                await session.commit()
        except Exception:  # noqa: BLE001 - status refresh is best effort
            pass
    return {
        "id": run.id,
        "created_at": run.created_at.isoformat(),
        "status": run.status,
        "agent_kind": run.agent_kind,
        "model": run.model,
        "namespace": run.namespace,
        "image": run.image,
        "job_name": run.job_name,
        "prompt": run.prompt,
    }


@app.get("/api/runs/{run_id}/events")
async def list_events(
    run_id: int, after: int = 0, session: AsyncSession = Depends(get_session)
) -> list[dict[str, Any]]:
    q = select(Event).where(Event.run_id == run_id, Event.id > after).order_by(Event.id)
    rows = (await session.execute(q)).scalars().all()
    return [
        {"id": e.id, "ts": e.ts.isoformat(), "kind": e.kind, "payload": e.payload} for e in rows
    ]


# ---------------------------------------------------------------------------
# Internal: agent wrapper / hooks POST here.
# Reachable only from agent pods via NetworkPolicy.
# ---------------------------------------------------------------------------


class EventIn(BaseModel):
    run_id: int
    kind: str
    payload: dict[str, Any] = Field(default_factory=dict)


@app.post("/api/events")
async def post_event(body: EventIn, session: AsyncSession = Depends(get_session)) -> JSONResponse:
    run = await session.get(Run, body.run_id)
    if not run:
        raise HTTPException(404, "unknown run")
    session.add(Event(run_id=body.run_id, kind=body.kind, payload=body.payload))
    # `finish` events also flip the run's status.
    if body.kind == "finish":
        run.status = body.payload.get("status", "succeeded")
    await session.commit()
    return JSONResponse({"ok": True})


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
