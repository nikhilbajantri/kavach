"""Plain-language explanations: every verdict must be readable by an auditor at a glance."""

from __future__ import annotations

from typing import Any

from kavach.models import Evidence, FlowReport, Origin, ParamAttribution, Remediation, Trust, Verdict
from kavach.policy.context import Destination

PARAM_NAMES = {
    "to": "recipient",
    "recipient_upi": "recipient UPI",
    "recipient_account": "recipient account",
    "amount_inr": "amount",
    "url": "URL",
    "customer_id": "customer id",
}
LEAD = {
    Verdict.BLOCK: "Blocked",
    Verdict.SANITISE: "Sanitised",
    Verdict.ESCALATE: "Escalated to a human",
    Verdict.ALLOW: "Allowed",
}


def inr(value: Any) -> str:
    try:
        n = int(float(str(value).replace(",", "")))
    except ValueError:
        return str(value)
    s = str(n)
    head, tail = s[:-3], s[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return "₹" + ",".join([*groups, tail]) if groups else f"₹{tail}"


def _source_phrase(evidence: list[Evidence]) -> str:
    untrusted = [e for e in evidence if e.trust is Trust.UNTRUSTED]
    if not untrusted:
        return "untrusted content"
    e = untrusted[0]
    how = "" if e.match == "exact" else f", {e.match.replace('decoded:', 'hidden as ')}"
    if e.source.startswith("email"):
        return f"an untrusted email ({e.record_id or e.label}{how})"
    if e.source.startswith("crm.customer_supplied"):
        return f"customer-supplied text stored in the CRM ({e.record_id}{how})"
    return f"untrusted {e.source} ({e.label}{how})"


def _param(attr: ParamAttribution) -> str:
    value = inr(attr.value) if attr.param == "amount_inr" else attr.value
    return f"{PARAM_NAMES.get(attr.param, attr.param)} '{value}'"


def explain(
    *,
    verdict: Verdict,
    rules: list[str],
    tool: str,
    is_sink: bool,
    attributions: list[ParamAttribution],
    flow: FlowReport | None,
    destinations: list[Destination],
    remediations: list[Remediation],
    customer: dict[str, Any] | None,
    args: dict[str, Any],
) -> str:
    reasons: list[str] = []
    if "R0" in rules:
        reasons.append(
            f"tool '{tool}' is quarantined because its pinned manifest changed (tool_manifest_changed)"
        )
    if "R1" in rules:
        for a in attributions:
            if a.origin is Origin.UNTRUSTED_ONLY:
                reasons.append(
                    f"{_param(a)} came only from {_source_phrase(a.evidence)}, not from the operator or verified records"
                )
    if "R2" in rules and flow:
        what = (
            f"regulated PII ({flow.records} customer KYC record{'s' if flow.records != 1 else ''})"
            if flow.records
            else f"{flow.sensitivity.value.replace('_', ' ')} data"
        )
        ext = next((d for d in destinations if d.trust == "external" and d.carries_data), None)
        where = f"external destination {ext.domain or ext.value}" if ext else "an external destination"
        reasons.append(f"{what} would flow to {where}, outside the bank and the data subject")
    if "R3" in rules:
        for d in destinations:
            if d.age_days is not None and d.age_days < 30 and d.trust != "org":
                reasons.append(
                    f"domain {d.domain} was registered {d.age_days} day{'s' if d.age_days != 1 else ''} ago (minimum 30)"
                )
    if "R4" in rules:
        for a in attributions:
            if a.origin is Origin.UNKNOWN:
                reasons.append(f"{_param(a)} appears nowhere in the session, so the model made it up")
    if "R6" in rules:
        who = customer["name"] if customer else "the ticket's customer"
        reasons.append(
            f"refund amount {inr(args.get('amount_inr'))} does not match any order on {who}'s record"
        )

    if verdict is Verdict.SANITISE:
        fixed = "; ".join(
            f"{PARAM_NAMES.get(r.param, r.param)} replaced with '{r.replacement}' ({r.reason})"
            for r in remediations
        )
        body = "; ".join(reasons) or "untrusted control value"
        return f"Sanitised: {body}. {fixed[0].upper() + fixed[1:] if fixed else ''}".strip()
    if verdict is Verdict.ALLOW:
        if not is_sink:
            return "Allowed: read-only call; its results are labelled into the provenance ledger."
        trusted = [_param(a) for a in attributions if a.origin is Origin.TRUSTED]
        tail = f" ({', '.join(trusted)})" if trusted else ""
        return f"Allowed: every control value traces to the operator or verified records{tail}."
    return f"{LEAD[verdict]}: " + "; ".join(reasons) + "."


def risk_summary(rules: list[str], session_untrusted: bool, session_regulated: bool, flagged: bool) -> str:
    if flagged:
        return "high"
    if session_untrusted and session_regulated:
        return "elevated"
    return "low"
