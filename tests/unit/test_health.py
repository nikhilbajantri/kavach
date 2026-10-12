from pathlib import Path

from fastapi.testclient import TestClient

from kavach.api.main import create_app


def test_health_ok(tmp_path: Path) -> None:
    with TestClient(create_app(str(tmp_path / "ledger.db"))) as client:
        body = client.get("/health").json()
    assert body["status"] == "ok"
    assert "kavach_enabled" in body
