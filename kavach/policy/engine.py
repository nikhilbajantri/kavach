"""Cedar policy engine wrapper: evaluates the context and returns every matching rule.

Cedar answers permit/deny; KAVACH needs graded verdicts. Each forbid policy
carries @rule and @verdict annotations; on a deny Cedar reports the ids of all
satisfied forbids, which we map back to their annotations.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import cedarpy

from kavach.models import Verdict

POLICY_DIR = Path(__file__).resolve().parents[2] / "policies"
_EMPTY_ENTITIES = cedarpy.Entities.from_json_str("[]")


@dataclass(frozen=True)
class RuleHit:
    rule: str
    verdict: str  # a Verdict value, or "FLAG"


@dataclass(frozen=True)
class PolicyResult:
    hits: tuple[RuleHit, ...]

    @property
    def verdict(self) -> Verdict:
        verdicts = [Verdict(h.verdict) for h in self.hits if h.verdict != "FLAG"]
        return max(verdicts, key=lambda v: v.severity, default=Verdict.ALLOW)

    @property
    def flagged(self) -> bool:
        return any(h.verdict == "FLAG" for h in self.hits)

    def rule_ids(self) -> list[str]:
        return sorted({h.rule for h in self.hits})

    def rules_for(self, verdict: Verdict) -> list[str]:
        return sorted({h.rule for h in self.hits if h.verdict == verdict.value})


class CedarEngine:
    def __init__(self, policy_dir: Path = POLICY_DIR) -> None:
        text = "\n".join(p.read_text(encoding="utf-8") for p in sorted(policy_dir.glob("*.cedar")))
        self.policy_text = text
        self._policies = cedarpy.PolicySet.from_str(text)
        parsed = json.loads(cedarpy.policies_to_json_str(text))["staticPolicies"]
        self._annotations: dict[str, RuleHit] = {
            pid: RuleHit(rule=p["annotations"]["rule"], verdict=p["annotations"]["verdict"])
            for pid, p in parsed.items()
            if "rule" in p.get("annotations", {})
        }

    @property
    def rules(self) -> list[RuleHit]:
        return list(self._annotations.values())

    def evaluate(self, agent_id: str, tool: str, context: dict[str, Any]) -> PolicyResult:
        request = {
            "principal": {"type": "Agent", "id": agent_id},
            "action": {"type": "Action", "id": "invoke"},
            "resource": {"type": "Tool", "id": tool},
            "context": context,
        }
        result = cedarpy.is_authorized(request, self._policies, _EMPTY_ENTITIES)
        if result.diagnostics.errors:
            # A policy evaluation error must never silently allow: fail closed.
            return PolicyResult(hits=(RuleHit(rule="POLICY_ERROR", verdict=Verdict.BLOCK.value),))
        hits = tuple(self._annotations[r] for r in result.diagnostics.reasons if r in self._annotations)
        return PolicyResult(hits=hits)


@lru_cache(maxsize=1)
def default_engine() -> CedarEngine:
    """Policies are parsed once per process and shared by every gateway."""
    return CedarEngine()
