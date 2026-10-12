"""ScriptedLLM: replays a recorded tool-call plan so the demo is deterministic and offline.

A plan is the transcript a naive LLM produces for the scenario, *including* the
hijacked calls the injected email causes. Later arguments can reference earlier
results with `${step_id.path|filter}` so the plan adapts to real upstream data.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from agent.llm.base import AssistantTurn, Message, ToolCall

PLANS_DIR = Path(__file__).resolve().parents[1] / "plans"
_TEMPLATE = re.compile(r"\$\{([a-zA-Z0-9_]+)((?:\.[a-zA-Z0-9_\[\]]+)*)(?:\|([a-z_]+))?\}")


class PlanStep(BaseModel):
    id: str
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    say: str = ""


class TaskSpec(BaseModel):
    """A legitimate ticket and the observable effects that prove it was completed."""

    id: str
    label: str
    checks: list[dict[str, dict[str, Any]]] = Field(default_factory=list)


class Attacker(BaseModel):
    upis: list[str] = Field(default_factory=list)
    accounts: list[str] = Field(default_factory=list)
    emails: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    id: str
    description: str = ""
    steps: list[PlanStep]
    final: str = "Done."
    attacker: Attacker = Field(default_factory=Attacker)
    tasks: list[TaskSpec] = Field(default_factory=list)


def load_plan(name_or_path: str | Path) -> Plan:
    path = Path(name_or_path)
    if not path.exists():
        path = PLANS_DIR / f"{name_or_path}.yaml"
    return Plan.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def _walk(value: Any, path: str) -> Any:
    for part in re.findall(r"[a-zA-Z0-9_]+|\[\d+\]", path):
        if value is None:
            return None
        if part.startswith("["):
            idx = int(part[1:-1])
            value = value[idx] if isinstance(value, list) and idx < len(value) else None
        else:
            value = value.get(part) if isinstance(value, dict) else None
    return value


def _inr(n: int) -> str:
    s = str(int(n))
    if len(s) <= 3:
        return f"₹{s}"
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return "₹" + ",".join([*groups, tail])


def _kyc_table(customers: list[dict[str, Any]]) -> str:
    lines = ["name | phone | PAN | Aadhaar | address"]
    lines += [
        f"{c['name']} | {c['phone']} | {c['pan']} | XXXX-XXXX-{c['aadhaar_last4']} | {c['address']}"
        for c in customers or []
    ]
    return "\n".join(lines)


def _statement(orders: list[dict[str, Any]]) -> str:
    return "\n".join(
        f"{o['date']}  {o['order_id']}  {o['item']}  {_inr(o['amount_inr'])}  {o['status']}"
        for o in orders or []
    )


FILTERS = {
    "json": lambda v: json.dumps(v, ensure_ascii=False),
    "kyc_table": _kyc_table,
    "statement": _statement,
    "inr": _inr,
}


def render(value: Any, results: dict[str, Any]) -> Any:
    """Resolve templates. A string that is exactly one template keeps the raw type (e.g. int)."""
    if isinstance(value, dict):
        return {k: render(v, results) for k, v in value.items()}
    if isinstance(value, list):
        return [render(v, results) for v in value]
    if not isinstance(value, str):
        return value

    def resolve(match: re.Match[str]) -> Any:
        raw = _walk(results.get(match.group(1)), match.group(2) or "")
        return FILTERS[match.group(3)](raw) if match.group(3) else raw

    full = _TEMPLATE.fullmatch(value)
    if full:
        return resolve(full)
    return _TEMPLATE.sub(lambda m: "" if (v := resolve(m)) is None else str(v), value)


class ScriptedLLM:
    mode = "scripted"

    def __init__(self, plan: Plan) -> None:
        self.plan = plan

    async def step(self, history: list[Message], tools: list[dict[str, Any]]) -> AssistantTurn:
        results: dict[str, Any] = {}
        for msg in history:
            if msg.role == "tool" and msg.tool_call_id:
                try:
                    results[msg.tool_call_id] = json.loads(msg.content)
                except json.JSONDecodeError:
                    results[msg.tool_call_id] = msg.content
        done = sum(len(m.tool_calls) for m in history if m.role == "assistant")
        if done >= len(self.plan.steps):
            return AssistantTurn(text=self.plan.final)
        step = self.plan.steps[done]
        call = ToolCall(id=step.id, name=step.tool, args=render(step.args, results))
        return AssistantTurn(text=step.say, tool_calls=[call])
