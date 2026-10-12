"""Append-only, hash-chained evidence ledger.

Each record stores `prev_hash` and `hash = SHA256(prev_hash + canonical_json(record))`,
so editing, deleting or reordering any row breaks every hash after it.

PII minimisation (DPDP): arguments are stored masked, together with the
SHA-256 of the exact raw arguments. That hash equals the `args_hash` inside the
action token, so the ledger proves *what* was sent without retaining the PII.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from kavach.canonical import args_hash, canonical_json, sha256_hex
from kavach.ledger.mask import mask
from kavach.models import Decision

GENESIS = "0" * 64

SCHEMA = """
CREATE TABLE IF NOT EXISTS ledger (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    record TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ledger_session ON ledger(session_id);
"""


def record_from_decision(decision: Decision, seq: int) -> dict[str, Any]:
    return {
        "seq": seq,
        "ts": round(time.time(), 3),
        "session_id": decision.session_id,
        "call_id": decision.call_id,
        "mode": decision.mode,
        "identity": decision.identity,
        "ticket_id": decision.ticket_id,
        "tool": decision.tool,
        "args": mask(decision.args),
        "final_args": mask(decision.final_args),
        "args_hash": args_hash(decision.final_args or {}),
        "origins": [
            {
                "param": a.param,
                "value": mask(a.value),
                "origin": a.origin.value,
                "evidence": [e.entry_id for e in a.evidence],
            }
            for a in decision.attributions
        ],
        "flow": decision.flow.model_dump(mode="json", exclude={"evidence_ids"}) if decision.flow else None,
        "evidence_ids": sorted(
            {e.entry_id for a in decision.attributions for e in a.evidence}
            | set(decision.flow.evidence_ids if decision.flow else [])
        ),
        "verdict": decision.verdict.value,
        "rule_ids": decision.rule_ids,
        "explanation": mask(decision.explanation),
        "remediations": [mask(r.model_dump()) for r in decision.remediations],
        "risk": decision.risk,
        "latency_ms": decision.latency_ms,
        "token_id": decision.token_id,
        "approval_id": decision.approval_id,
    }


class EvidenceLedger:
    def __init__(self, path: str | Path = ":memory:") -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.executescript(SCHEMA)
        self._lock = threading.Lock()

    def _head(self) -> tuple[int, str]:
        row = self.db.execute("SELECT seq, hash FROM ledger ORDER BY seq DESC LIMIT 1").fetchone()
        return (row[0], row[1]) if row else (0, GENESIS)

    def append(self, decision: Decision) -> dict[str, Any]:
        with self._lock:
            last_seq, prev_hash = self._head()
            record = record_from_decision(decision, last_seq + 1)
            body = canonical_json(record)
            digest = sha256_hex(prev_hash + body)
            self.db.execute(
                "INSERT INTO ledger (seq, session_id, record, prev_hash, hash) VALUES (?,?,?,?,?)",
                (record["seq"], decision.session_id, body, prev_hash, digest),
            )
            self.db.commit()
        return {**record, "prev_hash": prev_hash, "hash": digest}

    def rows(self, session_id: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
        sql = "SELECT record, prev_hash, hash FROM ledger"
        params: list[Any] = []
        if session_id:
            sql += " WHERE session_id = ?"
            params.append(session_id)
        sql += " ORDER BY seq DESC LIMIT ?"
        params.append(limit)
        return [
            {**json.loads(r), "prev_hash": p, "hash": h}
            for r, p, h in self.db.execute(sql, params).fetchall()
        ]

    def verify(self) -> dict[str, Any]:
        """Recompute the whole chain. Any edited, deleted or reordered row is reported."""
        prev = GENESIS
        count = 0
        expected_seq = 1
        for seq, record, prev_hash, digest in self.db.execute(
            "SELECT seq, record, prev_hash, hash FROM ledger ORDER BY seq"
        ):
            count += 1
            if seq != expected_seq:
                return {
                    "ok": False,
                    "count": count,
                    "broken_at": seq,
                    "reason": "missing row before this one",
                }
            if prev_hash != prev:
                return {"ok": False, "count": count, "broken_at": seq, "reason": "prev_hash does not link"}
            if sha256_hex(prev_hash + record) != digest:
                return {
                    "ok": False,
                    "count": count,
                    "broken_at": seq,
                    "reason": "record content was modified",
                }
            if json.loads(record).get("seq") != seq:
                return {"ok": False, "count": count, "broken_at": seq, "reason": "row was renumbered"}
            prev = digest
            expected_seq += 1
        return {"ok": True, "count": count, "head": prev}

    def sessions(self) -> list[str]:
        return [
            r[0]
            for r in self.db.execute(
                "SELECT session_id FROM ledger GROUP BY session_id ORDER BY MIN(seq) DESC"
            )
        ]
