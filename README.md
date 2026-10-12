# KAVACH — the provable trust layer for AI agents

> **Enforce, don't detect.** KAVACH tracks the provenance of every value an AI agent uses. Deterministic policy, running outside the LLM, guarantees that untrusted data can never choose *who / where / how much* in a privileged action.

![KAVACH dashboard](docs/screenshot.png)

## The problem

- **L1: anything an agent reads can command it.** Prompt injection hides inside emails, web pages and tickets (EchoLeak, ForcedLeak).
- **L2: agents act with the user's full identity.** A hijacked agent holding long-lived keys can do anything the user can.
- **L3: tools change underneath the agent.** MCP tool descriptions can hide instructions or be rewritten after approval ("rug pull").

## Quick start (60 seconds, no API key)

```bash
# Docker
docker compose up            # dashboard: http://localhost:3000, API: http://localhost:8000

# or locally (Python 3.11+, Node 20+)
python -m venv .venv && .venv/Scripts/pip install -e ".[dev]"   # use .venv/bin/pip on macOS/Linux
python tasks.py demo         # same targets as the Makefile: dev | test | lint | demo | bench
```

## Status

Building milestone by milestone. See [PLAN.md](PLAN.md).

- [x] M1: skeleton (FastAPI health check, Next.js shell, CI, Docker)
- [x] M2: mock systems (CRM with 60 customers, inbox, Razorpay-style refunds that need a token, RDAP registry) plus a scripted agent. With KAVACH OFF, the attack succeeds: ₹48,000 goes to the attacker and 50 KYC records leak.
- [x] M3: gateway core: provenance ledger, per-field labelling, CONTROL/CONTENT tool typing, Argument Provenance Attribution (handles Base64, hex, URL encoding, homoglyphs, zero-width characters and ₹ numerals) and sensitivity-flow detection. Runs over real MCP in both directions.
- [x] M4: Cedar policies R0–R6, SANITISE remediation, plain-language explanations and a human-approval queue. With KAVACH ON, the refund is SANITISED to Ravi's verified UPI, the KYC export is BLOCKED (R1, R2, R3) and the customer reply is ALLOWED. Result: ₹0 lost, 0 records leaked, 4/4 tickets completed.
- [x] M5: Ed25519 action tokens (60 s, bound to the exact arguments) that upstreams verify; a hash-chained evidence ledger with masked PII and `/ledger/verify`; an "RBI FREE-AI / DPDP evidence pack" export; the dashboard API with an SSE stream.
- [x] M6: dashboard. Live Demo split view: streaming cards, CONTROL params highlighted, provenance chips that open an evidence drawer with the injected span highlighted, outcome tiles, ₹ formatting. Also: Approvals (approve or reject; the decision itself is ledgered) and the Evidence Ledger (chain badge, per-session evidence-pack export).

## Team

Nikhil Bajantri, Srushti Sankpal, Arsh Tomar, Likhita Naik (Srinivas Institute of Technology)

*Inspired by Google DeepMind's CaMeL research; KAVACH productises provenance enforcement as a drop-in MCP gateway.*

## License

Apache-2.0
