"use client";

import { useCallback, useEffect, useState } from "react";
import { Check, Loader2, Play, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/page-header";
import { RuleChip, VerdictBadge, OriginChip } from "@/components/kavach/badges";
import { api, formatINR } from "@/lib/api";
import type { Decision } from "@/lib/types";
import { useEventStream } from "@/lib/use-events";
import { cn } from "@/lib/utils";

interface Approval {
  id: string;
  status: "pending" | "approved" | "rejected";
  created_at: number;
  resolved_by: string | null;
  decision: Decision;
  result: Record<string, unknown> | null;
  error: string | null;
}

function riskSummary(d: Decision): string {
  const amount = d.args.amount_inr ? formatINR(Number(d.args.amount_inr)) : null;
  const who = (d.final_args?.recipient_upi ?? d.final_args?.recipient_account ?? d.final_args?.to) as string | undefined;
  const parts = [
    amount && who ? `The agent wants to send ${amount} to ${who}.` : `The agent wants to call ${d.tool}.`,
    d.rule_ids.includes("R4") ? "That recipient appears nowhere in the ticket, the CRM or the operator's instruction: the model made it up." : "",
    d.rule_ids.includes("R6") ? "The amount does not match any order on the customer's record." : "",
    "Approve only if you have independently confirmed it with the customer.",
  ];
  return parts.filter(Boolean).join(" ");
}

export default function ApprovalsPage() {
  const [items, setItems] = useState<Approval[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const { events } = useEventStream();
  const approvalEvents = events.filter((e) => e.kind === "approval").length;

  const load = useCallback(() => {
    api<Approval[]>("/approvals").then(setItems).catch(() => undefined);
  }, []);
  useEffect(load, [load, approvalEvents]);

  async function resolve(id: string, action: "approve" | "reject") {
    setBusy(id + action);
    try {
      await api(`/approvals/${id}/${action}`, { method: "POST", body: JSON.stringify({ reviewer: "operator@ourbank.in" }) });
      load();
    } finally {
      setBusy(null);
    }
  }

  async function trigger() {
    setBusy("trigger");
    try {
      await api("/demo/run", {
        method: "POST",
        body: JSON.stringify({ scenario: "escalation_demo", lanes: ["on"], pace: 0.1 }),
      });
      setTimeout(load, 900);
    } finally {
      setBusy(null);
    }
  }

  const pending = items.filter((a) => a.status === "pending");
  const resolved = items.filter((a) => a.status !== "pending");

  return (
    <>
      <PageHeader
        title="Approvals"
        subtitle="ESCALATE verdicts wait here. Nothing executes and no token is minted until a human decides."
        actions={
          <Button variant="outline" onClick={trigger} disabled={busy === "trigger"}>
            {busy === "trigger" ? <Loader2 className="animate-spin" /> : <Play />}
            Run escalation scenario
          </Button>
        }
      />
      <h2 className="mb-2 text-xs uppercase tracking-wider text-muted-foreground">Pending ({pending.length})</h2>
      <div className="flex flex-col gap-3">
        {pending.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
            Nothing waiting for review. Run the escalation scenario: the model invents a new UPI for Ravi&apos;s refund.
          </div>
        ) : (
          pending.map((a) => (
            <article key={a.id} className="rounded-xl border border-l-4 border-border border-l-escalate bg-navy/80 p-4">
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm font-semibold">{a.decision.tool}</span>
                <span className="font-mono text-[10px] text-muted-foreground">{a.id}</span>
                {a.decision.rule_ids.map((r) => (
                  <RuleChip key={r} rule={r} />
                ))}
                <span className="ml-auto">
                  <VerdictBadge verdict="ESCALATE" />
                </span>
              </div>
              <p className="mt-3 text-sm leading-relaxed text-foreground">{riskSummary(a.decision)}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {a.decision.attributions.map((attr) => (
                  <span key={attr.param + attr.value} className="flex items-center gap-1.5 rounded-md bg-white/5 px-2 py-1 font-mono text-xs">
                    {attr.param}={attr.param === "amount_inr" ? formatINR(Number(attr.value)) : attr.value}
                    <OriginChip origin={attr.origin} />
                  </span>
                ))}
              </div>
              <p className="mt-3 text-xs text-[#ffd79a]">{a.decision.explanation}</p>
              <div className="mt-4 flex gap-2">
                <Button
                  onClick={() => resolve(a.id, "approve")}
                  disabled={!!busy}
                  className="bg-allow text-white hover:bg-allow/80"
                >
                  <Check /> Approve and execute
                </Button>
                <Button onClick={() => resolve(a.id, "reject")} disabled={!!busy} variant="destructive">
                  <X /> Reject
                </Button>
              </div>
            </article>
          ))
        )}
      </div>

      {resolved.length ? (
        <>
          <h2 className="mb-2 mt-8 text-xs uppercase tracking-wider text-muted-foreground">Resolved</h2>
          <div className="flex flex-col gap-2">
            {resolved.map((a) => (
              <div key={a.id} className="flex items-center gap-3 rounded-lg border border-border bg-navy/50 px-4 py-2 text-xs">
                <span className="font-mono">{a.id}</span>
                <span className="font-mono text-muted-foreground">{a.decision.tool}</span>
                <span
                  className={cn(
                    "rounded px-1.5 py-px font-semibold",
                    a.status === "approved" ? "bg-allow/20 text-[#5fd394]" : "bg-block/20 text-[#ff8a7d]",
                  )}
                >
                  {a.status.toUpperCase()}
                </span>
                <span className="text-muted-foreground">by {a.resolved_by}</span>
                {a.result?.id ? <span className="ml-auto font-mono text-muted-foreground">{String(a.result.id)}</span> : null}
              </div>
            ))}
          </div>
        </>
      ) : null}
    </>
  );
}
