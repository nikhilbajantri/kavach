from fastapi.testclient import TestClient

from kavach.api.main import create_app


def test_health_ok() -> None:
    client = TestClient(create_app())
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert "kavach_enabled" in body
