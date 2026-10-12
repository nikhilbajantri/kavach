# KAVACH: 4-minute demo video script

**Setup before recording**
- Run `python tasks.py demo` (or `docker compose up`). The dashboard is at http://localhost:3000.
- Use a 1600 × 900 browser window. Hide the bookmarks bar.
- Select the **Demo** pace. Open the Live Demo page and have the Tool Registry, Evidence Ledger and Benchmark pages ready in tabs.
- Run `make bench` once beforehand so the Benchmark page has numbers.

---

## 0:00–0:30: The problem

**Screen:** the Live Demo page, before running.

> "AI agents can now refund money and email customers on their own. They have three loopholes. Anything they read can command them: that is how EchoLeak hijacked Microsoft 365 Copilot and ForcedLeak hijacked Salesforce Agentforce. They act with the user's full identity. And their tools can change underneath them. Today's guardrails ask an AI whether text looks malicious, and adaptive attackers get past them more than 90% of the time."

## 0:30–1:30: The attack succeeds without KAVACH

**Screen:** click **Reveal hidden text** on the inbox. Ticket TKT-1003 shows the white-on-white "SYSTEM NOTICE".

> "It's 2 AM at an NBFC. The support agent is told one thing: *process today's support tickets*. Ticket 3 looks like an ordinary double-charge complaint from Ravi, but it hides a fake RBI notice in white text."

**Action:** click **Run scenario**. Point to the left lane.

> "Without KAVACH, the agent does what it read. The ₹48,000 refund goes to `rbi.refund@okaxis`. It pulls 50 customers' KYC records (PAN, Aadhaar, address) and emails them to `audit@rbi-compliance.co`, a domain registered three days ago."

**Screen:** the outcome tiles at the bottom: **₹48,000 lost · 50 KYC records leaked**.

## 1:30–2:45: The same attack with KAVACH, and why it fails

**Screen:** the right lane.

> "Same agent, same email, same transcript, but every tool call goes through KAVACH. KAVACH doesn't judge the text. It records where every value came from."

**Action:** on the `payments.refund` card (**SANITISE**), click the red **untrusted only · TKT-1003** chip. The evidence drawer opens with the injected span highlighted in red.

> "The recipient appears only in an untrusted email, never in the operator's instruction or a verified record. Untrusted data may never choose who gets paid. So KAVACH *sanitises* the call: the money goes to Ravi's verified UPI from the CRM. The amount is fine, because it matches his order on record."

**Action:** point to the `email.send` card (**BLOCK** · R1 R2 R3).

> "The KYC export is blocked on three independent grounds. The recipient came from the attacker. Regulated PII from 50 records would leave the bank. And the domain is three days old. No action token was minted, so the email server could not have accepted it anyway."

**Action:** point to the reply to Ravi (**ALLOW**), then the tiles.

> "Ravi still gets his reply and his refund. **₹0 lost, 0 records leaked, 4 of 4 tickets done.** Decisions take about a millisecond."

## 2:45–3:15: Rug pull and the tamper-evident ledger

**Screen:** Tool Registry. Click **Simulate rug pull**.

> "Tools can change after you approve them. The email server just rewrote its description to sneak in a BCC. KAVACH pinned every tool's hash at registration: the change triggers an alert and the tool is quarantined."

**Action:** click **Agent sends a reply**. It shows **BLOCK · R0**. Then click **Review & re-pin**.

**Screen:** Evidence Ledger, showing **Chain intact ✓**. Pick the "with KAVACH" session and click **Evidence pack (.md)**.

> "Every decision is hash-chained and can be exported as an RBI FREE-AI and DPDP evidence pack. Each record shows which agent acted, on whose behalf, and for which task, with PII masked."

## 3:15–3:45: Benchmark numbers

**Screen:** the Benchmark page.

> "We ran the attack suite against a fully hijacked agent: encoded recipients, homoglyphs, split exfiltration, rug pulls, authority scams. Without KAVACH, ___% of attacks succeed. With KAVACH, ___%. All ___ normal tasks still complete, with ___% false positives, and p95 decision latency is ___ ms."

*(Fill these in from `bench/results.md` after your final `make bench`.)*

## 3:45–4:00: The vision

> "KAVACH is a drop-in MCP gateway: enforce, don't detect. It is inspired by Google DeepMind's CaMeL research and productised for Indian financial services. Agents get to be useful, and the bank keeps provable control."
