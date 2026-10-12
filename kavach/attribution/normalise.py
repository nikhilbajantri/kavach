"""Canonicalise text so that disguised values still match their source.

Attackers hide a recipient by Base64-encoding it, swapping Latin letters for
Cyrillic look-alikes, sprinkling zero-width characters, or writing ₹48k instead
of 48000. Every view produced here keeps a map back to the original offsets,
so the dashboard can highlight the exact span the value came from.
"""

from __future__ import annotations

import base64
import binascii
import re
import unicodedata
import urllib.parse
from dataclasses import dataclass

ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍‎‏⁠⁡⁢⁣⁤﻿­᠎"))

# Confusables that NFKC does not fold (Cyrillic, Greek, Armenian look-alikes → Latin).
HOMOGLYPHS = str.maketrans(
    {
        "а": "a", "в": "b", "е": "e", "ё": "e", "к": "k", "м": "m", "н": "h", "о": "o", "р": "p",
        "с": "c", "т": "t", "у": "y", "х": "x", "ѕ": "s", "і": "i", "ї": "i", "ј": "j", "ԁ": "d",
        "ɡ": "g", "һ": "h", "ӏ": "l", "ԛ": "q", "ԝ": "w", "ս": "u", "օ": "o", "ı": "i",
        "А": "a", "В": "b", "Е": "e", "К": "k", "М": "m", "Н": "h", "О": "o", "Р": "p", "С": "c",
        "Т": "t", "Х": "x", "У": "y", "І": "i", "Ј": "j", "Ѕ": "s",
        "α": "a", "β": "b", "ε": "e", "ι": "i", "κ": "k", "ν": "v", "ο": "o", "ρ": "p", "τ": "t",
        "υ": "u", "χ": "x", "Α": "a", "Β": "b", "Ε": "e", "Ζ": "z", "Η": "h", "Ι": "i", "Κ": "k",
        "Μ": "m", "Ν": "n", "Ο": "o", "Ρ": "p", "Τ": "t", "Υ": "y", "Χ": "x",
    }
)  # fmt: skip


@dataclass(frozen=True)
class View:
    """A normalised rendering of (part of) a text, mappable back to original offsets."""

    text: str
    index: tuple[int, ...]  # index[i] = offset in the original text of normalised char i
    kind: str = "plain"  # plain | base64 | url | hex
    origin_span: tuple[int, int] | None = None  # for decoded views: the encoded token's span

    def span(self, start: int, end: int) -> tuple[int, int]:
        if self.origin_span is not None:
            return self.origin_span
        if not self.index or start >= len(self.index):
            return (0, 0)
        return (self.index[start], self.index[max(start, end - 1)] + 1)


_FOLD_CACHE: dict[str, str] = {}


def _fold_char(ch: str) -> str:
    folded = _FOLD_CACHE.get(ch)
    if folded is None:
        raw = unicodedata.normalize("NFKC", ch).translate(ZERO_WIDTH).translate(HOMOGLYPHS).lower()
        folded = _FOLD_CACHE[ch] = "".join(c for c in raw if not c.isspace())
    return folded


def normalise_with_map(text: str) -> tuple[str, tuple[int, ...]]:
    """Lowercase, NFKC, drop zero-width + whitespace, fold homoglyphs; keep an offset map."""
    if text.isascii():  # fast path: nothing to fold beyond case and whitespace
        index = tuple(i for i, ch in enumerate(text) if not ch.isspace())
        return "".join(text.split()).lower(), index
    out: list[str] = []
    index_list: list[int] = []
    for i, ch in enumerate(text):
        folded = _fold_char(ch)
        out.append(folded)
        index_list.extend([i] * len(folded))
    return "".join(out), tuple(index_list)


_NEEDS_FOLD = re.compile("[" + re.escape("".join(chr(c) for c in (*ZERO_WIDTH, *HOMOGLYPHS))) + "]")


def normalise(text: str) -> str:
    """Whole-string variant (C-speed) used on the decision hot path."""
    if not text.isascii():
        text = unicodedata.normalize("NFKC", text)
        if _NEEDS_FOLD.search(text):  # translate() is slow; only pay for it when needed
            text = text.translate(ZERO_WIDTH).translate(HOMOGLYPHS)
    return "".join(text.lower().split())


