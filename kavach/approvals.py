"""Human-in-the-loop queue for ESCALATE verdicts."""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from kavach.models import Decision

if TYPE_CHECKING:
    from kavach.gateway import Session


@dataclass
class Approval:
    id: str
    decision: Decision
    session: Session
    created_at: float = field(default_factory=time.time)
    status: str = "pending"  # pending | approved | rejected
    resolved_by: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "created_at": self.created_at,
            "resolved_by": self.resolved_by,
            "decision": self.decision.model_dump(mode="json"),
            "result": self.result,
            "error": self.error,
        }


class ApprovalQueue:
    def __init__(self) -> None:
        self._items: dict[str, Approval] = {}
        self._ids = itertools.count(1)

    def add(self, decision: Decision, session: Session) -> Approval:
        approval = Approval(id=f"apr_{next(self._ids):04d}", decision=decision, session=session)
        self._items[approval.id] = approval
        return approval

    def get(self, approval_id: str) -> Approval | None:
        return self._items.get(approval_id)

    def all(self) -> list[Approval]:
        return sorted(self._items.values(), key=lambda a: a.created_at, reverse=True)

    def pending(self) -> list[Approval]:
        return [a for a in self.all() if a.status == "pending"]
