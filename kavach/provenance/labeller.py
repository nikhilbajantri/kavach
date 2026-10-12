"""Labelling rules: how each tool result is split into trusted / untrusted ledger entries.

Rules are per field, not per tool, because one CRM record mixes verified
recipient fields (trusted), KYC fields (regulated PII) and free text typed by
customers (untrusted). Anything we do not recognise is labelled untrusted:
fail closed.
"""

from __future__ import annotations

import json
from typing import Any

from kavach.models import Sensitivity, Trust
from kavach.provenance.ledger import ProvenanceStore

T, U = Trust.TRUSTED, Trust.UNTRUSTED
PUB, INT, CONF, PII = (
    Sensitivity.PUBLIC,
    Sensitivity.INTERNAL,
    Sensitivity.CONFIDENTIAL,
    Sensitivity.REGULATED_PII,
)

# field -> (trust, sensitivity, source)
CRM_FIELDS: dict[str, tuple[Trust, Sensitivity, str]] = {
    "customer_id": (T, CONF, "crm.record"),
    "name": (T, CONF, "crm.record"),
    "email": (T, CONF, "crm.verified"),
    "verified_upi": (T, CONF, "crm.verified"),
    "verified_account": (T, CONF, "crm.verified"),
    "phone": (T, PII, "crm.kyc"),
    "address": (T, PII, "crm.kyc"),
    "pan": (T, PII, "crm.kyc"),
    "aadhaar_last4": (T, PII, "crm.kyc"),
    "city": (T, CONF, "crm.record"),
    "bank": (T, CONF, "crm.record"),
    "created_at": (T, INT, "crm.record"),
    "notes": (U, CONF, "crm.free_text"),
}


def label_session_start(
    store: ProvenanceStore, system_prompt: str, operator_prompt: str, org_domains: tuple[str, ...]
) -> None:
    store.add(system_prompt, source="org_config", trust=T, sensitivity=INT, label="agent system prompt")
    store.add(operator_prompt, source="user_prompt", trust=T, sensitivity=INT, label="operator instruction")
    store.add(
        " ".join(org_domains), source="org_config", trust=T, sensitivity=PUB, label="verified org domains"
    )


def label_result(
    store: ProvenanceStore, tool: str, args: dict[str, Any], result: dict[str, Any], call_id: str
) -> None:
    labeller = _LABELLERS.get(tool, _label_unknown)
    labeller(store, args, result, call_id)


def _label_inbox(store: ProvenanceStore, args: dict[str, Any], result: dict[str, Any], call_id: str) -> None:
    for m in result.get("messages", []):
        store.add(
            m.get("from", ""),
            source="email.sender",
            trust=U,
            sensitivity=INT,
            label=f"sender of {m['id']}",
            field_name="from",
            record_id=m["id"],
            call_id=call_id,
        )
        store.add(
            m.get("subject", ""),
            source="email.inbound",
            trust=U,
            sensitivity=INT,
            label=f"subject of {m['id']}",
            field_name="subject",
            record_id=m["id"],
            call_id=call_id,
        )


def _label_read(store: ProvenanceStore, args: dict[str, Any], result: dict[str, Any], call_id: str) -> None:
    mid = result.get("id", args.get("message_id", "?"))
    store.add(
        result.get("from", ""),
        source="email.sender",
        trust=U,
        sensitivity=INT,
        label=f"sender of {mid}",
        field_name="from",
        record_id=mid,
        call_id=call_id,
    )
    store.add(
        result.get("subject", ""),
        source="email.inbound",
        trust=U,
        sensitivity=INT,
        label=f"subject of {mid}",
        field_name="subject",
        record_id=mid,
        call_id=call_id,
    )
    store.add(
        result.get("body", ""),
        source="email.inbound",
        trust=U,
        sensitivity=INT,
        label=f"email {mid} body",
        field_name="body",
        record_id=mid,
        call_id=call_id,
    )


def _label_customer(store: ProvenanceStore, customer: dict[str, Any], call_id: str) -> None:
    cid = customer.get("customer_id", "?")
    for key, value in customer.items():
        if key == "orders":
            for order in value or []:
                text = f"{order['order_id']} {order['item']} ₹{order['amount_inr']} {order['date']} {order['status']}"
                store.add(
                    text,
                    source="crm.order",
                    trust=T,
                    sensitivity=CONF,
                    label=f"order {order['order_id']} of {cid}",
                    field_name="order",
                    record_id=cid,
                    call_id=call_id,
                )
            continue
        if key == "address_provenance":
            continue
        trust, sens, source = CRM_FIELDS.get(key, (U, CONF, "crm.unknown_field"))
        if key == "address" and customer.get("address_provenance") == "customer_supplied":
            trust, source = U, "crm.customer_supplied"  # taint persisted with the data
        store.add(
            str(value),
            source=source,
            trust=trust,
            sensitivity=sens,
            label=f"{key} of {cid}",
            field_name=key,
            record_id=cid,
            call_id=call_id,
        )


def _label_get_customer(
    store: ProvenanceStore, args: dict[str, Any], result: dict[str, Any], call_id: str
) -> None:
    _label_customer(store, result, call_id)


def _label_search(store: ProvenanceStore, args: dict[str, Any], result: dict[str, Any], call_id: str) -> None:
    for customer in result.get("customers", []):
        _label_customer(store, customer, call_id)


def _label_update_address(
    store: ProvenanceStore, args: dict[str, Any], result: dict[str, Any], call_id: str
) -> None:
    store.add(
        result.get("address", ""),
        source="crm.customer_supplied",
        trust=U,
        sensitivity=PII,
        label=f"address of {result.get('customer_id')}",
        field_name="address",
        record_id=result.get("customer_id"),
        call_id=call_id,
    )


def _label_system_ack(
    store: ProvenanceStore, args: dict[str, Any], result: dict[str, Any], call_id: str
) -> None:
    """Receipts from our own systems: only system-generated fields are trusted.

    Echoed request fields (recipient, notes) are deliberately skipped: a receipt
    must never launder an attacker-chosen value into a trusted one.
    """
    for key in ("id", "status"):
        if key in result:
            store.add(
                str(result[key]),
                source="system.receipt",
                trust=T,
                sensitivity=INT,
                label=f"{key} in receipt of {call_id}",
                field_name=key,
                call_id=call_id,
            )


def _label_unknown(
    store: ProvenanceStore, args: dict[str, Any], result: dict[str, Any], call_id: str
) -> None:
    store.add(
        json.dumps(result, ensure_ascii=False),
        source="tool.unknown",
        trust=U,
        sensitivity=CONF,
        label=f"result of {call_id}",
        call_id=call_id,
    )


_LABELLERS = {
    "email.list_inbox": _label_inbox,
    "email.read": _label_read,
    "email.send": _label_system_ack,
    "crm.get_customer": _label_get_customer,
    "crm.search_customers": _label_search,
    "crm.update_address": _label_update_address,
    "payments.refund": _label_system_ack,
}
