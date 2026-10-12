"""Build the deterministic policy context Cedar evaluates.

Everything here is computed from provenance and systems of record, never from
the LLM's opinion. The context answers: where did each control value come
from, where is the data or money going, and how sensitive is it?
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from kavach.attribution.flow import sensitivity_flow
from kavach.models import FlowReport, Origin, ParamAttribution, Sensitivity
from kavach.policy.directory import TrustDirectory
from kavach.provenance.ledger import ProvenanceStore
from kavach.registry.manifests import ParamKind, ToolSpec

URL_RX = re.compile(r"https?://([^/\s\"'<>?#:]+)", re.IGNORECASE)
NO_AGE = 100_000  # Cedar needs a Long; "no domain to age" must never look young
REMEDIABLE = {"refund_to_verified_recipient": {"recipient_upi", "recipient_account"}}


@dataclass
class Destination:
    param: str
    value: str
    kind: str  # email | upi | account | url
    trust: str  # org | verified_customer | external
    domain: str | None = None
    age_days: int | None = None
    customer_id: str | None = None
    carries_data: bool = True

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _domain_trust(domain: str, org_domains: tuple[str, ...]) -> bool:
    return domain in org_domains or any(domain.endswith("." + d) for d in org_domains)


def resolve_destinations(
    spec: ToolSpec,
    args: dict[str, Any],
    directory: TrustDirectory,
    store: ProvenanceStore,
    org_domains: tuple[str, ...],
) -> list[Destination]:
    out: list[Destination] = []
    for name in spec.destination_params():
        value = str(args.get(name) or "").strip()
        if not value:
            continue
        kind = spec.params[name].kind.value
        owner = directory.recipient_owner(value)
        domain = value.rsplit("@", 1)[-1].lower() if kind == ParamKind.EMAIL.value and "@" in value else None
        if domain and _domain_trust(domain, org_domains):
            trust = "org"
        elif owner:
            trust = "verified_customer"
        else:
            trust = "external"
        age = directory.domain_age_days(domain) if domain else None
        out.append(Destination(name, value, kind, trust, domain, age, owner))

    # Links inside outbound content are destinations too (EchoLeak-style exfiltration via URLs).
    if spec.category == "outbound":
        for pname in spec.content_params():
            for match in URL_RX.finditer(str(args.get(pname) or "")):
                host = match.group(1).lower()
                url = match.group(0)
                end = str(args[pname]).find(" ", match.start())
                full = str(args[pname])[match.start() : end if end > 0 else None]
                carries = sensitivity_flow(full, store).sensitivity.rank >= Sensitivity.CONFIDENTIAL.rank
                trust = "org" if _domain_trust(host, org_domains) else "external"
                out.append(
                    Destination(
                        pname, url, "url", trust, host, directory.domain_age_days(host), None, carries
                    )
                )
    return out


def build_context(
    spec: ToolSpec,
    attributions: list[ParamAttribution],
    flow: FlowReport | None,
    destinations: list[Destination],
    store: ProvenanceStore,
    *,
    amount_matches_order: bool,
    quarantined: bool,
) -> dict[str, Any]:
    untrusted = [a.param for a in attributions if a.origin is Origin.UNTRUSTED_ONLY]
    unknown = [a.param for a in attributions if a.origin is Origin.UNKNOWN]
    fixable = REMEDIABLE.get(spec.remediation or "", set())
    ages = [d.age_days for d in destinations if d.age_days is not None and d.trust != "org"]
    return {
        "tool": spec.name,
        "category": spec.category,
        "is_sink": spec.sink,
        "is_outbound": spec.category in {"outbound", "payment"},
        "control_untrusted_only": bool(untrusted),
        "untrusted_params": untrusted,
        "control_unknown": bool(unknown),
        "unknown_params": unknown,
        "remediable": bool(untrusted) and set(untrusted) <= fixable,
        "flow_sensitivity": (flow.sensitivity if flow else Sensitivity.PUBLIC).value,
        "destination_external": any(d.trust == "external" and d.carries_data for d in destinations),
        "min_domain_age_days": min(ages, default=NO_AGE),
        "amount_matches_order": amount_matches_order,
        "tool_quarantined": quarantined,
        "session_untrusted": store.saw_untrusted,
        "session_regulated": store.touched_regulated,
    }


def refund_amount_ok(args: dict[str, Any], customer: dict[str, Any] | None) -> bool:
    """R6: the amount must equal an order amount or charge on the ticket customer's record."""
    if customer is None:
        return False
    try:
        amount = int(float(str(args.get("amount_inr", "")).replace(",", "")))
    except ValueError:
        return False
    valid = {o["amount_inr"] for o in customer.get("orders", [])}
    valid |= {c for o in customer.get("orders", []) for c in o.get("charges_inr", [])}
    return amount in valid
