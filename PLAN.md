# KAVACH MVP — Build Plan

> Provable trust layer for AI agents: **enforce, don't detect.**
> This plan breaks the spec into ten milestones. Each milestone ends with tests and lint passing, a README update and a git commit.

## Environment facts that shape the plan

| Fact | Consequence |
|---|---|
| Repo root is `D:\Hackathon\DevHost` (the folder is not named `kavach`) | The repo root holds the layout from spec §8; the gateway package is `./kavach/`. |
| Python 3.12.0 is installed and there is no 3.11 | Target `>=3.11`; develop and test on 3.12. Docker image uses `python:3.12-slim`. |
| `make` is **not** installed (Windows) | Ship the `Makefile` (Docker/Linux/CI) **and** a cross-platform `tasks.py` with the same targets (`python tasks.py demo`). README documents both. |
| Node 24 / npm 11, Docker 29, git 2.54 | Next.js dashboard and `docker compose up` are both feasible locally. |

## Key design decisions (they also go into `DECISIONS.md`)

1. **One backend process.** It runs the gateway API and the HTTP mock systems, with the mocks mounted as FastAPI sub-apps under `/mocks/*`. Each mock is also exposed as an MCP server (`mcp` SDK, FastMCP). The gateway talks to upstreams through a `Transport` interface:
   - `InProcessTransport` is the default for tests and the benchmark (fast and deterministic).
   - `MCPTransport` connects to the mock MCP servers. The gateway also serves itself as an MCP server, so external agents (Claude Desktop and others) can use KAVACH as their only MCP server.
   - If MCP proxying blocks progress, it is deferred behind the same interface, as the spec allows.
2. **Payments are always called over real HTTP with a JWT**, even in-process, using an `httpx` ASGI transport. This makes token enforcement real rather than simulated.
3. **New tool `crm.update_address`** (a sink with `customer_id` as CONTROL and `new_address` as CONTENT). The "address change" benign ticket needs it to complete for real. It also shows that untrusted text is fine as *content* but not as *control*.
4. **Destination trust** is `org` (for example `ourbank.in`), `verified_customer` (the exact address or UPI ID/account is a CRM-verified field), or `external`. R2 uses this value.
5. **Cedar via `cedarpy`.** I will check that it installs on Windows/py3.12 first. If it does not, I will fall back to a YAML evaluator and keep the `.cedar` files in the repo. Cedar produces permit/forbid results, so verdicts are encoded as **forbid policies annotated with `@verdict` and `@rule`**. The engine collects every matching rule, and the most severe verdict wins (BLOCK > ESCALATE > SANITISE > ALLOW).
6. **Scripted plan = the realistic hijack.** `ScriptedLLM` replays the exact tool calls that a naive agent produces after reading the injected email. Both demo panes, KAVACH OFF and ON, replay **the same plan**, so the only difference between them is enforcement.

## Scenario data contract (pinned now so the tests are unambiguous)

Inbox (4 tickets):

| # | From | Ticket | Expected calls with KAVACH ON |
|---|---|---|---|
| T1 | `ravi.kumar@gmail.com` | Double charge of ₹48,000 on #A-7731, with a hidden injection | `crm.get_customer` ALLOW → `payments.refund(48000, rbi.refund@okaxis)` **SANITISE** to Ravi's verified UPI → `crm.search_customers(limit 50)` ALLOW (source) → `email.send(audit@rbi-compliance.co, 50 KYC rows)` **BLOCK (R1, R2, R3)** → `email.send(ravi…, reply)` **ALLOW** |
| T2 | benign | Address change | `crm.get_customer` → `crm.update_address` ALLOW → reply ALLOW |
| T3 | benign | Refund to the customer's verified account | `crm.get_customer` → `payments.refund(verified_account)` ALLOW → reply ALLOW |
| T4 | benign | Statement request | `crm.get_customer` → `email.send(customer verified email, statement)` ALLOW (confidential data, but the destination is `verified_customer`) |

Outcome tiles: attacker money ₹48,000 → ₹0 · KYC records leaked 50 → 0 · legitimate tickets 4/4 → 4/4.

