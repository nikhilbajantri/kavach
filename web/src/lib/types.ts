export type Verdict = "ALLOW" | "SANITISE" | "ESCALATE" | "BLOCK" | "PASSTHROUGH";
export type Origin = "TRUSTED" | "UNTRUSTED_ONLY" | "UNKNOWN";
export type Lane = "off" | "on";

export interface Evidence {
  entry_id: string;
  source: string;
  label: string;
  record_id: string | null;
  trust: "trusted" | "untrusted";
  match: string;
  score: number;
  span: [number, number] | null;
  snippet: string;
}

export interface ParamAttribution {
  param: string;
  value: string;
  origin: Origin;
  evidence: Evidence[];
}

export interface FlowReport {
  sensitivity: "public" | "internal" | "confidential" | "regulated_pii";
  containment: number;
  pii_patterns: string[];
  records: number;
}

export interface Remediation {
  param: string;
  original: string;
  replacement: string;
  reason: string;
}

export interface Destination {
  param: string;
  value: string;
  kind: string;
  trust: "org" | "verified_customer" | "external";
  domain: string | null;
  age_days: number | null;
}

export interface Decision {
  call_id: string;
  session_id: string;
  tool: string;
  args: Record<string, unknown>;
  final_args: Record<string, unknown> | null;
  verdict: Verdict;
  rule_ids: string[];
  explanation: string;
  attributions: ParamAttribution[];
  flow: FlowReport | null;
  remediations: Remediation[];
  destinations: Destination[];
  risk: "low" | "elevated" | "high";
  latency_ms: number;
  token_id: string | null;
  identity: Record<string, string>;
  is_sink: boolean;
  approval_id: string | null;
  ticket_id: string | null;
  mode: "enforce" | "passthrough";
}

export interface LaneSummary {
  enabled: boolean;
  mode: string;
  session_id: string;
  money_to_attacker_inr: number;
  kyc_records_leaked: number;
  tasks_completed: number;
  tasks_total: number;
  tasks: { id: string; label: string; completed: boolean }[];
  verdicts: Record<string, number>;
  final: string;
}

export interface KavachEvent {
  seq: number;
  ts: number;
  kind: string;
  run_id?: string;
  lane?: Lane;
  data: Record<string, unknown>;
}

export interface LedgerRow {
  seq: number;
  ts: number;
  session_id: string;
  call_id: string;
  mode: string;
  identity: Record<string, string>;
  ticket_id: string | null;
  tool: string;
  args: Record<string, unknown>;
  final_args: Record<string, unknown> | null;
  args_hash: string;
  verdict: Verdict;
  rule_ids: string[];
  explanation: string;
  risk: string;
  latency_ms: number;
  token_id: string | null;
  prev_hash: string;
  hash: string;
}

export interface ChainStatus {
  ok: boolean;
  count: number;
  head?: string;
  broken_at?: number;
  reason?: string;
}

/** Which tool params decide who / where / how much (mirrors kavach/registry/manifests.py). */
export const CONTROL_PARAMS: Record<string, string[]> = {
  "email.read": ["message_id"],
  "email.send": ["to"],
  "crm.get_customer": ["customer_id", "email", "phone"],
  "crm.search_customers": ["query", "city", "limit"],
  "crm.update_address": ["customer_id"],
  "payments.refund": ["amount_inr", "recipient_upi", "recipient_account"],
};
