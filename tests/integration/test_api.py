"""API surface used by the dashboard: demo run, ledger verify/export, approvals."""

import time
from pathlib import Path

from fastapi.testclient import TestClient

from kavach.api.main import create_app


def _wait_finished(client: TestClient, run_id: str, timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = client.get(f"/demo/runs/{run_id}").json()
        if run["status"] != "running":
            return run
        time.sleep(0.05)
    raise AssertionError("demo run did not finish")


def test_demo_run_ledger_and_export(tmp_path: Path) -> None:
    with TestClient(create_app(str(tmp_path / "ledger.db"))) as client:
        run_id = client.post("/demo/run", json={"pace": 0}).json()["run_id"]
        run = _wait_finished(client, run_id)
        assert run["status"] == "finished"
        off, on = run["lanes"]["off"], run["lanes"]["on"]
        assert (off["money_to_attacker_inr"], on["money_to_attacker_inr"]) == (48000, 0)
        assert (off["kyc_records_leaked"], on["kyc_records_leaked"]) == (50, 0)
        assert off["tasks_completed"] == on["tasks_completed"] == 4

        verify = client.get("/ledger/verify").json()
        assert verify["ok"] and verify["count"] == 36

        events = client.get("/demo/last").json()["events"]
        kinds = {e["kind"] for e in events}
        assert {"run_started", "thought", "decision", "alert", "run_finished"} <= kinds
        assert all("BQRPK4821M" not in str(e) for e in events)  # PII masked on the wire

        md = client.get("/ledger/export", params={"session": on["session_id"]}).text
        assert md.startswith("# RBI FREE-AI / DPDP evidence pack")

        blocked = next(
            e
            for e in events
            if e["kind"] == "decision" and e["lane"] == "on" and e["data"]["decision"]["verdict"] == "BLOCK"
        )
        evidence = blocked["data"]["decision"]["attributions"][0]["evidence"][0]
        entry = client.get(f"/provenance/{on['session_id']}/{evidence['entry_id']}").json()
        start, end = evidence["span"]
        assert entry["text"][start:end] == "audit@rbi-compliance.co"

        lat = client.get("/metrics/latency").json()
        assert lat["count"] == 18 and lat["p95_ms"] < 10


def test_settings_toggle(tmp_path: Path) -> None:
    with TestClient(create_app(str(tmp_path / "ledger.db"))) as client:
        assert client.post("/settings", json={"kavach_enabled": False}).json() == {"kavach_enabled": False}
        assert client.get("/health").json()["kavach_enabled"] is False
