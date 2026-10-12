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

## D12: Graded verdicts from Cedar

Cedar only answers permit or deny. Each rule in `policies/kavach.cedar` is therefore a `forbid` with `@rule` and `@verdict` annotations. On a deny, Cedar reports every satisfied policy, so KAVACH maps those back to their annotations, and the most severe verdict wins. R5 uses verdict `FLAG`: it raises the session's risk level without changing the verdict. A Cedar evaluation error fails closed (BLOCK).

## D13: SANITISE results are re-checked

After remediation (a refund recipient replaced with the customer's CRM-verified UPI or account), the whole pipeline re-evaluates the new arguments. A remediated call must pass on its own merits. The looked-up value is added to the provenance ledger with source `kavach.directory` (trusted), because KAVACH itself read it from the system of record. If no customer can be resolved from the ticket sender, SANITISE becomes BLOCK.

## D14: URLs inside outbound content are destinations

A link in an email body is treated as a destination (EchoLeak-style exfiltration). R3 applies to every linked domain. R2 applies only when the URL itself carries sensitive data, so an ordinary link next to a customer's own statement does not cause a false positive.

## D15: Unknown domain age is not "young"

The RDAP mock covers every domain used in the demo and the benchmark. A domain absent from the registry is reported as "age unknown" and does not trigger R3; R2 still blocks sensitive data going there. A production deployment would treat failed RDAP lookups as an ESCALATE.

## D16: Ed25519 action tokens

The broker signs tokens with EdDSA (Ed25519) rather than a shared HMAC secret. Upstream services hold only the public key, so a compromised upstream cannot mint tokens itself. If `KAVACH_SIGNING_KEY_PEM` is unset, a fresh key is generated per process.

## D17: The ledger stores masked arguments plus a hash of the raw arguments

Each evidence record keeps masked arguments, plus `args_hash`, the SHA-256 of the exact raw arguments. That hash equals the `args_hash` claim of the action token, so the ledger can prove what was executed without keeping a second copy of the PII (DPDP data minimisation). Everything sent to the browser (SSE events, approvals, alerts) passes through the same masker.

## D18: Quarantined tools show the agent their pinned description

When an upstream manifest drifts, KAVACH quarantines the tool (R0) and keeps serving the agent the manifest it pinned at registration. Without this, a poisoned description would still reach the model even though calls were blocked, and it could steer other tools. Tools that appear after pinning are quarantined and hidden until an operator re-pins. In enforce mode the gateway re-hashes upstream listings before every call; this runs before the latency timer starts, because it is upstream time.
