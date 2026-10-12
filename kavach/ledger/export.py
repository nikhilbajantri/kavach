"""Audit export: one session as an "RBI FREE-AI / DPDP evidence pack" (Markdown + JSON)."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from kavach.ledger.chain import EvidenceLedger

TITLE = "RBI FREE-AI / DPDP evidence pack"
RULES = {
    "R0": "Supply-chain quarantine: tool manifest changed after pinning",
    "R1": "Control integrity: untrusted data may not choose who / where / how much",
    "R2": "No PII exfiltration outside the bank or the data subject",
    "R3": "Outbound destinations must be at least 30 days old",
    "R4": "Invented payment parameters need human approval",
    "R5": "Rule of Two: untrusted input + regulated data + external sink",
    "R6": "Refund amount must match an order on the customer's record",
}


def export_json(ledger: EvidenceLedger, session_id: str) -> dict[str, Any]:
    rows = list(reversed(ledger.rows(session_id=session_id, limit=10_000)))
    verdicts = Counter(r["verdict"] for r in rows)
    identity = rows[0]["identity"] if rows else {}
    return {
        "title": TITLE,
        "generated_at": datetime.now(UTC).isoformat(),
        "session_id": session_id,
        "identity": identity,
        "chain": ledger.verify(),
        "summary": {
            "decisions": len(rows),
            "verdicts": dict(verdicts),
            "rules_triggered": sorted({rule for r in rows for rule in r["rule_ids"]}),
            "max_risk": max((r["risk"] for r in rows), key=["low", "elevated", "high"].index, default="low"),
        },
        "rules": RULES,
        "records": rows,
    }


def export_markdown(ledger: EvidenceLedger, session_id: str) -> str:
    pack = export_json(ledger, session_id)
    ident = pack["identity"]
    chain = pack["chain"]
    lines = [
        f"# {TITLE}",
        "",
        f"*Generated {pack['generated_at']} by KAVACH — provable trust layer for AI agents.*",
        "",
        "## Accountability",
        "",
        f"- **Agent:** `{ident.get('agent_id', '?')}`",
        f"- **On behalf of:** `{ident.get('on_behalf_of', '?')}`",
        f"- **Task:** `{ident.get('task_id', '?')}`",
        f"- **Session:** `{session_id}`",
        f"- **Evidence chain:** {'intact ✓' if chain['ok'] else '**BROKEN** at row ' + str(chain.get('broken_at'))}"
        f" ({chain['count']} records, head `{str(chain.get('head', ''))[:16]}…`)",
        "",
        "## Summary",
        "",
        f"- Decisions: {pack['summary']['decisions']}",
        f"- Verdicts: {', '.join(f'{k} × {v}' for k, v in sorted(pack['summary']['verdicts'].items()))}",
        f"- Rules triggered: {', '.join(pack['summary']['rules_triggered']) or 'none'}",
        f"- Highest session risk: {pack['summary']['max_risk']}",
        "",
        "## Decisions",
        "",
        "| # | Tool | Verdict | Rules | Explanation | Token | Record hash |",
        "|---|------|---------|-------|-------------|-------|-------------|",
    ]
    for r in pack["records"]:
        expl = r["explanation"].replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {r['seq']} | `{r['tool']}` | **{r['verdict']}** | {', '.join(r['rule_ids']) or '—'} | {expl} "
            f"| {r['token_id'] or '—'} | `{r['hash'][:12]}` |"
        )
    lines += ["", "## Rules in force", ""]
    lines += [f"- **{k}** — {v}" for k, v in RULES.items()]
    lines += [
        "",
        "## Data protection note",
        "",
        "Arguments are stored masked. Each record keeps the SHA-256 of the exact arguments sent upstream, which "
        "equals the `args_hash` claim of the 60-second action token, so the action can be proven without "
        "retaining the personal data (DPDP Act 2023, data minimisation).",
        "",
    ]
    return "\n".join(lines)
