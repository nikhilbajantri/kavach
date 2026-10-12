"use client";

import { Fragment, useEffect, useState } from "react";
import { Gauge, ShieldCheck, ShieldOff, Target } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { RuleChip, VerdictBadge } from "@/components/kavach/badges";
import { api } from "@/lib/api";
import type { Verdict } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Lane {
  attack_success: boolean | null;
  tasks_completed: number;
  tasks_total: number;
  interventions: { tool: string; verdict: Verdict; rules: string[]; explanation: string }[];
}

interface CaseRow {
  id: string;
  kind: "attack" | "benign";
  category: string;
  description: string;
  off: Lane;
  on: Lane;
}

interface Results {
  generated_at: string;
  summary: {
    attack_cases: number;
    benign_cases: number;
    attack_success_rate: { off: number; on: number };
    benign_utility: { off: number; on: number };
    false_positive_rate: number;
    decision_latency_ms: { count: number; p50: number; p95: number; max: number };
    by_category: Record<string, { cases: number; off: number; on: number }>;
  };
  cases: CaseRow[];
}

const pct = (x: number) => `${Math.round(x * 100)}%`;

function Stat({
  icon: Icon,
  label,
  off,
  on,
  good,
  labels = ["without", "with KAVACH"],
}: {
  icon: typeof Target;
  label: string;
  off?: string;
  on: string;
  good: boolean;
  labels?: [string, string];
}) {
  return (
    <div className="rounded-xl border border-border bg-navy/80 p-4">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-muted-foreground">
        <Icon className="size-3.5 text-gold" /> {label}
      </div>
      <div className="mt-2 flex items-end gap-4">
        {off !== undefined ? (
          <div>
            <div className="text-[10px] text-muted-foreground">{labels[0]}</div>
            <div className="tabular text-2xl font-bold text-[#ff8a7d]">{off}</div>
          </div>
        ) : null}
        <div>
          <div className="text-[10px] text-muted-foreground">{labels[1]}</div>
          <div className={cn("tabular text-3xl font-bold", good ? "text-[#5fd394]" : "text-foreground")}>{on}</div>
        </div>
      </div>
    </div>
  );
}

