"""In-process pub/sub for Server-Sent Events, with replay so late subscribers catch up."""

from __future__ import annotations

import asyncio
import itertools
import json
import time
from collections import deque
from collections.abc import AsyncIterator
from typing import Any

from kavach.ledger.mask import mask


class EventBus:
    def __init__(self, history: int = 2000) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._history: deque[dict[str, Any]] = deque(maxlen=history)
        self._seq = itertools.count(1)

    def publish(self, kind: str, data: dict[str, Any], **tags: Any) -> dict[str, Any]:
        # Everything that leaves the gateway for a browser is PII-masked.
        event = {"seq": next(self._seq), "ts": time.time(), "kind": kind, **tags, "data": mask(data)}
        self._history.append(event)
        for queue in list(self._subscribers):
            queue.put_nowait(event)
        return event

    def history(self, since: int = 0) -> list[dict[str, Any]]:
        return [e for e in self._history if e["seq"] > since]

    async def stream(self, since: int = 0, heartbeat: float = 15.0) -> AsyncIterator[str]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers.add(queue)
        try:
            for event in self.history(since):
                yield _sse(event)
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=heartbeat)
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                if event["seq"] > since:
                    yield _sse(event)
        finally:
            self._subscribers.discard(queue)


def _sse(event: dict[str, Any]) -> str:
    # No `event:` line: every message reaches EventSource.onmessage; the kind is in the payload.
    return f"id: {event['seq']}\ndata:{json.dumps(event, ensure_ascii=False, default=str)}\n\n"
