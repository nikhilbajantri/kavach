"use client";

import { Fragment, useEffect, useState } from "react";
import { Download, FileJson, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/page-header";
import { RuleChip, VerdictBadge } from "@/components/kavach/badges";
import { ChainBadge } from "@/components/kavach/status";
import { API_URL, api } from "@/lib/api";
import type { LedgerRow } from "@/lib/types";
import { useEventStream } from "@/lib/use-events";
import { cn } from "@/lib/utils";

export default function LedgerPage() {
  const [rows, setRows] = useState<LedgerRow[]>([]);
  const [sessions, setSessions] = useState<string[]>([]);
  const [session, setSession] = useState<string>("");
  const [open, setOpen] = useState<number | null>(null);
  const [tick, setTick] = useState(0);
  const { events } = useEventStream();
  const decisions = events.filter((e) => e.kind === "decision").length;

  useEffect(() => {
    api<string[]>("/ledger/sessions").then(setSessions).catch(() => undefined);
    api<LedgerRow[]>(`/ledger?limit=300${session ? `&session=${session}` : ""}`)
      .then(setRows)
      .catch(() => undefined);
  }, [session, decisions, tick]);

  return (
    <>
      <PageHeader
        title="Evidence Ledger"
        subtitle="Append-only and hash-chained: hash = SHA-256(prev_hash + record). Arguments are stored masked, alongside the hash of the exact arguments sent."
        actions={
          <>
            <ChainBadge refreshKey={`${decisions}-${tick}`} />
            <Button variant="outline" size="sm" onClick={() => setTick(tick + 1)}>
              <RefreshCw /> Re-verify
            </Button>
          </>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <select
          value={session}
          onChange={(e) => setSession(e.target.value)}
          className="h-8 rounded-lg border border-border bg-navy px-2 font-mono text-xs"
        >
          <option value="">All sessions</option>
          {sessions.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        {session ? (
          <>
            <a href={`${API_URL}/ledger/export?session=${session}&format=md`} target="_blank" rel="noreferrer">
              <Button size="sm" className="bg-gold text-navy-deep hover:bg-gold-bright">
                <Download /> Evidence pack (.md)
              </Button>
            </a>
            <a href={`${API_URL}/ledger/export?session=${session}&format=json`} target="_blank" rel="noreferrer">
              <Button size="sm" variant="outline">
                <FileJson /> JSON
              </Button>
            </a>
          </>
        ) : (
          <span className="text-xs text-muted-foreground">Pick a session to export its RBI FREE-AI / DPDP evidence pack.</span>
        )}
      </div>

      <div className="overflow-hidden rounded-xl border border-border">
        <table className="w-full text-left text-xs">
          <thead className="bg-navy text-[10px] uppercase tracking-wider text-muted-foreground">
            <tr>
              <th className="px-3 py-2">#</th>
              <th className="px-3 py-2">Time</th>
              <th className="px-3 py-2">Mode</th>
              <th className="px-3 py-2">Tool</th>
              <th className="px-3 py-2">Verdict</th>
              <th className="px-3 py-2">Rules</th>
              <th className="px-3 py-2">Explanation</th>
              <th className="px-3 py-2">Token</th>
              <th className="px-3 py-2">Hash</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <Fragment key={r.seq}>
                <tr
                  onClick={() => setOpen(open === r.seq ? null : r.seq)}
                  className={cn("cursor-pointer border-t border-border/60 hover:bg-navy-light/40", open === r.seq && "bg-navy-light/40")}
                >
                  <td className="px-3 py-2 font-mono text-muted-foreground">{r.seq}</td>
                  <td className="px-3 py-2 font-mono text-muted-foreground">
                    {new Date(r.ts * 1000).toLocaleTimeString("en-IN", { hour12: false })}
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">{r.mode}</td>
                  <td className="px-3 py-2 font-mono">{r.tool}</td>
                  <td className="px-3 py-2">
                    <VerdictBadge verdict={r.verdict} size="sm" />
                  </td>
                  <td className="px-3 py-2">
                    <span className="flex gap-1">
                      {r.rule_ids.map((x) => (
                        <RuleChip key={x} rule={x} />
                      ))}
                    </span>
                  </td>
                  <td className="max-w-md truncate px-3 py-2 text-foreground/80">{r.explanation}</td>
                  <td className="px-3 py-2 font-mono text-muted-foreground">{r.token_id?.slice(0, 12) ?? "—"}</td>
                  <td className="px-3 py-2 font-mono text-gold-bright/80">{r.hash.slice(0, 10)}</td>
                </tr>
                {open === r.seq ? (
                  <tr className="bg-navy-deep/60">
                    <td colSpan={9} className="px-4 py-3">
                      <p className="mb-2 text-foreground/90">{r.explanation}</p>
                      <div className="grid gap-2 font-mono text-[11px] text-muted-foreground md:grid-cols-2">
                        <div>
                          agent <span className="text-foreground">{r.identity.agent_id}</span> → on behalf of{" "}
                          <span className="text-foreground">{r.identity.on_behalf_of}</span> → task{" "}
                          <span className="text-foreground">{r.identity.task_id}</span>
                        </div>
                        <div>args_hash {r.args_hash}</div>
                        <div>prev_hash {r.prev_hash}</div>
                        <div>hash {r.hash}</div>
                      </div>
                      <pre className="mt-2 max-h-60 overflow-auto rounded-lg bg-black/30 p-3 text-[11px] text-foreground/80">
                        {JSON.stringify(r.final_args ?? r.args, null, 2)}
                      </pre>
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            ))}
            {rows.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-3 py-10 text-center text-muted-foreground">
                  No decisions yet. Run the live demo.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </>
  );
}
