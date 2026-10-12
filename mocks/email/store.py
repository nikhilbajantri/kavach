"""Mailbox: an inbox to read from and an outbound sink. Nothing is ever really sent."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from mocks.email.inbox import InboundEmail, default_inbox


class SentEmail(BaseModel):
    id: str
    to: str
    subject: str
    body: str
    sent_at: str
    token_id: str | None = None


class Mailbox:
    def __init__(self, inbox: list[InboundEmail] | None = None) -> None:
        self.inbox = inbox if inbox is not None else default_inbox()
        self.sent: list[SentEmail] = []
        self._ids = itertools.count(1)

    def list_inbox(self) -> list[dict[str, Any]]:
        return [
            {
                "id": m.id,
                "from": m.from_addr,
                "from_name": m.from_name,
                "subject": m.subject,
                "received_at": m.received_at,
            }
            for m in self.inbox
        ]

    def read(self, message_id: str) -> dict[str, Any] | None:
        for m in self.inbox:
            if m.id == message_id:
                return {
                    "id": m.id,
                    "from": m.from_addr,
                    "from_name": m.from_name,
                    "subject": m.subject,
                    "received_at": m.received_at,
                    "body": m.body_text,
                }
        return None

    def get_html(self, message_id: str) -> str | None:
        return next((m.body_html for m in self.inbox if m.id == message_id), None)

    def send(self, to: str, subject: str, body: str, token_id: str | None = None) -> SentEmail:
        msg = SentEmail(
            id=f"out_{next(self._ids):04d}",
            to=to.strip(),
            subject=subject,
            body=body,
            sent_at=datetime.now(UTC).isoformat(),
            token_id=token_id,
        )
        self.sent.append(msg)
        return msg
