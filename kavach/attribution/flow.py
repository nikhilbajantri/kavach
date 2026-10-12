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


# shingle_rank values are 1 + Sensitivity.rank: 3 = confidential, 4 = regulated PII.
_REGULATED = bytes.maketrans(bytes(range(5)), b"00001")
_CONF_OR_HIGHER = bytes.maketrans(bytes(range(5)), b"00011")
_RUNS = re.compile(rb"1(?:0{0,%d}1)*" % (SHINGLE - 1))


def _coverage(flags: bytes, length: int, n: int = SHINGLE) -> float:
    """Fraction of the content's characters covered by a sensitive shingle.

    Character coverage (not shingle share) keeps short fields like a PAN from being
    drowned out by the separators between them. Runs of hits closer than `n`
    overlap, so each merged run covers its span plus n - 1 characters.
    """
    covered = sum(m.end() - m.start() + n - 1 for m in _RUNS.finditer(flags))
    return min(1.0, covered / length) if length else 0.0


def _level_coverage(text: str, ranks: dict[str, int], n: int = SHINGLE) -> tuple[float, float]:
    """(regulated coverage, confidential-or-higher coverage), with the merging done in C."""
    if len(text) < n:
        rank = ranks.get(text, 0)
        return (1.0 if rank >= 4 else 0.0, 1.0 if rank >= 3 else 0.0)
    get = ranks.get
    levels = bytes([get(text[i : i + n], 0) for i in range(len(text) - n + 1)])
    return (
        _coverage(levels.translate(_REGULATED), len(text), n),
        _coverage(levels.translate(_CONF_OR_HIGHER), len(text), n),
    )


def sensitivity_flow(content: str, store: ProvenanceStore) -> FlowReport:
    if not content.strip():
        return FlowReport()
    layers = decode_layers(content)
    views = all_views(content, with_index=False, layers=layers)
    combined = "\n".join(v.text for v in views)
    report = FlowReport()

    if store.shingle_rank:
        shares = [_level_coverage(v.text, store.shingle_rank) for v in views]
        regulated = max(s[0] for s in shares)
        confidential = max(s[1] for s in shares)
        report.containment = round(max(regulated, confidential), 3)
        if regulated >= CONTAINMENT_THRESHOLD:
            report.sensitivity = Sensitivity.REGULATED_PII
        elif confidential >= CONTAINMENT_THRESHOLD:
            report.sensitivity = Sensitivity.CONFIDENTIAL

    report.pii_patterns = _pii_hits(content, [dec for dec, _, _ in layers])
    if report.pii_patterns:
        report.sensitivity = Sensitivity.REGULATED_PII

    # Count distinct customer records whose KYC fields appear in the content.
    records: set[str] = set()
    evidence: list[str] = []
    for needle, record_id, entry_id in store.record_values:
        if needle in combined:
            records.add(record_id)
            if len(evidence) < 60:
                evidence.append(entry_id)
    report.records = len(records)
    report.evidence_ids = evidence
    if report.records and report.sensitivity.rank < Sensitivity.REGULATED_PII.rank:
        report.sensitivity = Sensitivity.REGULATED_PII
    return report
