"""Provenance ledger: every piece of content that enters the agent's context, with its label.

Entries are pre-normalised when added, so attribution at decision time is a
cheap scan rather than repeated Unicode work (the p95 < 10 ms budget).
"""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from kavach.attribution.normalise import View, all_views, extract_numbers
from kavach.models import Sensitivity, Trust

SHINGLE = 8
# KYC fields that identify one customer record; used to count records inside outbound content.
RECORD_FIELDS = frozenset({"pan", "phone", "address", "aadhaar_last4"})


class LedgerEntry(BaseModel):
    id: str
    session_id: str
    text: str
    source: str  # user_prompt | org_config | crm.record | crm.verified | crm.order | email.inbound | ...
    trust: Trust
    sensitivity: Sensitivity
    timestamp: float = Field(default_factory=time.time)
    label: str = ""  # human description, e.g. "email TKT-1003 body"
    field: str | None = None
    record_id: str | None = None
    call_id: str | None = None


@dataclass
class IndexedEntry:
    entry: LedgerEntry
    views: list[View]
    numbers: list[tuple[float, tuple[int, int]]]

    @property
    def plain(self) -> View:
        return self.views[0]


def shingles(text: str, n: int = SHINGLE) -> set[str]:
    if len(text) < n:
        return {text} if text else set()
    return {text[i : i + n] for i in range(len(text) - n + 1)}


@dataclass
class ProvenanceStore:
    session_id: str
    entries: list[IndexedEntry] = field(default_factory=list)
    by_id: dict[str, IndexedEntry] = field(default_factory=dict)
    # Shingle sets per sensitivity level, maintained incrementally for flow checks.
    sensitive_shingles: dict[Sensitivity, set[str]] = field(default_factory=dict)
    # (normalised value, record id, entry id) for KYC fields, so flow checks skip everything else.
    record_values: list[tuple[str, str, str]] = field(default_factory=list)
    saw_untrusted: bool = False
    _ids: itertools.count = field(default_factory=lambda: itertools.count(1))

    def add(
        self,
        text: str,
        *,
        source: str,
        trust: Trust,
        sensitivity: Sensitivity,
        label: str = "",
        field_name: str | None = None,
        record_id: str | None = None,
        call_id: str | None = None,
    ) -> LedgerEntry | None:
        text = str(text)
        if not text.strip():
            return None
        entry = LedgerEntry(
            id=f"ent_{self.session_id[-6:]}_{next(self._ids):04d}",
            session_id=self.session_id,
            text=text,
            source=source,
            trust=trust,
            sensitivity=sensitivity,
            label=label,
            field=field_name,
            record_id=record_id,
            call_id=call_id,
        )
        indexed = IndexedEntry(entry=entry, views=all_views(text), numbers=extract_numbers(text))
        self.entries.append(indexed)
        self.by_id[entry.id] = indexed
        self.saw_untrusted |= trust is Trust.UNTRUSTED
        if sensitivity.rank >= Sensitivity.CONFIDENTIAL.rank:
            self.sensitive_shingles.setdefault(sensitivity, set()).update(shingles(indexed.plain.text))
        if field_name in RECORD_FIELDS and record_id and len(indexed.plain.text) >= 6:
            self.record_values.append((indexed.plain.text, record_id, entry.id))
        return entry

    @property
    def touched_regulated(self) -> bool:
        return Sensitivity.REGULATED_PII in self.sensitive_shingles

    def get(self, entry_id: str) -> LedgerEntry | None:
        hit = self.by_id.get(entry_id)
        return hit.entry if hit else None
