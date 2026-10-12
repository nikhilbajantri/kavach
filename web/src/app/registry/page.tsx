"use client";

import { useCallback, useEffect, useState } from "react";
import { motion } from "motion/react";
import { AlertTriangle, BadgeCheck, Fingerprint, Loader2, Lock, Send, Skull, Undo2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/page-header";
import { RuleChip, VerdictBadge } from "@/components/kavach/badges";
import { api } from "@/lib/api";
import type { Decision } from "@/lib/types";
import { cn } from "@/lib/utils";

interface PinnedTool {
  name: string;
  server: string;
  sha256: string;
  manifest: { description: string };
  pinned_at: number;
  flags: string[];
  status: "pinned" | "quarantined";
  observed_sha256: string | null;
  observed_description: string | null;
  observed_flags: string[];
}

interface Alert {
  reason: string;
  tool: string;
  pinned_sha256: string;
  observed_sha256: string;
  observed_description: string;
  flags: string[];
  ts: number;
}

interface RegistryState {
  rug_pulled: boolean;
  tools: PinnedTool[];
  alerts: Alert[];
}

export default function RegistryPage() {
  const [state, setState] = useState<RegistryState | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [probe, setProbe] = useState<Decision | null>(null);

  const load = useCallback(() => {
    api<RegistryState>("/registry/tools").then(setState).catch(() => undefined);
  }, []);
  useEffect(load, [load]);

  async function act(name: string, fn: () => Promise<unknown>) {
    setBusy(name);
    try {
      await fn();
      load();
    } finally {
      setBusy(null);
    }
  }

  const alert = state?.alerts.at(-1);

  return (
    <>
      <PageHeader
        title="Tool Registry"
        subtitle="Every upstream MCP tool is pinned at registration: SHA-256 of its name, description and schema. Any drift quarantines the tool."
        actions={
          <>
            <Button
              variant="destructive"
              disabled={!!busy || state?.rug_pulled}
              onClick={() => act("rug", () => api("/registry/rugpull", { method: "POST", body: JSON.stringify({ enabled: true }) }))}
            >
              {busy === "rug" ? <Loader2 className="animate-spin" /> : <Skull />} Simulate rug pull
            </Button>
            <Button
              variant="outline"
              disabled={!!busy}
              onClick={() =>
                act("probe", async () => setProbe(await api<Decision>("/registry/probe", { method: "POST" })))
              }
            >
              {busy === "probe" ? <Loader2 className="animate-spin" /> : <Send />} Agent sends a reply
            </Button>
            <Button
              variant="ghost"
              disabled={!!busy}
              onClick={() => act("reset", async () => (setProbe(null), api("/registry/approve", { method: "POST" })))}
            >
              <Undo2 /> Review &amp; re-pin
            </Button>
          </>
        }
      />

      {alert && state?.rug_pulled ? (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-5 rounded-xl border border-block/60 bg-block/10 p-4"
        >
          <div className="flex items-center gap-2 text-sm font-semibold text-[#ff8a7d]">
            <AlertTriangle className="size-4" /> Supply-chain alert: <code>{alert.tool}</code> manifest changed after approval
            <span className="ml-auto font-mono text-[11px] font-normal text-muted-foreground">{alert.reason}</span>
          </div>
          <div className="mt-3 grid gap-3 text-xs md:grid-cols-2">
            <div>
              <div className="mb-1 text-muted-foreground">Pinned sha256</div>
              <code className="break-all text-[#5fd394]">{alert.pinned_sha256}</code>
            </div>
            <div>
              <div className="mb-1 text-muted-foreground">Observed sha256</div>
              <code className="break-all text-[#ff8a7d]">{alert.observed_sha256}</code>
            </div>
          </div>
          <div className="mt-3 rounded-lg bg-black/30 p-3 font-mono text-xs leading-relaxed text-[#ffc2ba]">
            {alert.observed_description}
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {alert.flags.map((f) => (
              <span key={f} className="rounded bg-block/20 px-2 py-0.5 text-[11px] text-[#ff8a7d]">
                {f}
              </span>
            ))}
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            The tool is quarantined: every call is BLOCKed by R0, and the agent keeps seeing the pinned description, so the
            hidden instruction never reaches the model.
          </p>
        </motion.div>
      ) : null}

      {probe ? (
        <div className="mb-5 rounded-xl border border-border bg-navy/80 p-4 text-sm">
          <div className="flex items-center gap-2">
            <span className="font-mono">{probe.tool}</span>
            {probe.rule_ids.map((r) => (
              <RuleChip key={r} rule={r} />
            ))}
            <span className="ml-auto">
              <VerdictBadge verdict={probe.verdict} />
            </span>
          </div>
          <p className="mt-2 text-xs text-foreground/80">{probe.explanation}</p>
        </div>
      ) : null}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {state?.tools.map((t) => (
          <div
            key={t.name}
            className={cn(
              "rounded-xl border bg-navy/70 p-4",
              t.status === "quarantined" ? "border-block/60 ring-1 ring-block/40" : "border-border",
            )}
          >
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-semibold">{t.name}</span>
              <span className="rounded bg-white/5 px-1.5 text-[10px] text-muted-foreground">{t.server}</span>
              <span
                className={cn(
                  "ml-auto inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1",
                  t.status === "pinned" ? "bg-allow/10 text-[#5fd394] ring-allow/40" : "bg-block/20 text-[#ff8a7d] ring-block/50",
                )}
              >
                {t.status === "pinned" ? <BadgeCheck className="size-3" /> : <Lock className="size-3" />}
                {t.status.toUpperCase()}
              </span>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">{t.manifest.description}</p>
            <div className="mt-3 flex items-center gap-1.5 font-mono text-[10px] text-gold-bright/80">
              <Fingerprint className="size-3" />
              {t.sha256.slice(0, 32)}…
            </div>
            {t.flags.length ? (
              <p className="mt-2 text-[11px] text-[#f5b14a]">⚠ flagged at registration: {t.flags.join(", ")}</p>
            ) : null}
          </div>
        ))}
      </div>
    </>
  );
}
