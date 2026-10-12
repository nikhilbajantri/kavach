"""Canonical JSON + hashing shared by the token broker, upstream verifiers and the ledger."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> str:
    """Deterministic JSON: sorted keys, no whitespace, UTF-8 preserved.

    Both sides of a hash (KAVACH and an upstream) must serialise identically,
    otherwise a legitimate token would fail the args-hash check.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def args_hash(args: dict[str, Any]) -> str:
    return sha256_hex(canonical_json(args))
