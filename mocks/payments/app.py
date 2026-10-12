"""Razorpay-style refunds API. Refuses any request without a valid KAVACH action token.

Two credentials are required and the agent holds neither:
  * `X-Api-Key`: the upstream merchant secret, which only KAVACH reads from env.
  * `Authorization: Bearer <jwt>`: a 60 s token bound to this exact refund.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, model_validator

from kavach.identity.broker import TokenError, TokenVerifier

TOOL_NAME = "payments.refund"


class RefundRequest(BaseModel):
    amount_inr: int
    recipient_upi: str | None = None
    recipient_account: str | None = None
    reason: str = ""

    @model_validator(mode="after")
    def _one_recipient(self) -> RefundRequest:
        if not (self.recipient_upi or self.recipient_account):
            raise ValueError("recipient_upi or recipient_account is required")
        return self


class PaymentsLedger:
    def __init__(self) -> None:
        self.refunds: list[dict[str, Any]] = []


def create_payments_app(ledger: PaymentsLedger, verifier: TokenVerifier, api_key: str) -> FastAPI:
    app = FastAPI(title="Mock Razorpay Refunds")

    @app.post("/refunds")
    def create_refund(
        body: RefundRequest,
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None),
    ) -> dict[str, Any]:
        if x_api_key != api_key:
            raise HTTPException(status_code=401, detail="invalid merchant API key")
        token = authorization.removeprefix("Bearer ").strip() if authorization else None
        args = body.model_dump(exclude_none=True)
        try:
            claims = verifier.verify(token, TOOL_NAME, args)
        except TokenError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        refund = {
            "id": f"rfnd_{uuid.uuid4().hex[:14]}",
            "entity": "refund",
            "amount": body.amount_inr * 100,  # Razorpay reports paise
            "currency": "INR",
            "status": "processed",
            "speed_processed": "instant",
            "recipient": body.recipient_upi or body.recipient_account,
            "notes": {"reason": body.reason, "task_id": claims["task_id"], "kavach_token": claims["jti"]},
            "created_at": int(time.time()),
        }
        ledger.refunds.append(refund)
        return refund

    @app.get("/refunds")
    def list_refunds() -> dict[str, Any]:
        return {"entity": "collection", "count": len(ledger.refunds), "items": ledger.refunds}

    return app
