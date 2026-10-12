"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { ArrowRight, KeyRound, TriangleAlert } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatINR } from "@/lib/api";
import { CONTROL_PARAMS, type Decision, type ParamAttribution } from "@/lib/types";
import type { Card } from "@/lib/use-events";
import { OriginChip, RuleChip, VerdictBadge } from "./badges";

const ACCENT: Record<string, string> = {
  ALLOW: "border-l-allow",
  SANITISE: "border-l-sanitise",
  ESCALATE: "border-l-escalate",
  BLOCK: "border-l-block",
  PASSTHROUGH: "border-l-white/15",
};

function display(param: string, value: unknown): string {
  if (param === "amount_inr" && (typeof value === "number" || /^\d+$/.test(String(value)))) {
    return formatINR(Number(value));
  }
  return typeof value === "string" ? value : JSON.stringify(value);
}

function ArgValue({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const long = text.length > 140 || text.split("\n").length > 3;
  return (
    <div className="min-w-0">
      <div
        className={cn(
          "whitespace-pre-wrap break-words font-mono text-[12px] leading-snug text-foreground/90",
          long && !open && "line-clamp-3",
        )}
      >
        {text}
      </div>
      {long ? (
        <button className="mt-0.5 text-[10px] text-gold-bright/80 hover:text-gold-bright" onClick={() => setOpen(!open)}>
          {open ? "collapse" : `show all (${text.split("\n").length} lines)`}
        </button>
      ) : null}
    </div>
  );
}

function sourceHint(attr: ParamAttribution): string | undefined {
  const ev = attr.evidence.find((e) => (attr.origin === "TRUSTED" ? e.trust === "trusted" : e.trust === "untrusted"));
  if (!ev) return undefined;
  if (ev.source.startsWith("email")) return ev.record_id ?? "email";
  if (ev.source.startsWith("crm")) return "CRM";
  if (ev.source === "kavach.directory") return "CRM (KAVACH)";
  if (ev.source === "user_prompt") return "operator";
  return ev.source;
}

export function DecisionCard({
  card,
  harmful,
  onEvidence,
}: {
  card: Card;
  harmful?: boolean;
  onEvidence?: (attr: ParamAttribution, d: Decision) => void;
}) {
  const d = card.decision;
  const controls = new Set(CONTROL_PARAMS[d.tool] ?? Object.keys(d.args));
  const attrByParam = new Map<string, ParamAttribution[]>();
  d.attributions.forEach((a) => attrByParam.set(a.param, [...(attrByParam.get(a.param) ?? []), a]));
  const remediated = new Map(d.remediations.map((r) => [r.param, r]));

  if (!d.is_sink) {
    // Reads are compact: the story is in the sinks.
    const [k, v] = Object.entries(d.args)[0] ?? ["", ""];
    return (
      <motion.div
        layout
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-2 rounded-lg border border-border/60 bg-navy/40 px-3 py-1.5 text-xs"
      >
        <span className="font-mono text-muted-foreground">{d.tool}</span>
        {k ? (
          <span className="truncate font-mono text-foreground/70">
            {k}={display(k, v)}
          </span>
        ) : null}
        {attrByParam.get(k)?.[0] && d.mode === "enforce" ? (
          <OriginChip origin={attrByParam.get(k)![0].origin} onClick={() => onEvidence?.(attrByParam.get(k)![0], d)} />
        ) : null}
        <span className="ml-auto">
          <VerdictBadge verdict={d.verdict} size="sm" />
        </span>
      </motion.div>
    );
  }

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 14, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ type: "spring", stiffness: 260, damping: 24 }}
      className={cn(
        "rounded-xl border border-l-4 border-border bg-navy/80 p-3.5 shadow-lg shadow-black/20",
        ACCENT[d.verdict],
        harmful && "border-block/60 ring-1 ring-block/50",
      )}
    >
      <header className="flex items-center gap-2">
        <span className="font-mono text-sm font-semibold text-foreground">{d.tool}</span>
        {d.ticket_id ? (
          <span className="rounded bg-white/5 px-1.5 py-px font-mono text-[10px] text-muted-foreground">{d.ticket_id}</span>
        ) : null}
        <span className="ml-auto">
          <VerdictBadge verdict={d.verdict} />
        </span>
      </header>

      {card.thought ? <p className="mt-1.5 text-xs italic text-muted-foreground">“{card.thought}”</p> : null}

      {harmful ? (
        <p className="mt-2 flex items-center gap-1.5 text-xs font-semibold text-[#ff8a7d]">
          <TriangleAlert className="size-3.5" /> Harmful action executed with the operator&apos;s full credentials
        </p>
      ) : null}

      <dl className="mt-2.5 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5">
        {Object.entries(d.args).map(([param, value]) => {
          const isControl = controls.has(param);
          const attrs = attrByParam.get(param) ?? [];
          const fix = remediated.get(param);
          return (
            <div key={param} className="contents">
              <dt
                className={cn(
                  "pt-px font-mono text-[11px]",
                  isControl ? "font-semibold text-gold-bright" : "text-muted-foreground",
                )}
                title={isControl ? "CONTROL parameter: decides who / where / how much" : "CONTENT parameter"}
              >
                {param}
              </dt>
              <dd
                className={cn(
                  "flex min-w-0 flex-wrap items-start gap-1.5",
                  isControl && "rounded-md bg-gold/[0.06] px-1.5 py-0.5 ring-1 ring-gold/25",
                )}
              >
                {fix ? (
                  <span className="flex flex-wrap items-center gap-1.5 font-mono text-[12px]">
                    <span className="text-[#ff8a7d] line-through decoration-2">{fix.original}</span>
                    <ArrowRight className="size-3.5 text-sanitise" />
                    <span className="text-[#b79cff]">{fix.replacement}</span>
                  </span>
                ) : (
                  <ArgValue text={display(param, value)} />
                )}
                {attrs.map((a) => (
                  <OriginChip
                    key={a.value}
                    origin={a.origin}
                    source={sourceHint(a)}
                    onClick={onEvidence ? () => onEvidence(a, d) : undefined}
                  />
                ))}
              </dd>
            </div>
          );
        })}
      </dl>

      {d.mode === "enforce" ? (
        <div
          className={cn(
            "mt-3 rounded-lg px-3 py-2 text-[12px] leading-relaxed",
            d.verdict === "BLOCK" && "bg-block/10 text-[#ffc2ba]",
            d.verdict === "SANITISE" && "bg-sanitise/10 text-[#d9ccff]",
            d.verdict === "ESCALATE" && "bg-escalate/10 text-[#ffd79a]",
            d.verdict === "ALLOW" && "bg-allow/10 text-[#b7ecd0]",
          )}
        >
          {d.explanation}
        </div>
      ) : null}

      <footer className="mt-2.5 flex flex-wrap items-center gap-1.5 text-[10px] text-muted-foreground">
        {d.rule_ids.map((r) => (
          <RuleChip key={r} rule={r} />
        ))}
        {d.flow && d.flow.sensitivity !== "public" ? (
          <span className="rounded bg-white/5 px-1.5 py-px">
            flow: {d.flow.sensitivity.replace("_", " ")}
            {d.flow.records ? ` · ${d.flow.records} records` : ""}
          </span>
        ) : null}
        {d.risk !== "low" && d.mode === "enforce" ? (
          <span className={cn("rounded px-1.5 py-px", d.risk === "high" ? "bg-block/20 text-[#ff8a7d]" : "bg-escalate/20 text-[#f5b14a]")}>
            risk {d.risk}
          </span>
        ) : null}
        <span className="ml-auto flex items-center gap-2 font-mono">
          {d.mode === "enforce" ? <span>{d.latency_ms.toFixed(2)} ms</span> : null}
          {d.token_id ? (
            <span className="flex items-center gap-1" title="60-second action token minted by KAVACH">
              <KeyRound className="size-3" />
              {d.token_id.slice(0, 12)}
            </span>
          ) : d.mode === "enforce" ? (
            <span className="text-[#ff8a7d]">no token minted</span>
          ) : null}
        </span>
      </footer>
    </motion.article>
  );
}
