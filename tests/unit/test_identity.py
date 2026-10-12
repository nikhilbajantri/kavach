"""Acceptance: the payments mock rejects forged, expired and arg-mismatched tokens with 401."""

import time

import httpx
import pytest

from kavach.identity.broker import CredentialBroker, Identity, TokenVerifier, load_or_generate_key
from mocks.world import World

API_KEY = "rzp_test_mock_secret"
ARGS = {"amount_inr": 48000, "recipient_upi": "ravikumar.blr@okicici", "reason": "duplicate charge"}
WHO = Identity(agent_id="support-bot-1", on_behalf_of="operator@ourbank.in", task_id="T-2026-10-12-001")


@pytest.fixture
def setup() -> tuple[CredentialBroker, World]:
    broker = CredentialBroker(load_or_generate_key(None))
    return broker, World(TokenVerifier(broker.public_key), API_KEY)


async def _post(world: World, args: dict, token: str | None, api_key: str = API_KEY) -> httpx.Response:
    async with world.payments_client() as client:
        headers = {"X-Api-Key": api_key}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        return await client.post("/refunds", json=args, headers=headers)


async def test_valid_token_is_accepted(setup) -> None:
    broker, world = setup
    resp = await _post(world, ARGS, broker.mint(WHO, "payments.refund", ARGS).token)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"].startswith("rfnd_") and body["status"] == "processed"
    assert body["amount"] == 48000 * 100
    assert body["notes"]["task_id"] == "T-2026-10-12-001"


async def test_missing_token_is_rejected(setup) -> None:
    _, world = setup
    assert (await _post(world, ARGS, None)).status_code == 401


async def test_forged_token_signed_by_another_key_is_rejected(setup) -> None:
    _, world = setup
    forger = CredentialBroker(load_or_generate_key(None))
    resp = await _post(world, ARGS, forger.mint(WHO, "payments.refund", ARGS).token)
    assert resp.status_code == 401
    assert "invalid token" in resp.json()["detail"]


async def test_expired_token_is_rejected(setup) -> None:
    broker, world = setup
    stale = broker.mint(WHO, "payments.refund", ARGS, now=time.time() - 120).token
    resp = await _post(world, ARGS, stale)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "token expired"


async def test_token_replayed_with_different_args_is_rejected(setup) -> None:
    broker, world = setup
    token = broker.mint(WHO, "payments.refund", ARGS).token
    hijacked = {**ARGS, "recipient_upi": "rbi.refund@okaxis"}
    resp = await _post(world, hijacked, token)
    assert resp.status_code == 401
    assert "args_hash" in resp.json()["detail"]


async def test_token_for_another_tool_is_rejected(setup) -> None:
    broker, world = setup
    resp = await _post(world, ARGS, broker.mint(WHO, "email.send", ARGS).token)
    assert resp.status_code == 401


async def test_wrong_merchant_key_is_rejected(setup) -> None:
    broker, world = setup
    resp = await _post(world, ARGS, broker.mint(WHO, "payments.refund", ARGS).token, api_key="stolen")
    assert resp.status_code == 401


def test_token_lifetime_is_60_seconds(setup) -> None:
    broker, _ = setup
    minted = broker.mint(WHO, "payments.refund", ARGS, now=1_000_000)
    assert minted.expires_at == 1_000_060
