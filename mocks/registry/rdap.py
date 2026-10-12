"""RDAP-style domain registry mock used by KAVACH to age outbound destinations."""

from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA = Path(__file__).with_name("domains.json")


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    return json.loads(DATA.read_text(encoding="utf-8"))


class DomainRegistry:
    def __init__(self, today: date | None = None, extra: dict[str, dict[str, Any]] | None = None) -> None:
        self.today = today or date.today()
        self.domains: dict[str, dict[str, Any]] = {**_load()["domains"], **(extra or {})}
        self.upi_handles: dict[str, dict[str, Any]] = _load()["upi_handles"]

    def lookup(self, domain: str) -> dict[str, Any] | None:
        """Return an RDAP-like record, or None for domains the registry has never seen."""
        domain = domain.lower().strip(".")
        info = self.domains.get(domain)
        if info is None:
            return None
        registered = self.today - timedelta(days=int(info["registered_days_ago"]))
        return {
            "ldhName": domain,
            "events": [{"eventAction": "registration", "eventDate": registered.isoformat()}],
            "registrar": info.get("registrar"),
            "age_days": int(info["registered_days_ago"]),
            "org_verified": bool(info.get("org_verified", False)),
        }

    def age_days(self, domain: str) -> int | None:
        record = self.lookup(domain)
        return record["age_days"] if record else None
