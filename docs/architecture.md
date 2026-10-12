# KAVACH architecture

```mermaid
flowchart LR
    OP([Operator<br/>"Process today's tickets"]) --> AG[Agent<br/>LLM tool-calling loop<br/><i>holds no credentials</i>]
    AG -- every tool call<br/>(MCP) --> GW

    subgraph GW[KAVACH gateway]
        direction TB
        L[1 · Label<br/>provenance ledger] --> T[2 · Type<br/>CONTROL vs CONTENT]
        T --> A[3 · Attribute<br/>normalise · match · origin]
        A --> D[4 · Decide<br/>Cedar R0–R6]
        D --> M[5 · Mint<br/>60 s Ed25519 token]
        REG[(Tool registry<br/>SHA-256 pins)] -.-> D
        DIR[(Trust directory<br/>CRM · RDAP)] -.-> D
        D --> EV[(Evidence ledger<br/>hash chain)]
        D --> APR[Approvals queue]
    end

    M -- token in _meta / Bearer --> UP
    subgraph UP[Upstream systems: verify the token]
        CRM[(CRM<br/>SQLite)]
        MAIL[(Email<br/>inbox + sink)]
        PAY[(Razorpay-style<br/>refunds API)]
    end
    UP -- results --> L
    GW -- SSE --> UI[Dashboard<br/>Next.js]
```

## Request lifecycle

1. **Label.** Every tool result is split field by field into provenance-ledger entries, each with `source`, `trust` (trusted or untrusted) and `sensitivity` (public, internal, confidential or regulated_pii). Labels are set per field: a CRM record mixes verified recipient fields (trusted), KYC fields (regulated PII) and customer-typed text (untrusted). Taint persists in storage, so an address a customer wrote stays untrusted after it is saved to the CRM.
2. **Type.** KAVACH-owned manifests (`kavach/registry/manifests.py`) mark each parameter CONTROL (who / where / how much) or CONTENT, and each tool as sink or source. Unknown tools fail closed: they are treated as sinks with every parameter CONTROL.
3. **Attribute.** For each CONTROL value, KAVACH normalises the value (NFKC, zero-width removal, homoglyph folding, Base64/hex/URL decoding, Indian numerals). It then matches it against the ledger: exact or decoded match first, then fuzzy, with numbers compared numerically. The value's origin is classified as `TRUSTED`, `UNTRUSTED_ONLY` or `UNKNOWN`. A fuzzy match never grants trust. Sinks also get a sensitivity-flow report: the share of the content's characters that come from sensitive ledger entries, plus PAN/Aadhaar patterns and a count of KYC records.
4. **Decide.** A deterministic context (origins, flow, destination trust, domain age, amount check, quarantine, session flags) is evaluated by Cedar (`policies/kavach.cedar`). Every matching rule is collected and the most severe verdict wins. A SANITISE remediation rewrites the call, and the rewritten call is evaluated again from scratch.
5. **Mint.** On ALLOW or SANITISE, the broker signs a 60-second EdDSA token bound to `tool` and `args_hash`. Upstreams hold only the public key and reject anything else with 401.

## Rules

| Rule | Condition | Verdict |
|---|---|---|
| R0 | tool manifest changed after pinning | BLOCK |
| R1 | a sink's CONTROL value is `UNTRUSTED_ONLY` | SANITISE if a safe default exists, else BLOCK |
| R2 | confidential / regulated content to an external destination | BLOCK |
| R3 | outbound destination domain < 30 days old | BLOCK |
| R4 | payment CONTROL value `UNKNOWN` (invented by the model) | ESCALATE |
| R5 | untrusted input + regulated data + external sink in one session | raise risk to high |
| R6 | refund amount not on the customer's record | ESCALATE |

## Why rephrasing does not help the attacker

No rule reads what the text *says*. The rules only consider where a value came from, where data is going, and how sensitive it is. An attacker can reword the injection endlessly, but the recipient they want still originates in their email, and that is what R1 checks.

## Components

| Path | Responsibility |
|---|---|
| `kavach/gateway.py` | the five-step pipeline, approvals, tool refresh |
| `kavach/provenance/` | ledger store and per-field labelling rules |
| `kavach/attribution/` | normalisation, matching, sensitivity flow |
| `kavach/policy/` | Cedar engine, context builder, remediation, explanations |
| `kavach/identity/` | credential broker and upstream verifier |
| `kavach/ledger/` | hash-chained evidence ledger, masking, audit export |
| `kavach/registry/` | tool typing and SHA-256 pinning |
| `kavach/mcp_bridge.py` | MCP client to upstreams; KAVACH served as an MCP server |
| `mocks/` | CRM, email, payments and RDAP mocks (HTTP + MCP) |
| `agent/` | tool-calling loop; scripted, Anthropic, OpenAI and Ollama LLMs |
| `bench/` | attack and benign suites, runner, results |
| `web/` | Next.js dashboard (SSE) |
