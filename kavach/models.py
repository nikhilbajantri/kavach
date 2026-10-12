"""Shared vocabulary of the gateway: labels, origins, verdicts and decisions."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Trust(StrEnum):
    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"


class Sensitivity(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    REGULATED_PII = "regulated_pii"

    @property
    def rank(self) -> int:
        return _SENSITIVITY_RANK[self]


_SENSITIVITY_RANK = {
    Sensitivity.PUBLIC: 0,
    Sensitivity.INTERNAL: 1,
    Sensitivity.CONFIDENTIAL: 2,
    Sensitivity.REGULATED_PII: 3,
}


class Origin(StrEnum):
    """Where a CONTROL argument's value came from (Argument Provenance Attribution)."""

    TRUSTED = "TRUSTED"
    UNTRUSTED_ONLY = "UNTRUSTED_ONLY"
    UNKNOWN = "UNKNOWN"


class Verdict(StrEnum):
    ALLOW = "ALLOW"
    SANITISE = "SANITISE"
    ESCALATE = "ESCALATE"
    BLOCK = "BLOCK"
    PASSTHROUGH = "PASSTHROUGH"  # KAVACH disabled: forwarded without enforcement, still logged

    @property
    def severity(self) -> int:
        return _VERDICT_SEVERITY[self]


_VERDICT_SEVERITY = {
    Verdict.PASSTHROUGH: -1,
    Verdict.ALLOW: 0,
    Verdict.SANITISE: 1,
    Verdict.ESCALATE: 2,
    Verdict.BLOCK: 3,
}


class ParamRole(StrEnum):
    CONTROL = "CONTROL"  # decides who / where / how much
    CONTENT = "CONTENT"  # payload only


class Evidence(BaseModel):
    """One ledger entry that a value was matched against, with the matched span."""

    entry_id: str
    source: str
    label: str = ""
    record_id: str | None = None
    trust: Trust
    match: str  # "exact" | "fuzzy" | "numeric" | "decoded"
    score: float = 100.0
    span: tuple[int, int] | None = None  # offsets into the entry's original text
    snippet: str = ""


class ParamAttribution(BaseModel):
    param: str
    value: str
    origin: Origin
    evidence: list[Evidence] = Field(default_factory=list)


class FlowReport(BaseModel):
    """How much sensitive ledger content rides inside a sink's CONTENT arguments."""

    sensitivity: Sensitivity = Sensitivity.PUBLIC
    containment: float = 0.0
    pii_patterns: list[str] = Field(default_factory=list)
    records: int = 0  # distinct customer records whose sensitive fields leaked into content
    evidence_ids: list[str] = Field(default_factory=list)


class Remediation(BaseModel):
    param: str
    original: str
    replacement: str
    reason: str


class Decision(BaseModel):
    """The gateway's verdict for one tool call, with everything needed to explain it."""

    call_id: str
    session_id: str
    tool: str
    args: dict[str, Any]
    final_args: dict[str, Any] | None = None
    verdict: Verdict
    rule_ids: list[str] = Field(default_factory=list)
    explanation: str = ""
    attributions: list[ParamAttribution] = Field(default_factory=list)
    flow: FlowReport | None = None
    remediations: list[Remediation] = Field(default_factory=list)
    destinations: list[dict[str, Any]] = Field(default_factory=list)
    risk: str = "low"
    latency_ms: float = 0.0
    token_id: str | None = None
    identity: dict[str, str] = Field(default_factory=dict)
    is_sink: bool = False
    approval_id: str | None = None
    ticket_id: str | None = None
    mode: str = "enforce"  # enforce | passthrough
