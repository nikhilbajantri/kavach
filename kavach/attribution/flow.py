"""Sensitivity flow: how much regulated / confidential ledger content rides in a sink's CONTENT.

We measure the share of the outgoing content's 8-character shingles that also
occur in sensitive ledger entries. At ≥ 30 % the content "carries" that
sensitivity. PAN and Aadhaar patterns trip regulated PII on their own, including
inside Base64, hex or URL-encoded blobs.
"""

from __future__ import annotations

import re

from kavach.attribution.normalise import all_views, decode_layers
from kavach.models import FlowReport, Sensitivity
from kavach.provenance.ledger import SHINGLE, ProvenanceStore

CONTAINMENT_THRESHOLD = 0.30

PII_PATTERNS = {
    "PAN": re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),
    "Aadhaar": re.compile(r"\b[2-9][0-9]{3}[\s-]?[0-9]{4}[\s-]?[0-9]{4}\b"),
    "Aadhaar (masked)": re.compile(r"\bX{4}[\s-]X{4}[\s-][0-9]{4}\b", re.IGNORECASE),
}


def _pii_hits(raw: str, views: list[str]) -> list[str]:
    hits = [name for name, rx in PII_PATTERNS.items() if rx.search(raw)]
    for decoded in views:
        hits += [f"{name} (encoded)" for name, rx in PII_PATTERNS.items() if rx.search(decoded)]
    return sorted(set(hits))


def _coverage(text: str, grams: list[str], pool: set[str], n: int = SHINGLE) -> float:
    """Fraction of the content's characters covered by a shingle that also occurs in the pool.

    Character coverage (not shingle share) keeps short fields like a PAN from being
    drowned out by the separators between them.
    """
    if not text:
        return 0.0
    if len(text) < n:
        return 1.0 if text in pool else 0.0
    covered, reach = 0, 0
    for i in [i for i, gram in enumerate(grams) if gram in pool]:
        start = max(i, reach)
        reach = i + n
        covered += reach - start
    return covered / len(text)


def _grams(text: str, n: int = SHINGLE) -> list[str]:
    return [text[i : i + n] for i in range(len(text) - n + 1)]


def sensitivity_flow(content: str, store: ProvenanceStore) -> FlowReport:
    if not content.strip():
        return FlowReport()
    layers = decode_layers(content)
    views = all_views(content, with_index=False, layers=layers)
    combined = "\n".join(v.text for v in views)
    report = FlowReport()

    grams = [_grams(v.text) for v in views]
    for level in (Sensitivity.REGULATED_PII, Sensitivity.CONFIDENTIAL):
        pool = store.sensitive_shingles.get(level)
        if not pool:
            continue
        share = max(_coverage(v.text, g, pool) for v, g in zip(views, grams, strict=True))
        if share > report.containment:
            report.containment = round(share, 3)
        if share >= CONTAINMENT_THRESHOLD and level.rank > report.sensitivity.rank:
            report.sensitivity = level

    report.pii_patterns = _pii_hits(content, [dec for dec, _, _ in layers])
    if report.pii_patterns:
        report.sensitivity = Sensitivity.REGULATED_PII

    # Count distinct customer records whose KYC fields appear in the content.
    # A cheap shingle pre-filter avoids a full substring scan for each of hundreds of entries.
    content_shingles = {combined[i : i + 6] for i in range(len(combined) - 5)}
    records: set[str] = set()
    evidence: list[str] = []
    for needle, record_id, entry_id in store.record_values:
        if needle[:6] in content_shingles and needle[-6:] in content_shingles and needle in combined:
            records.add(record_id)
            if len(evidence) < 60:
                evidence.append(entry_id)
    report.records = len(records)
    report.evidence_ids = evidence
    if report.records and report.sensitivity.rank < Sensitivity.REGULATED_PII.rank:
        report.sensitivity = Sensitivity.REGULATED_PII
    return report
