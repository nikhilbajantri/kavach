# Design decisions

This file records spec ambiguities, and how they were resolved, while building KAVACH. Each entry gives the decision first, then the reasoning.

## D1: Repo root is the working folder

The repo is built in the session folder (`DevHost`) and not in a separate `kavach/` folder. The layout matches spec §8 relative to the repo root, so the gateway Python package sits at `./kavach/`.

## D2: `tasks.py` alongside the `Makefile`

The dev machine (Windows) has no `make`. `python tasks.py <target>` mirrors every Makefile target. Docker, Linux and CI use the Makefile.

## D3: Python 3.12

The spec asks for Python 3.11+. Only 3.12 was available, so development, CI and the Docker image all use 3.12. `pyproject.toml` still declares `>=3.11`.

## D4: SQLite via the stdlib `sqlite3` module

The stdlib module is used directly instead of SQLModel. The schemas are tiny, and this drops a dependency and an ORM layer from the hot path, where the decision-latency target is under 10 ms.

## D5: Cedar is real

`cedarpy` 4.x installed cleanly on Windows/py3.12, so the YAML fallback evaluator is not needed. Rules live in `policies/*.cedar`.

## D6: `crm.update_address` added

The spec's tool list cannot complete the benign "address change" ticket, so this tool was added. It is a sink: `customer_id` is a CONTROL parameter and `new_address` is CONTENT. That split also demonstrates the core rule: untrusted text may be *content*, but never *control*.

## D7: MCP in both directions, token in `_meta`

The `mcp` SDK 2.x lowlevel `Server` with `Client` works in-process and over URLs, so no HTTP fallback was needed. KAVACH's action token travels in the MCP request `_meta` under `kavach/token`. Upstream MCP servers verify it exactly as the HTTP payments API does. `InProcessTransport` remains the default for tests and the benchmark because it is faster. `MCPTransport` runs the same scenario end-to-end (see `tests/integration/test_mcp.py`).

## D8: Fuzzy matches can never make a value TRUSTED

Fuzzy matching (`rapidfuzz.partial_ratio ≥ 90`) only ever counts as evidence that a value came from untrusted content. Otherwise a typosquatted UPI like `ravikumar.blr@okicic1` would borrow trust from the verified `ravikumar.blr@okicici`. A value becomes TRUSTED only through an exact, decoded or numeric match. This is the fail-closed choice.

## D9: Provenance persists with stored data

When `crm.update_address` writes a customer-typed address, the CRM stores `address_provenance = customer_supplied`. The labeller then marks that field untrusted on every later read, so attacker text cannot be laundered into "trusted CRM data" by writing it to the CRM first.

## D10: Tool receipts never launder arguments

Refund and send receipts echo their request fields, such as the recipient. Only the fields our own systems generate (`id`, `status`) are labelled trusted.

## D11: Flow metric is character coverage

"≥ 30% containment" is defined as the fraction of the outgoing content's characters covered by an 8-character shingle that also occurs in sensitive ledger content. Shingle *share* was rejected: separators between short fields such as PAN numbers drown out the signal. KYC record counting (`records`) is a separate, exact check used for explanations ("50 customer records").