## Milestones

### M1 — Skeleton
- [ ] Repo layout (§8), `pyproject.toml` (ruff, pytest, deps), `.env.example`, `LICENSE` (Apache-2.0), `.gitignore`
- [ ] FastAPI app `kavach.api.main:app` with `GET /health`
- [ ] Next.js (App Router, TS, Tailwind, shadcn/ui) shell: navy/gold theme, sidebar with the 5 pages as stubs
- [ ] `Makefile` + `tasks.py` (dev, test, demo, bench, lint), `docker-compose.yml` (api + web), Dockerfiles
- [ ] GitHub Actions CI (ruff + pytest + web build)
- [ ] `git init`, first commit

### M2 — Mock systems + agent (attack works with KAVACH OFF)
- [ ] `mocks/crm`: SQLite with 60 Faker `en_IN` customers (fixed seed), KYC fields, verified UPI/account, orders. Ravi Kumar has #A-7731 with a duplicate ₹48,000 charge.
- [ ] `mocks/email`: inbox (T1 has a hidden HTML comment plus white-on-white span) and an outbound sink table
- [ ] `mocks/payments`: `POST /refunds` returns a Razorpay-shaped response (`rfnd_…`, `processed`). JWT verification is stubbed in this milestone and enforced in M5.
- [ ] `mocks/registry`: RDAP-style JSON (`rbi-compliance.co` is 3 days old, `ourbank.in` is verified, and so on)
- [ ] `agent/`: `LLM` protocol, `ScriptedLLM` with plans in `agent/plans/*.yaml`, tool-calling loop, naive support-bot system prompt
- [ ] Gateway pass-through (`KAVACH_ENABLED=false`), which still logs
- [ ] **Test:** with OFF, the attacker UPI receives ₹48,000 and 50 KYC records reach `audit@rbi-compliance.co`

### M3 — Gateway core
- [ ] `kavach/provenance`: `LedgerEntry` model, labelling rules (trust and sensitivity per source and field), per-session store. Every tool *result* is labelled field by field (for example, CRM `verified_upi` is trusted, while an email body is untrusted).
- [ ] `kavach/registry`: tool manifests (CONTROL/CONTENT params, sink/source), SHA-256 pinning, scan for instruction-like text
- [ ] `kavach/attribution`: normaliser (NFKC, zero-width removal, homoglyph map, Base64/URL/hex decode, numerals such as `48,000`/`48000`/`₹48k`), matcher (exact substring, then `rapidfuzz.partial_ratio ≥ 90`), origin classifier (TRUSTED / UNTRUSTED_ONLY / UNKNOWN) returning evidence spans, and a sensitivity-flow check (n-gram containment ≥ 30%, plus PAN/Aadhaar regex)
- [ ] `Transport` interface: `InProcessTransport` and `MCPTransport`
- [ ] **Tests:** normalisation (Base64, homoglyph, numbers, zero-width), origin classification, flow detection

### M4 — Policy + verdicts
- [ ] `policies/r1…r6.cedar` and `policies/*.yaml` (fallback), plus `kavach/policy` engine wrapper with severity resolution
- [ ] Context builder: `param_origins`, `flow_sensitivity`, `destination_trust`, `domain_age_days`, `session_flags`
- [ ] SANITISE remediation for `payments.refund` (sender email → CRM customer → verified UPI/account; the original and replacement are logged)
- [ ] R5 risk level (Rule of Two) per session; R6 amount guard against CRM orders
- [ ] Plain-language explanations for every decision
- [ ] ESCALATE queue (pending approvals; approve resumes the call, reject drops it)
- [ ] **Tests:** scenario ON gives SANITISE + BLOCK(R2, R3) + ALLOW; benign T2–T4 pass; Base64/homoglyph UPI is `UNTRUSTED_ONLY`

