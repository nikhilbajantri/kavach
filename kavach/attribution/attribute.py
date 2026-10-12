"""Argument Provenance Attribution: where did each CONTROL value come from?

Matching ladder, per ledger entry:
  1. exact   normalised substring (also inside Base64 / hex / URL-decoded views)
  2. numeric for amounts, equality of parsed numbers (48,000 = 48000 = ₹48k)
  3. fuzzy   rapidfuzz partial_ratio ≥ 90 on values of 6+ chars

Security choice: only exact/decoded/numeric matches can make a value TRUSTED.
A fuzzy match is evidence *against* a value, never for it; otherwise a
typosquat like `ravikumar@okicic1` would borrow trust from `ravikumar@okicici`.
"""

from __future__ import annotations

from typing import Any

from rapidfuzz import fuzz, process

from kavach.attribution.normalise import View, normalise, parse_number
from kavach.models import Evidence, Origin, ParamAttribution, Trust
from kavach.provenance.ledger import IndexedEntry, ProvenanceStore

FUZZY_THRESHOLD = 90.0
FUZZY_MIN_LEN = 6
EXACT_MIN_LEN = 3
SNIPPET_PAD = 48


def _snippet(text: str, span: tuple[int, int]) -> str:
    start, end = max(0, span[0] - SNIPPET_PAD), min(len(text), span[1] + SNIPPET_PAD)
    return ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")


def _evidence(item: IndexedEntry, match: str, span: tuple[int, int], score: float = 100.0) -> Evidence:
    e = item.entry
    return Evidence(
        entry_id=e.id,
        source=e.source,
        trust=e.trust,
        match=match,
        score=score,
        span=span,
        snippet=_snippet(e.text, span),
    )


def _exact(item: IndexedEntry, needle: str) -> Evidence | None:
    for view in item.views:
        pos = view.text.find(needle)
        if pos >= 0:
            kind = "exact" if view.kind == "plain" else f"decoded:{view.kind}"
            return _evidence(item, kind, view.span(pos, pos + len(needle)))
    return None


def _numeric(item: IndexedEntry, number: float) -> Evidence | None:
    for value, span in item.numbers:
        if abs(value - number) < 0.005:
            return _evidence(item, "numeric", span)
    return None


def _fuzzy(candidates: list[IndexedEntry], needle: str) -> list[Evidence]:
    """One vectorised pass over all candidate views (C speed), then map hits back to spans."""
    views: list[tuple[IndexedEntry, View]] = [(item, v) for item in candidates for v in item.views]
    if not views or len(needle) < FUZZY_MIN_LEN:
        return []
    hits = process.extract(
        needle,
        [v.text for _, v in views],
        scorer=fuzz.partial_ratio,
        score_cutoff=FUZZY_THRESHOLD,
        limit=None,
    )
    out: list[Evidence] = []
    seen: set[str] = set()
    for _, score, idx in hits:
        item, view = views[idx]
        if item.entry.id in seen:
            continue
        seen.add(item.entry.id)
        align = fuzz.partial_ratio_alignment(needle, view.text)
        span = view.span(align.dest_start, align.dest_end) if align else (0, 0)
        out.append(_evidence(item, "fuzzy", span, score=round(score, 1)))
    return out


def attribute_value(
    param: str, value: Any, store: ProvenanceStore, *, numeric: bool = False
) -> ParamAttribution:
    text = str(value)
    evidence: list[Evidence] = []
    number = parse_number(value) if numeric else None
    needle = normalise(text)

    for item in store.entries:
        hit = None
        if number is not None:
            hit = _numeric(item, number)
        elif len(needle) >= EXACT_MIN_LEN:
            hit = _exact(item, needle)
        elif needle and item.plain.text == needle:
            hit = _evidence(item, "exact", (0, len(item.entry.text)))
        if hit:
            evidence.append(hit)

    if any(e.trust is Trust.TRUSTED for e in evidence):
        origin = Origin.TRUSTED
    elif evidence:
        origin = Origin.UNTRUSTED_ONLY
    else:
        untrusted = [i for i in store.entries if i.entry.trust is Trust.UNTRUSTED]
        evidence = [] if number is not None else _fuzzy(untrusted, needle)
        origin = Origin.UNTRUSTED_ONLY if evidence else Origin.UNKNOWN

    # Trusted evidence first, then strongest matches; cap what we ship to the UI.
    evidence.sort(key=lambda e: (e.trust is not Trust.TRUSTED, -e.score))
    return ParamAttribution(param=param, value=text, origin=origin, evidence=evidence[:8])
