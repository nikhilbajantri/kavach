"""SANITISE remediations: replace attacker-chosen control values with safe defaults.

For refunds the safe default is unambiguous: money goes back to the customer's
own verified instrument, found by matching the ticket sender to the CRM.
"""

from __future__ import annotations

from typing import Any

from kavach.models import Origin, ParamAttribution, Remediation, Sensitivity, Trust
from kavach.policy.directory import TrustDirectory
from kavach.provenance.ledger import ProvenanceStore

_VERIFIED_FIELD = {"recipient_upi": "verified_upi", "recipient_account": "verified_account"}


def refund_to_verified_recipient(
    args: dict[str, Any],
    attributions: list[ParamAttribution],
    customer: dict[str, Any] | None,
    store: ProvenanceStore,
) -> tuple[dict[str, Any], list[Remediation]] | None:
    if customer is None:
        return None
    new_args = dict(args)
    fixes: list[Remediation] = []
    for attr in attributions:
        if attr.origin is not Origin.UNTRUSTED_ONLY or attr.param not in _VERIFIED_FIELD:
            continue
        field = _VERIFIED_FIELD[attr.param]
        replacement = customer[field]
        new_args[attr.param] = replacement
        # KAVACH itself looked this up in the system of record: record it as trusted provenance.
        store.add(
            replacement,
            source="kavach.directory",
            trust=Trust.TRUSTED,
            sensitivity=Sensitivity.CONFIDENTIAL,
            label=f"{field} of {customer['customer_id']} (looked up by KAVACH)",
            field_name=field,
            record_id=customer["customer_id"],
        )
        fixes.append(
            Remediation(
                param=attr.param,
                original=str(attr.value),
                replacement=replacement,
                reason=f"replaced with {customer['name']}'s {field.replace('_', ' ')} from the CRM",
            )
        )
    return (new_args, fixes) if fixes else None


REMEDIATIONS = {"refund_to_verified_recipient": refund_to_verified_recipient}


def ticket_customer(directory: TrustDirectory, sender: str | None) -> dict[str, Any] | None:
    return directory.customer_by_email(sender) if sender else None
