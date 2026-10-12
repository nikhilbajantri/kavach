"""Process-wide state behind the API: one evidence ledger, one event bus, one approval queue."""

from __future__ import annotations

import asyncio
import math
import statistics
import uuid
from typing import Any

from agent.llm.scripted import load_plan
from agent.runner import RunOutcome, Runtime, build_runtime, run_scenario
from kavach.api.events import EventBus
from kavach.approvals import ApprovalQueue
from kavach.config import settings
from kavach.ledger.chain import EvidenceLedger

LANES = {"off": False, "on": True}


class AppState:
    def __init__(self, ledger_path: str | None = None) -> None:
        path = ledger_path or str(settings.data_dir / "ledger.db")
        self.ledger = EvidenceLedger(path)
        self.bus = EventBus()
        self.approvals = ApprovalQueue()
        self.kavach_enabled = settings.enabled
        self.runs: dict[str, dict[str, Any]] = {}
        self.runtimes: dict[str, Runtime] = {}  # session_id -> runtime (provenance lookups, rug pull)
        self.last_run_id: str | None = None
        self.alerts: list[dict[str, Any]] = []
        self._tasks: set[asyncio.Task[Any]] = set()
        # A standing enforce-mode runtime for the Tool Registry page (rug-pull demo + probes).
        self.live = build_runtime(enabled=True, on_event=self._live_event, ledger=self.ledger)
        self.live.gateway.approvals = self.approvals

    def _live_event(self, kind: str, data: dict[str, Any]) -> None:
        if kind == "alert":
            self.alerts.append({"run_id": None, "lane": "live", **data})
        self.bus.publish(kind, data, lane="live")

    # ------------------------------------------------------------------ demo
    def start_demo(
        self, scenario: str = "nbfc_2am", pace: float = 0.45, lanes: tuple[str, ...] = ("off", "on")
    ) -> str:
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        self.runs[run_id] = {"run_id": run_id, "scenario": scenario, "status": "running", "lanes": {}}
        self.last_run_id = run_id
        task = asyncio.create_task(self._run_demo(run_id, scenario, pace, lanes))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return run_id

    async def _run_demo(self, run_id: str, scenario: str, pace: float, lanes: tuple[str, ...]) -> None:
        plan = load_plan(scenario)
        self.bus.publish(
            "run_started",
            {"scenario": scenario, "lanes": list(lanes), "tasks": [t.model_dump() for t in plan.tasks]},
            run_id=run_id,
        )
        try:
            results = await asyncio.gather(*(self._run_lane(run_id, plan, lane, pace) for lane in lanes))
        except Exception as exc:  # surface failures to the dashboard instead of dying silently
            self.runs[run_id]["status"] = "failed"
            self.bus.publish("run_failed", {"error": repr(exc)}, run_id=run_id)
            raise
        self.runs[run_id]["status"] = "finished"
        self.bus.publish(
            "run_finished",
            {lane: summary for lane, summary in zip(lanes, results, strict=True)},
            run_id=run_id,
        )

    async def _run_lane(self, run_id: str, plan: Any, lane: str, pace: float) -> dict[str, Any]:
        enabled = LANES[lane]

        def emit(kind: str, data: dict[str, Any]) -> None:
            if kind == "alert":
                self.alerts.append({"run_id": run_id, "lane": lane, **data})
            self.bus.publish(kind, data, run_id=run_id, lane=lane)

        runtime = build_runtime(enabled=enabled, on_event=emit, ledger=self.ledger)
        runtime.gateway.approvals = self.approvals
        outcome, rt = await run_scenario(plan, enabled=enabled, runtime=runtime, narrate=emit, pace=pace)
        self.runtimes[outcome.transcript.session_id] = rt
        summary = summarise(outcome)
        self.runs[run_id]["lanes"][lane] = summary
        return summary

    # ------------------------------------------------------------------ metrics
    def latency(self) -> dict[str, Any]:
        values = sorted(r["latency_ms"] for r in self.ledger.rows(limit=5000) if r["mode"] == "enforce")
        if not values:
            return {"count": 0, "p50_ms": None, "p95_ms": None}
        p95 = values[min(len(values) - 1, math.ceil(0.95 * len(values)) - 1)]
        return {"count": len(values), "p50_ms": round(statistics.median(values), 3), "p95_ms": round(p95, 3)}


def summarise(outcome: RunOutcome) -> dict[str, Any]:
    verdicts: dict[str, int] = {}
    for d in outcome.decisions:
        verdicts[d.verdict.value] = verdicts.get(d.verdict.value, 0) + 1
    return {
        "enabled": outcome.enabled,
        "mode": outcome.mode,
        "session_id": outcome.transcript.session_id,
        "money_to_attacker_inr": outcome.money_to_attacker_inr,
        "kyc_records_leaked": outcome.kyc_records_leaked,
        "tasks_completed": outcome.tasks_completed,
        "tasks_total": len(outcome.tasks),
        "tasks": [t.model_dump() for t in outcome.tasks],
        "verdicts": verdicts,
        "final": outcome.transcript.final,
    }