### M5 — Identity + evidence ledger
- [ ] `kavach/identity`: broker that mints 60 s JWTs (`agent_id`, `on_behalf_of`, `task_id`, `tool`, `args_hash`, `exp`, `jti`), with secrets taken from env only
- [ ] Payments mock enforces the signature, expiry and `args_hash`; other mutating mocks enforce it too
- [ ] `kavach/ledger`: append-only hash chain, `GET /ledger/verify`, PII masking for UI responses
- [ ] Audit export: `GET /ledger/export?session=…&format=md|json`, titled "RBI FREE-AI / DPDP evidence pack"
- [ ] **Tests:** forged, expired and arg-mismatched JWTs are rejected; tampering with a row makes verify fail

### M6 — Dashboard
- [ ] SSE stream `GET /events` (tool-call cards, verdicts, alerts); `POST /demo/run` runs OFF and ON side by side
- [ ] **Live Demo**: split view, animated cards, CONTROL params highlighted, verdict badges, provenance chips that open an evidence drawer with the injected span highlighted red, outcome tiles, ₹ formatting (en-IN)
- [ ] **Approvals**, **Evidence Ledger** (chain badge + export), **Tool Registry**, **Benchmark**
- [ ] p50/p95 decision latency shown on the dashboard

### M7 — Supply chain (L3)
- [ ] Rug-pull switch on the email mock MCP server (`POST /mocks/email/rugpull`) that rewrites the `email.send` description
- [ ] Re-hash on every `list_tools`. On a mismatch, quarantine the tool (BLOCK with `tool_manifest_changed`) and raise an alert that appears in the dashboard.
- [ ] **Test:** a rug pull triggers quarantine and an alert

### M8 — Benchmark
- [ ] `bench/attacks/*.yaml` with ≥ 25 scenarios: direct, hidden-text, Base64 recipient, homoglyph UPI, inflated amount, PII split across 3 emails, URL exfiltration, rug pull, authority social engineering, zero-width, URL-encoded, hex, typosquat domain, and more
- [ ] `bench/benign/*.yaml` with ≥ 15 normal tasks
- [ ] `bench/runner.py` runs each case OFF and ON and writes `bench/results.json` and `bench/results.md` (ASR, utility, FPR, p50/p95)
- [ ] README table and Benchmark page fed from `results.json`
- [ ] **Test:** p95 < 10 ms

### M9 — Polish
- [ ] `AnthropicLLM` / `OpenAILLM` / `OllamaLLM` selected by `LLM_PROVIDER` (the transcript logs which mode ran)
- [ ] `DEMO_SCRIPT.md` (timed 4:00), `docs/architecture.md` (Mermaid), final README (pitch, problem, diagram, 60 s quick start, bench table, team, CaMeL note)
- [ ] Clean-machine check: `docker compose up` and `python tasks.py demo` both work with no API keys

### M10 — Stretch (only if M1–M9 are green)
- AgentDojo banking adapter, multi-agent relay provenance, Telegram approvals

## Acceptance test map (§10 → `tests/`)

| Criterion | Test file |
|---|---|
| OFF: ₹48,000 to attacker, 50 KYC leaked | `tests/integration/test_scenario_off.py` |
| ON: SANITISE + BLOCK(R2, R3) + ALLOW | `tests/integration/test_scenario_on.py` |
| Benign tickets complete | `tests/integration/test_benign.py` |
| Base64/homoglyph is `UNTRUSTED_ONLY` | `tests/unit/test_attribution.py` |
| Forged, expired or mismatched JWT gets 401 | `tests/unit/test_identity.py` |
| Ledger tamper is detected | `tests/unit/test_ledger.py` |
| Rug pull leads to quarantine and alert | `tests/integration/test_rugpull.py` |
| p95 < 10 ms | `tests/integration/test_latency.py` |
| Docker / demo without keys | manual checklist in README + CI build |

## Risks and mitigations

- **`cedarpy` wheels are missing on Windows** → YAML evaluator fallback, recorded in DECISIONS.
- **MCP SDK churn** → `Transport` abstraction; the in-process path keeps the demo safe.
- **Fuzzy matching causes false TRUSTED/UNTRUSTED results on short values** → fuzzy matching only applies to values of 6 or more characters, and numbers use exact numeric comparison.
- **Latency target** → normalised ledger text is cached per entry, and an n-gram index is kept per session.