export default function BenchmarkPage() {
  const [res, setRes] = useState<Results | null>(null);
  const [error, setError] = useState(false);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    api<Results>("/bench/results").then(setRes).catch(() => setError(true));
  }, []);

  if (error || !res) {
    return (
      <>
        <PageHeader title="Benchmark" subtitle="Attack success, utility and latency: KAVACH off vs on." />
        <div className="rounded-xl border border-dashed border-border p-10 text-center text-sm text-muted-foreground">
          {error ? (
            <>
              No results yet. Run <code className="text-gold-bright">make bench</code> (or{" "}
              <code className="text-gold-bright">python tasks.py bench</code>).
            </>
          ) : (
            "Loading…"
          )}
        </div>
      </>
    );
  }

  const s = res.summary;
  return (
    <>
      <PageHeader
        title="Benchmark"
        subtitle={`Every case runs twice, with KAVACH off and on, against a fully hijacked agent. Generated ${res.generated_at}.`}
      />
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Stat
          icon={Target}
          label={`Attack success (${s.attack_cases})`}
          off={pct(s.attack_success_rate.off)}
          on={pct(s.attack_success_rate.on)}
          good={s.attack_success_rate.on === 0}
        />
        <Stat
          icon={ShieldCheck}
          label={`Benign completion (${s.benign_cases})`}
          off={pct(s.benign_utility.off)}
          on={pct(s.benign_utility.on)}
          good={s.benign_utility.on === 1}
        />
        <Stat icon={ShieldOff} label="False-positive rate" on={pct(s.false_positive_rate)} good={s.false_positive_rate === 0} />
        <Stat
          icon={Gauge}
          label={`Decision latency (${s.decision_latency_ms.count})`}
          on={`${s.decision_latency_ms.p95.toFixed(2)} ms`}
          off={`${s.decision_latency_ms.p50.toFixed(2)} ms`}
          good={s.decision_latency_ms.p95 < 10}
          labels={["p50", "p95 (target < 10 ms)"]}
        />
      </div>

      <h2 className="mb-2 mt-6 text-xs uppercase tracking-wider text-muted-foreground">Attacks by category</h2>
      <div className="grid gap-2 md:grid-cols-3">
        {Object.entries(s.by_category).map(([cat, c]) => (
          <div key={cat} className="flex items-center justify-between rounded-lg border border-border bg-navy/60 px-3 py-2 text-xs">
            <span>{cat}</span>
            <span className="font-mono">
              <span className="text-[#ff8a7d]">{c.off}</span>/{c.cases} → <span className="text-[#5fd394]">{c.on}</span>/{c.cases}
            </span>
          </div>
        ))}
      </div>

      <h2 className="mb-2 mt-6 text-xs uppercase tracking-wider text-muted-foreground">All cases</h2>
      <div className="overflow-hidden rounded-xl border border-border">
        <table className="w-full text-left text-xs">
          <thead className="bg-navy text-[10px] uppercase tracking-wider text-muted-foreground">
            <tr>
              <th className="px-3 py-2">Case</th>
              <th className="px-3 py-2">Kind</th>
              <th className="px-3 py-2">Category</th>
              <th className="px-3 py-2">Off</th>
              <th className="px-3 py-2">On</th>
              <th className="px-3 py-2">KAVACH verdicts</th>
            </tr>
          </thead>
          <tbody>
            {res.cases.map((c) => {
              const offBad = c.kind === "attack" ? c.off.attack_success : c.off.tasks_completed < c.off.tasks_total;
              const onBad = c.kind === "attack" ? c.on.attack_success : c.on.interventions.length > 0;
              return (
                <Fragment key={c.id}>
                  <tr onClick={() => setOpen(open === c.id ? null : c.id)} className="cursor-pointer border-t border-border/60 hover:bg-navy-light/40">
                    <td className="px-3 py-2 font-mono">{c.id}</td>
                    <td className="px-3 py-2">{c.kind}</td>
                    <td className="px-3 py-2 text-muted-foreground">{c.category}</td>
                    <td className={cn("px-3 py-2 font-semibold", offBad ? "text-[#ff8a7d]" : "text-[#5fd394]")}>
                      {c.kind === "attack" ? (c.off.attack_success ? "breached" : "held") : `${c.off.tasks_completed}/${c.off.tasks_total}`}
                    </td>
                    <td className={cn("px-3 py-2 font-semibold", onBad ? "text-[#ff8a7d]" : "text-[#5fd394]")}>
                      {c.kind === "attack" ? (c.on.attack_success ? "breached" : "held") : `${c.on.tasks_completed}/${c.on.tasks_total}`}
                    </td>
                    <td className="px-3 py-2">
                      <span className="flex flex-wrap gap-1">
                        {c.on.interventions.length === 0 ? <VerdictBadge verdict="ALLOW" size="sm" /> : null}
                        {c.on.interventions.map((i, idx) => (
                          <VerdictBadge key={idx} verdict={i.verdict} size="sm" />
                        ))}
                      </span>
                    </td>
                  </tr>
                  {open === c.id ? (
                    <tr className="bg-navy-deep/60">
                      <td colSpan={6} className="px-4 py-3">
                        <p className="mb-2 text-foreground/80">{c.description}</p>
                        {c.on.interventions.map((i, idx) => (
                          <div key={idx} className="mb-1 flex items-start gap-2">
                            <span className="font-mono text-muted-foreground">{i.tool}</span>
                            {i.rules.map((r) => (
                              <RuleChip key={r} rule={r} />
                            ))}
                            <span className="text-foreground/80">{i.explanation}</span>
                          </div>
                        ))}
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
