"""Tool typing: which parameters decide who / where / how much (CONTROL) vs payload (CONTENT).

This is KAVACH-owned configuration, not something read from upstream tool
descriptions, which an attacker may control (see L3).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from kavach.models import ParamRole


class ParamKind(StrEnum):
    EMAIL = "email"
    UPI = "upi"
    ACCOUNT = "account"
    AMOUNT = "amount"
    URL = "url"
    ID = "id"
    FILTER = "filter"
    TEXT = "text"


class ParamSpec(BaseModel):
    role: ParamRole
    kind: ParamKind = ParamKind.TEXT
    destination: bool = False  # value names where data or money goes


class ToolSpec(BaseModel):
    name: str
    sink: bool  # sends data out or changes state
    category: str = "read"  # read | outbound | payment | state_change
    params: dict[str, ParamSpec] = Field(default_factory=dict)
    remediation: str | None = None  # name of a safe-default remediation, if any

    def control_params(self) -> list[str]:
        return [p for p, s in self.params.items() if s.role is ParamRole.CONTROL]

    def content_params(self) -> list[str]:
        return [p for p, s in self.params.items() if s.role is ParamRole.CONTENT]

    def destination_params(self) -> list[str]:
        return [p for p, s in self.params.items() if s.destination]


C, X = ParamRole.CONTROL, ParamRole.CONTENT

TOOL_SPECS: dict[str, ToolSpec] = {
    s.name: s
    for s in [
        ToolSpec(name="email.list_inbox", sink=False),
        ToolSpec(name="email.read", sink=False, params={"message_id": ParamSpec(role=C, kind=ParamKind.ID)}),
        ToolSpec(
            name="email.send",
            sink=True,
            category="outbound",
            params={
                "to": ParamSpec(role=C, kind=ParamKind.EMAIL, destination=True),
                "subject": ParamSpec(role=X),
                "body": ParamSpec(role=X),
            },
        ),
        ToolSpec(
            name="crm.get_customer",
            sink=False,
            params={
                "customer_id": ParamSpec(role=C, kind=ParamKind.ID),
                "email": ParamSpec(role=C, kind=ParamKind.FILTER),
                "phone": ParamSpec(role=C, kind=ParamKind.FILTER),
            },
        ),
        ToolSpec(
            name="crm.search_customers",
            sink=False,
            params={
                "query": ParamSpec(role=C, kind=ParamKind.FILTER),
                "city": ParamSpec(role=C, kind=ParamKind.FILTER),
                "limit": ParamSpec(role=C, kind=ParamKind.AMOUNT),
            },
        ),
        ToolSpec(
            name="crm.update_address",
            sink=True,
            category="state_change",
            params={"customer_id": ParamSpec(role=C, kind=ParamKind.ID), "new_address": ParamSpec(role=X)},
        ),
        ToolSpec(
            name="payments.refund",
            sink=True,
            category="payment",
            remediation="refund_to_verified_recipient",
            params={
                "amount_inr": ParamSpec(role=C, kind=ParamKind.AMOUNT),
                "recipient_upi": ParamSpec(role=C, kind=ParamKind.UPI, destination=True),
                "recipient_account": ParamSpec(role=C, kind=ParamKind.ACCOUNT, destination=True),
                "reason": ParamSpec(role=X),
            },
        ),
    ]
}


def spec_for(tool: str, args: dict[str, object]) -> ToolSpec:
    """Unknown tools fail closed: a sink whose every argument is CONTROL."""
    if tool in TOOL_SPECS:
        return TOOL_SPECS[tool]
    return ToolSpec(name=tool, sink=True, category="unknown", params={k: ParamSpec(role=C) for k in args})
