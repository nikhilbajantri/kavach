"""Acceptance: tampering with any ledger row makes verification fail."""

import json

import pytest

from agent.llm.scripted import load_plan
from agent.runner import build_runtime, run_scenario
from kavach.ledger.chain import EvidenceLedger
from kavach.ledger.export import TITLE, export_json, export_markdown
from kavach.ledger.mask import mask_text


@pytest.fixture
async def ledger_with_run() -> tuple[EvidenceLedger, str]:
    ledger = EvidenceLedger()
    rt = build_runtime(enabled=True, ledger=ledger)
    outcome, _ = await run_scenario(load_plan("nbfc_2am"), enabled=True, runtime=rt)
    return ledger, outcome.transcript.session_id


async def test_chain_is_intact_after_a_run(ledger_with_run) -> None:
    ledger, _ = ledger_with_run
    result = ledger.verify()
    assert result["ok"] and result["count"] == 18


@pytest.mark.parametrize("seq", [1, 9, 18])
async def test_editing_any_row_breaks_the_chain(ledger_with_run, seq: int) -> None:
    ledger, _ = ledger_with_run
    record = json.loads(ledger.db.execute("SELECT record FROM ledger WHERE seq = ?", (seq,)).fetchone()[0])
    record["verdict"] = "ALLOW" if record["verdict"] != "ALLOW" else "BLOCK"
    ledger.db.execute("UPDATE ledger SET record = ? WHERE seq = ?", (json.dumps(record), seq))
    result = ledger.verify()
    assert not result["ok"]
    assert result["broken_at"] == seq


async def test_deleting_a_row_breaks_the_chain(ledger_with_run) -> None:
    ledger, _ = ledger_with_run
    ledger.db.execute("DELETE FROM ledger WHERE seq = 5")
    assert not ledger.verify()["ok"]


async def test_ledger_never_stores_raw_pan(ledger_with_run) -> None:
    ledger, _ = ledger_with_run
    dump = "\n".join(r[0] for r in ledger.db.execute("SELECT record FROM ledger"))
    assert "BQRPK4821M" not in dump  # Ravi's PAN appears in the blocked KYC email body
    assert "BQ•••••••M" in dump


async def test_audit_export(ledger_with_run) -> None:
    ledger, session_id = ledger_with_run
    pack = export_json(ledger, session_id)
    assert pack["title"] == TITLE and pack["chain"]["ok"]
    assert pack["summary"]["verdicts"] == {"ALLOW": 16, "SANITISE": 1, "BLOCK": 1}
    md = export_markdown(ledger, session_id)
    assert md.startswith(f"# {TITLE}")
    assert "`T-2026-10-12-001`" in md and "intact ✓" in md


def test_masking() -> None:
    assert mask_text("PAN BQRPK4821M, +91 98450 31277") == "PAN BQ•••••••M, +91 •••••1277"
