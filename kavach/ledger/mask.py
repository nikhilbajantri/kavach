"""PII masking for anything that leaves the gateway for humans (UI, exports)."""

from __future__ import annotations

import re
from typing import Any

_PAN = re.compile(r"\b([A-Z]{2})[A-Z]{3}[0-9]{4}([A-Z])\b")
_AADHAAR = re.compile(r"\b[2-9][0-9]{3}[\s-]?[0-9]{4}[\s-]?([0-9]{4})\b")
_PHONE = re.compile(r"(\+91[\s-]?)?\b[6-9][0-9]{4}[\s-]?[0-9]([0-9]{4})\b")


def mask_text(text: str) -> str:
    text = _PAN.sub(lambda m: f"{m.group(1)}•••••••{m.group(2)}", text)
    text = _AADHAAR.sub(lambda m: f"XXXX-XXXX-{m.group(1)}", text)
    return _PHONE.sub(lambda m: f"{m.group(1) or ''}•••••{m.group(2)}", text)


def mask(value: Any) -> Any:
    if isinstance(value, str):
        return mask_text(value)
    if isinstance(value, dict):
        return {k: mask(v) for k, v in value.items()}
    if isinstance(value, list):
        return [mask(v) for v in value]
    return value
