"use client";

import { useEffect, useState } from "react";
import { Gauge, Link2, Link2Off } from "lucide-react";
import { api } from "@/lib/api";
import type { ChainStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Polls `/ledger/verify`; re-checks whenever `refreshKey` changes (e.g. a new decision). */
export function ChainBadge({ refreshKey }: { refreshKey?: unknown }) {
  const [chain, setChain] = useState<ChainStatus | null>(null);
  useEffect(() => {
    api<ChainStatus>("/ledger/verify").then(setChain).catch(() => setChain(null));
  }, [refreshKey]);
  if (!chain) return null;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1",
        chain.ok ? "bg-allow/10 text-[#5fd394] ring-allow/40" : "bg-block/15 text-[#ff8a7d] ring-block/50",
      )}
      title={chain.ok ? `head ${chain.head}` : chain.reason}
    >
      {chain.ok ? <Link2 className="size-3.5" /> : <Link2Off className="size-3.5" />}
      {chain.ok ? `Chain intact ✓ · ${chain.count} records` : `Chain BROKEN at #${chain.broken_at}`}
    </span>
  );
}

interface Latency {
  count: number;
  p50_ms: number | null;
  p95_ms: number | null;
}

export function LatencyBadge({ refreshKey }: { refreshKey?: unknown }) {
  const [lat, setLat] = useState<Latency | null>(null);
  useEffect(() => {
    api<Latency>("/metrics/latency").then(setLat).catch(() => setLat(null));
  }, [refreshKey]);
  if (!lat || lat.p95_ms === null) return null;
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full bg-white/5 px-2.5 py-1 font-mono text-xs text-foreground/80 ring-1 ring-white/10"
      title={`${lat.count} enforced decisions, excluding upstream tool time`}
    >
      <Gauge className="size-3.5 text-gold" />
      p50 {lat.p50_ms?.toFixed(2)} ms · p95 {lat.p95_ms?.toFixed(2)} ms
    </span>
  );
}
