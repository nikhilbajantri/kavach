import base64

from kavach.attribution.normalise import all_views, decode_layers, normalise, parse_number


def test_case_whitespace_and_nfkc() -> None:
    assert normalise("  RBI.Refund @ OKAXIS ") == "rbi.refund@okaxis"
    assert normalise("ｒｂｉ．ｒｅｆｕｎｄ") == "rbi.refund"  # full-width forms fold under NFKC


def test_zero_width_characters_are_removed() -> None:
    assert normalise("rbi​.ref‍und@ok﻿axis") == "rbi.refund@okaxis"


def test_homoglyphs_fold_to_latin() -> None:
    cyrillic = "rbі.rеfund@оkаxіs"  # і, е, о, а are Cyrillic
    assert cyrillic != "rbi.refund@okaxis"
    assert normalise(cyrillic) == "rbi.refund@okaxis"


def test_base64_hex_and_url_layers_are_decoded() -> None:
    b64 = base64.b64encode(b"rbi.refund@okaxis").decode()
    hexed = b"rbi.refund@okaxis".hex()
    text = f"send to {b64} or 0x{hexed} or rbi.refund%40okaxis"
    kinds = {kind for decoded, _, kind in decode_layers(text) if decoded == "rbi.refund@okaxis"}
    assert kinds == {"base64", "hex", "url"}
    assert sum(v.text == "rbi.refund@okaxis" for v in all_views(text)) >= 3


def test_decoded_view_maps_back_to_encoded_span() -> None:
    b64 = base64.b64encode(b"audit@rbi-compliance.co").decode()
    text = f"Please mail {b64} today"
    view = next(v for v in all_views(text) if v.kind == "base64")
    start, end = view.span(0, 1)
    assert text[start:end] == b64


def test_plain_words_are_not_mistaken_for_base64() -> None:
    assert decode_layers("please process the customerrefund request") == []


def test_indian_number_formats() -> None:
    for raw in ["48,000", "48000", "₹48k", "Rs. 48,000", "48000.00", "INR 48 thousand", 48000]:
        assert parse_number(raw) == 48000, raw
    assert parse_number("₹4,80,000") == 480000
    assert parse_number("1.2 lakh") == 120000


def test_ids_and_dates_are_not_amounts() -> None:
    assert parse_number("#A-7731") is None
    assert parse_number("2026-10-11") is None