# ------------------------------------------------------------- decoding layers
_B64 = re.compile(r"(?<![A-Za-z0-9+/_-])[A-Za-z0-9+/_-]{12,}={0,2}(?![A-Za-z0-9+/=_-])")
_HEX = re.compile(r"(?<![0-9A-Fa-f])(?:0x)?((?:[0-9A-Fa-f]{2}){5,})(?![0-9A-Fa-f])")
_URLENC = re.compile(r"(?:%[0-9A-Fa-f]{2}|[^\s%<>\"'])*%[0-9A-Fa-f]{2}(?:%[0-9A-Fa-f]{2}|[^\s%<>\"'])*")


def _printable(raw: bytes) -> str | None:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if len(text) < 4:
        return None
    good = sum(ch.isprintable() and not unicodedata.category(ch).startswith("C") for ch in text)
    return text if good / len(text) >= 0.9 else None


def _try_b64(token: str) -> str | None:
    if token.isdigit() or (token.isalpha() and (token.islower() or token.isupper() or token.istitle())):
        return None  # plain words and numbers are valid Base64 alphabets but almost never encodings
    padded = token + "=" * (-len(token) % 4)
    for alt in (padded, padded.replace("-", "+").replace("_", "/")):
        try:
            decoded = _printable(base64.b64decode(alt, validate=True))
        except (binascii.Error, ValueError):
            continue
        if decoded:
            return decoded
    return None


def decode_layers(text: str) -> list[tuple[str, tuple[int, int], str]]:
    """Decoded Base64 / hex / URL-encoded tokens as (decoded text, encoded span, kind)."""
    found: list[tuple[str, tuple[int, int], str]] = []
    for m in _B64.finditer(text):
        if (dec := _try_b64(m.group(0))) is not None:
            found.append((dec, m.span(), "base64"))
    for m in _HEX.finditer(text):
        try:
            dec = _printable(bytes.fromhex(m.group(1)))
        except ValueError:
            dec = None
        if dec:
            found.append((dec, m.span(), "hex"))
    for m in _URLENC.finditer(text) if "%" in text else ():
        dec = urllib.parse.unquote_plus(m.group(0))
        if dec != m.group(0):
            found.append((dec, m.span(), "url"))
    return found


def decoded_views(
    text: str, depth: int = 2, layers: list[tuple[str, tuple[int, int], str]] | None = None
) -> list[View]:
    """Normalised views of every decoded layer (recursive, bounded depth)."""
    views: list[View] = []
    for decoded, span, kind in decode_layers(text) if layers is None else layers:
        views.append(View(text=normalise(decoded), index=(), kind=kind, origin_span=span))
        if depth > 1:
            for inner in decoded_views(decoded, depth - 1):
                views.append(View(text=inner.text, index=(), kind=f"{kind}+{inner.kind}", origin_span=span))
    return views


def all_views(
    text: str, *, with_index: bool = True, layers: list[tuple[str, tuple[int, int], str]] | None = None
) -> list[View]:
    """Plain view plus decoded views. Skip the offset map when no span will be reported."""
    if with_index:
        norm, index = normalise_with_map(text)
    else:
        norm, index = normalise(text), ()
    return [View(text=norm, index=index), *decoded_views(text, layers=layers)]


# ------------------------------------------------------------------ numbers
_NUMBER = re.compile(
    r"(?<![\w\-/:+.#])(?:(?:₹|rs\.?|inr)\s*)?(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|lakhs?|lacs?|l|cr|crores?)?(?![\w\-/:])",
    re.IGNORECASE,
)
_MULTIPLIER = {"k": 1e3, "thousand": 1e3, "l": 1e5, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5}
_MULTIPLIER |= {"cr": 1e7, "crore": 1e7, "crores": 1e7}


def parse_number(raw: object) -> float | None:
    """Parse '48,000', '₹48k', '4,80,000', '48000.00', 48000 → float, or None."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int | float):
        return float(raw)
    found = extract_numbers(str(raw))
    return found[0][0] if len(found) == 1 else None


def extract_numbers(text: str) -> list[tuple[float, tuple[int, int]]]:
    """All monetary-looking numbers with their spans. Dates, phone numbers and ids are skipped."""
    out: list[tuple[float, tuple[int, int]]] = []
    for m in _NUMBER.finditer(text):
        try:
            value = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        unit = (m.group(2) or "").lower()
        out.append((value * _MULTIPLIER.get(unit, 1.0), m.span()))
    return out
