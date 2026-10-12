"""FastAPI entrypoint: dashboard API, SSE stream, evidence ledger and approvals."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel

from agent.prompts import OPERATOR_PROMPT, SYSTEM_PROMPT
from kavach import __version__
from kavach.api.state import AppState
from kavach.ledger.export import export_json, export_markdown
from kavach.ledger.mask import mask
from kavach.models import Sensitivity
from mocks.email.inbox import default_inbox, hidden_text, visible_text
from mocks.tools import list_manifests, rug_pull


class DemoRequest(BaseModel):
    scenario: str = "nbfc_2am"
    pace: float = 0.45
    lanes: list[str] = ["off", "on"]
    provider: str | None = None  # defaults to LLM_PROVIDER (scripted)


class Settings(BaseModel):
    kavach_enabled: bool


class RugPull(BaseModel):
    enabled: bool = True


class Resolution(BaseModel):
    reviewer: str = "operator@ourbank.in"


def create_app(ledger_path: str | None = None) -> FastAPI:
    """Build the app. A factory keeps tests isolated from each other."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.kavach = AppState(ledger_path)
        yield

    app = FastAPI(title="KAVACH Gateway", version=__version__, lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    def st(request: Request) -> AppState:
        return request.app.state.kavach

    @app.get("/health")
    def health(request: Request) -> dict[str, object]:
        return {"status": "ok", "version": __version__, "kavach_enabled": st(request).kavach_enabled}

    # ---------------------------------------------------------------- settings
    @app.get("/settings")
    def get_settings(request: Request) -> dict[str, Any]:
        return {"kavach_enabled": st(request).kavach_enabled}

    @app.post("/settings")
    def set_settings(body: Settings, request: Request) -> dict[str, Any]:
        st(request).kavach_enabled = body.kavach_enabled
        st(request).bus.publish("settings", {"kavach_enabled": body.kavach_enabled})
        return {"kavach_enabled": body.kavach_enabled}

    # ---------------------------------------------------------------- demo + events
    @app.post("/demo/run")
    async def run_demo(body: DemoRequest, request: Request) -> dict[str, str]:
        lanes = tuple(lane for lane in body.lanes if lane in {"off", "on"}) or ("off", "on")
        return {
            "run_id": st(request).start_demo(
                body.scenario, max(0.0, min(body.pace, 3.0)), lanes, body.provider
            )
        }

    @app.get("/demo/runs/{run_id}")
    def get_run(run_id: str, request: Request) -> dict[str, Any]:
        run = st(request).runs.get(run_id)
        if run is None:
            raise HTTPException(404, "unknown run")
        return run

    @app.get("/demo/last")
    def last_run(request: Request) -> dict[str, Any]:
        state = st(request)
        if not state.last_run_id:
            return {"run": None, "events": []}
        events = [e for e in state.bus.history() if e.get("run_id") == state.last_run_id]
        return {"run": state.runs[state.last_run_id], "events": events}

    @app.get("/events")
    async def events(request: Request, since: int = 0) -> StreamingResponse:
        last_id = request.headers.get("last-event-id")
        start = int(last_id) if last_id and last_id.isdigit() else since
        return StreamingResponse(
            st(request).bus.stream(since=start),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/provenance/{session_id}/{entry_id}")
    def provenance(session_id: str, entry_id: str, request: Request) -> dict[str, Any]:
        runtime = st(request).runtimes.get(session_id)
        session = runtime.gateway.sessions.get(session_id) if runtime else None
        entry = session.store.get(entry_id) if session else None
        if entry is None:
            raise HTTPException(404, "unknown ledger entry")
        data = entry.model_dump(mode="json")
        if entry.sensitivity is Sensitivity.REGULATED_PII:
            data["text"] = mask(entry.text)
        return data

    @app.get("/inbox")
    def inbox() -> list[dict[str, Any]]:
        """The demo inbox as a human sees it, plus what is hidden from human eyes."""
        return [
            {
                "id": m.id,
                "from": m.from_addr,
                "from_name": m.from_name,
                "subject": m.subject,
                "received_at": m.received_at,
                "visible": visible_text(m.body_html),
                "hidden": hidden_text(m.body_html),
            }
            for m in default_inbox()
        ]

    # ---------------------------------------------------------------- approvals
    @app.get("/approvals")
    def approvals(request: Request) -> list[dict[str, Any]]:
        return [mask(a.public()) for a in st(request).approvals.all()]

    @app.post("/approvals/{approval_id}/{action}")
    async def resolve(approval_id: str, action: str, body: Resolution, request: Request) -> dict[str, Any]:
        if action not in {"approve", "reject"}:
            raise HTTPException(400, "action must be approve or reject")
        approval = st(request).approvals.get(approval_id)
        if approval is None or approval.status != "pending" or approval.executor is None:
            raise HTTPException(404, "no pending approval with that id")
        result = await approval.executor.resolve_approval(approval_id, action == "approve", body.reviewer)
        return mask(result)

    # ---------------------------------------------------------------- ledger
    @app.get("/ledger")
    def ledger(request: Request, session: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        return st(request).ledger.rows(session_id=session, limit=min(limit, 2000))

    @app.get("/ledger/verify")
    def verify(request: Request) -> dict[str, Any]:
        return st(request).ledger.verify()

    @app.get("/ledger/sessions")
    def sessions(request: Request) -> list[str]:
        return st(request).ledger.sessions()

    @app.get("/ledger/export", response_model=None)
    def export(request: Request, session: str, format: str = "md") -> PlainTextResponse | dict[str, Any]:
        state = st(request)
        if session not in state.ledger.sessions():
            raise HTTPException(404, "unknown session")
        if format == "json":
            return export_json(state.ledger, session)
        return PlainTextResponse(
            export_markdown(state.ledger, session),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="kavach-evidence-{session}.md"'},
        )

    # ---------------------------------------------------------------- tool registry (L3)
    @app.get("/registry/tools")
    def registry_tools(request: Request) -> dict[str, Any]:
        live = st(request).live
        assert live.gateway.registry is not None
        return {
            "rug_pulled": "email.send" in live.world.tool_description_overrides,
            "tools": live.gateway.registry.snapshot(),
            "alerts": live.gateway.registry.alerts[-50:],
        }

    @app.post("/registry/rugpull")
    async def registry_rugpull(body: RugPull, request: Request) -> dict[str, Any]:
        """Demo switch: the upstream email server silently rewrites email.send's description."""
        live = st(request).live
        rug_pull(live.world, body.enabled)
        alerts = await live.gateway.refresh_tools()
        return {"rug_pulled": body.enabled, "new_alerts": alerts}

    @app.post("/registry/approve")
    async def registry_approve(request: Request) -> dict[str, Any]:
        """Operator reviewed the upstream and re-pins it as it is now (also lifts quarantine)."""
        live = st(request).live
        assert live.gateway.registry is not None
        rug_pull(live.world, False)
        live.gateway.registry.approve_current(list_manifests(live.world))
        live.gateway.quarantined = live.gateway.registry.quarantined()
        return {"ok": True}

    @app.post("/registry/probe")
    async def registry_probe(request: Request) -> dict[str, Any]:
        """Have the agent try an ordinary customer reply through the (possibly rug-pulled) tool."""
        live = st(request).live
        session = live.gateway.open_session(OPERATOR_PROMPT, SYSTEM_PROMPT)
        await live.gateway.call(session, "crm.get_customer", {"email": "ravi.kumar@gmail.com"})
        outcome = await live.gateway.call(
            session,
            "email.send",
            {
                "to": "ravi.kumar@gmail.com",
                "subject": "Re: your ticket",
                "body": "Your refund is on its way.",
            },
        )
        st(request).runtimes[session.session_id] = live
        return mask(outcome.decision.model_dump(mode="json"))

    @app.get("/bench/results")
    def bench_results() -> dict[str, Any]:
        """Latest `make bench` output (bench/results.json)."""
        from bench.runner import RESULTS_JSON

        if not RESULTS_JSON.exists():
            raise HTTPException(404, "no benchmark results yet; run `make bench`")
        return json.loads(RESULTS_JSON.read_text(encoding="utf-8"))

    @app.get("/metrics/latency")
    def latency(request: Request) -> dict[str, Any]:
        return st(request).latency()

    @app.get("/alerts")
    def alerts(request: Request) -> list[dict[str, Any]]:
        return mask(st(request).alerts[-100:])

    return app


app = create_app()
