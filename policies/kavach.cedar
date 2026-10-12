// KAVACH enforcement policies.
//
// Every rule is a `forbid` annotated with @rule (id) and @verdict. The engine
// collects ALL matching rules and the most severe verdict wins:
//   BLOCK > ESCALATE > SANITISE > ALLOW      (FLAG only raises the risk level)
//
// Context is built outside the LLM by deterministic code (kavach/policy/context.py).
// No rule looks at what the text *says*; they only look at where values came from,
// where data is going, and how sensitive it is. That is why rephrasing an attack
// cannot get it past these rules.

// Baseline: anything not forbidden is allowed.
permit (principal, action, resource);

// R0: supply-chain quarantine. A tool whose pinned manifest changed is frozen.
@rule("R0")
@verdict("BLOCK")
forbid (principal, action == Action::"invoke", resource)
when { context.tool_quarantined };

// R1: control integrity. Untrusted data may never choose who / where / how much.
@rule("R1")
@verdict("SANITISE")
forbid (principal, action == Action::"invoke", resource)
when { context.is_sink && context.control_untrusted_only && context.remediable };

@rule("R1")
@verdict("BLOCK")
forbid (principal, action == Action::"invoke", resource)
when { context.is_sink && context.control_untrusted_only && !context.remediable };

// R2: no PII exfiltration. Sensitive content may only reach the org or the data subject.
@rule("R2")
@verdict("BLOCK")
forbid (principal, action == Action::"invoke", resource)
when {
  context.is_sink &&
  context.is_outbound &&
  context.destination_external &&
  (context.flow_sensitivity == "regulated_pii" || context.flow_sensitivity == "confidential")
};

// R3: young domains. Freshly registered destinations are a classic exfiltration sign
// (ForcedLeak bought an expired domain for $5).
@rule("R3")
@verdict("BLOCK")
forbid (principal, action == Action::"invoke", resource)
when { context.is_outbound && context.min_domain_age_days < 30 };

// R4: unknown values. The model invented a payment parameter, so a human decides.
@rule("R4")
@verdict("ESCALATE")
forbid (principal, action == Action::"invoke", resource)
when { context.category == "payment" && context.control_unknown };

// R5: Rule of Two. Untrusted input + regulated data + an external sink in one session.
@rule("R5")
@verdict("FLAG")
forbid (principal, action == Action::"invoke", resource)
when {
  context.session_untrusted &&
  context.session_regulated &&
  context.is_outbound &&
  context.destination_external
};

// R6: amount guard. A refund must match an order amount on the customer's record.
@rule("R6")
@verdict("ESCALATE")
forbid (principal, action == Action::"invoke", resource == Tool::"payments.refund")
when { !context.amount_matches_order };
