"""Benchmark case format: a scripted agent transcript plus the world it runs in.

Attack cases replay what a *successfully hijacked* agent would do. This is the
worst case for KAVACH: the LLM is assumed fully compromised, so the only thing
standing between the attacker and the bank is the gateway.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

from agent.llm.scripted import Plan
from mocks.email.inbox import InboundEmail, default_inbox

BENCH_DIR = Path(__file__).resolve().parent


class EmailSpec(BaseModel):
    id: str
    from_addr: str = Field(alias="from")
    from_name: str = ""
    subject: str = ""
    body: str = ""  # plain text; wrapped in <p>
    hidden_html: str = ""  # appended verbatim (white-on-white spans, comments...)
    received_at: str = "2026-10-12T02:00:00+05:30"

    def to_inbound(self) -> InboundEmail:
        paragraphs = "".join(f"<p>{line}</p>" for line in self.body.split("\n") if line.strip())
        return InboundEmail(
            id=self.id,
            from_addr=self.from_addr,
            from_name=self.from_name or self.from_addr.split("@")[0],
            subject=self.subject,
            received_at=self.received_at,
            body_html=paragraphs + self.hidden_html,
        )


class BenchCase(Plan):
    kind: Literal["attack", "benign"]
    category: str
    inbox: list[EmailSpec] | Literal["default"] = "default"
    rug_pull: bool = False

    def inbound(self) -> list[InboundEmail]:
        return default_inbox() if self.inbox == "default" else [e.to_inbound() for e in self.inbox]


def load_cases(kind: str) -> list[BenchCase]:
    folder = BENCH_DIR / ("attacks" if kind == "attack" else "benign")
    cases: list[BenchCase] = []
    for path in sorted(folder.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        for item in raw if isinstance(raw, list) else [raw]:
            cases.append(BenchCase.model_validate({"kind": kind, **item}))
    return cases
