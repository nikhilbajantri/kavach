"""KAVACH's own read path to systems of record (CRM, domain registry).

The agent never sees this. KAVACH uses it to judge destinations ("is this a
customer's verified UPI?") and to remediate ("what is Ravi's verified UPI?").
"""

from __future__ import annotations

from typing import Any, Protocol

from mocks.world import World


class TrustDirectory(Protocol):
    def recipient_owner(self, value: str) -> str | None: ...

    def customer_by_email(self, email: str) -> dict[str, Any] | None: ...

    def customer(self, customer_id: str) -> dict[str, Any] | None: ...

    def domain_age_days(self, domain: str) -> int | None: ...


class WorldDirectory:
    def __init__(self, world: World) -> None:
        self.world = world
        self._recipients = world.crm.verified_recipients()  # verified fields never change at runtime

    def recipient_owner(self, value: str) -> str | None:
        return self._recipients.get(value.strip().lower())

    def customer_by_email(self, email: str) -> dict[str, Any] | None:
        return self.world.crm.get(email=email)

    def customer(self, customer_id: str) -> dict[str, Any] | None:
        return self.world.crm.get(customer_id=customer_id)

    def domain_age_days(self, domain: str) -> int | None:
        return self.world.registry.age_days(domain)
