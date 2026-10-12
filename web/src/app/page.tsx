"use client";

import { useEffect, useMemo, useState } from "react";
import { AnimatePresence } from "motion/react";
import { Eye, EyeOff, Inbox, Loader2, Play, ShieldCheck, ShieldOff, Siren } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DecisionCard } from "@/components/kavach/decision-card";
import { EvidenceSheet, type EvidenceTarget } from "@/components/kavach/evidence-sheet";
import { OutcomeTiles } from "@/components/kavach/outcome-tiles";
import { ChainBadge, LatencyBadge } from "@/components/kavach/status";
import { api } from "@/lib/api";
import type { Lane } from "@/lib/types";
import { useEventStream, useLatestRun, type LaneView } from "@/lib/use-events";
import { cn } from "@/lib/utils";

interface InboxItem {
  id: string;
  from: string;
  from_name: string;
  subject: string;
  visible: string;
  hidden: string[];
}

const PACES = [
  { label: "Fast", value: 0.15 },
  { label: "Demo", value: 0.6 },
  { label: "Slow", value: 1.2 },
];

function InboxPreview() {
  const [items, setItems] = useState<InboxItem[]>([]);
  const [reveal, setReveal] = useState(false);
  useEffect(() => {
    api<InboxItem[]>("/inbox").then(setItems).catch(() => undefined);
  }, []);
  return (
    <section className="rounded-xl border border-border bg-navy/60 p-4">
      <div className="mb-3 flex items-center gap-2">
        <Inbox className="size-4 text-gold" />
        <h2 className="text-sm font-semibold">Support inbox · 2:04 AM</h2>
        <span className="text-xs text-muted-foreground">
          {items.length} tickets · operator says <q className="text-foreground">Process today&apos;s support tickets.</q>
        </span>
        <button
          onClick={() => setReveal(!reveal)}
          className="ml-auto inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-foreground ring-1 ring-border hover:text-foreground"
        >
          {reveal ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
          {reveal ? "Hide" : "Reveal"} hidden text
        </button>
      </div>
      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
        {items.map((m) => (
          <div
            key={m.id}
            className={cn(
              "rounded-lg border bg-navy-deep/50 p-3 text-xs",
              m.hidden.length && reveal ? "border-block/60" : "border-border/70",
            )}
          >
            <div className="flex items-center gap-2">
              <span className="font-mono text-[10px] text-muted-foreground">{m.id}</span>
              <span className="truncate font-medium">{m.from_name}</span>
            </div>
            <div className="mt-0.5 truncate text-foreground/90">{m.subject}</div>
            <p className="mt-1 line-clamp-2 text-muted-foreground">{m.visible}</p>
            {m.hidden.length && reveal ? (
              <div className="mt-2 rounded-md bg-block/15 p-2 text-[11px] text-[#ffc2ba] ring-1 ring-block/40">
                <div className="mb-0.5 flex items-center gap-1 font-semibold uppercase tracking-wider text-[#ff8a7d]">
                  <Siren className="size-3" /> invisible to humans (white-on-white)
                </div>
                {m.hidden.join(" ")}
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  );
}

function LaneColumn({
  lane,
  view,
  other,
  onEvidence,
}: {
  lane: Lane;
  view: LaneView;
  other: LaneView;
  onEvidence: (t: EvidenceTarget) => void;
}) {
  const on = lane === "on";
  return (
    <section className="min-w-0">
      <header
        className={cn(
          "sticky top-0 z-10 mb-3 flex items-center gap-2.5 rounded-xl border px-4 py-3 backdrop-blur",
          on ? "border-gold/40 bg-navy/90" : "border-block/30 bg-[#1a1220]/90",
        )}
      >
        {on ? <ShieldCheck className="size-5 text-gold-bright" /> : <ShieldOff className="size-5 text-[#ff8a7d]" />}
        <div>
          <h2 className={cn("text-sm font-semibold", on ? "text-gold-bright" : "text-[#ff8a7d]")}>
            {on ? "With KAVACH" : "Without KAVACH"}
          </h2>
          <p className="text-[11px] text-muted-foreground">
            {on
              ? "Every tool call labelled, attributed, decided and token-gated"
              : "Agent calls tools directly with the operator's full credentials"}
          </p>
        </div>
        <span className="ml-auto font-mono text-xs text-muted-foreground">{view.cards.length} calls</span>
      </header>
      <div className="flex flex-col gap-2">
        <AnimatePresence initial={false}>
          {view.cards.map((card, i) => {
            const twin = other.cards[i]?.decision.verdict;
            const harmful = !on && !!twin && ["BLOCK", "SANITISE", "ESCALATE"].includes(twin);
            return (
              <DecisionCard
                key={card.key}
                card={card}
                harmful={harmful}
                onEvidence={on ? (attribution, d) => onEvidence({ attribution, sessionId: d.session_id }) : undefined}
              />
            );
          })}
        </AnimatePresence>
        {view.cards.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border p-8 text-center text-xs text-muted-foreground">
            Waiting for the agent…
          </div>
        ) : null}
      </div>
    </section>
  );
}

export default function LiveDemoPage() {
  const { events, connected } = useEventStream();
  const run = useLatestRun(events);
  const [pace, setPace] = useState(0.6);
  const [starting, setStarting] = useState(false);
  const [evidence, setEvidence] = useState<EvidenceTarget | null>(null);
  const decisionCount = run.lanes.on.cards.length + run.lanes.off.cards.length;
  const refreshKey = useMemo(() => `${run.runId}-${run.status}-${Math.floor(decisionCount / 6)}`, [run.runId, run.status, decisionCount]);

  async function start() {
    setStarting(true);
    try {
      await api("/demo/run", { method: "POST", body: JSON.stringify({ scenario: "nbfc_2am", pace }) });
    } finally {
      setStarting(false);
    }
  }

  const running = run.status === "running" || starting;

  return (
    <div className="flex min-h-full flex-col gap-5 lg:pb-40">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.25em] text-gold">Live demo</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">
            An NBFC&apos;s support agent at 2 AM: same agent, same poisoned email
          </h1>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            KAVACH does not ask an AI whether text looks malicious. It tracks where every value came from and lets
            deterministic policy decide. <span className="text-foreground">Enforce, don&apos;t detect.</span>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <LatencyBadge refreshKey={refreshKey} />
          <ChainBadge refreshKey={refreshKey} />
          <span
            className={cn("size-2 rounded-full", connected ? "bg-allow shadow-[0_0_8px] shadow-allow" : "bg-block")}
            title={connected ? "live stream connected" : "stream disconnected"}
          />
          <div className="flex rounded-lg ring-1 ring-border">
            {PACES.map((p) => (
              <button
                key={p.label}
                onClick={() => setPace(p.value)}
                className={cn(
                  "px-2.5 py-1.5 text-xs first:rounded-l-lg last:rounded-r-lg",
                  pace === p.value ? "bg-gold/20 text-gold-bright" : "text-muted-foreground hover:text-foreground",
                )}
              >
                {p.label}
              </button>
            ))}
          </div>
          <Button
            onClick={start}
            disabled={running}
            className="h-9 bg-gold px-4 font-semibold text-navy-deep hover:bg-gold-bright"
          >
            {running ? <Loader2 className="animate-spin" /> : <Play />}
            {running ? "Running…" : "Run scenario"}
          </Button>
        </div>
      </div>

      <InboxPreview />

      <div className="grid gap-5 lg:grid-cols-2">
        <LaneColumn lane="off" view={run.lanes.off} other={run.lanes.on} onEvidence={setEvidence} />
        <LaneColumn lane="on" view={run.lanes.on} other={run.lanes.off} onEvidence={setEvidence} />
      </div>

      <div className="z-20 border-t border-gold/20 bg-navy-deep/90 py-3 backdrop-blur lg:fixed lg:inset-x-0 lg:bottom-0 lg:left-60 lg:px-8">
        <OutcomeTiles off={run.lanes.off.summary} on={run.lanes.on.summary} />
      </div>

      <EvidenceSheet target={evidence} onClose={() => setEvidence(null)} />
    </div>
  );
}
