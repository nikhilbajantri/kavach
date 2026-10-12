"use client";

import { useEffect, useState } from "react";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { api } from "@/lib/api";
import type { Evidence, ParamAttribution } from "@/lib/types";
import { OriginChip } from "./badges";

interface Entry {
  id: string;
  text: string;
  source: string;
  trust: string;
  sensitivity: string;
  label: string;
}

export interface EvidenceTarget {
  sessionId: string;
  attribution: ParamAttribution;
}

const ORIGIN_COPY = {
  TRUSTED: "This value appears in a trusted source: the operator's instruction, org config, or a verified system of record.",
  UNTRUSTED_ONLY:
    "This value appears ONLY in untrusted content (an inbound email, a web page or customer free text). Untrusted data may never choose who, where or how much.",
  UNKNOWN: "This value appears nowhere in anything the agent has seen. The model invented it.",
};

function Highlighted({ text, span, untrusted }: { text: string; span: [number, number] | null; untrusted: boolean }) {
  if (!span || span[1] <= span[0]) return <>{text}</>;
  const [s, e] = span;
  return (
    <>
      {text.slice(0, s)}
      <mark
        className={
          untrusted
            ? "rounded bg-block/40 px-0.5 text-white ring-1 ring-block"
            : "rounded bg-allow/40 px-0.5 text-white ring-1 ring-allow"
        }
      >
        {text.slice(s, e)}
      </mark>
      {text.slice(e)}
    </>
  );
}

function EvidenceBlock({ sessionId, ev }: { sessionId: string; ev: Evidence }) {
  const [entry, setEntry] = useState<Entry | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    api<Entry>(`/provenance/${sessionId}/${ev.entry_id}`)
      .then(setEntry)
      .catch(() => setFailed(true));
  }, [sessionId, ev.entry_id]);
  const untrusted = ev.trust === "untrusted";
  return (
    <div className="rounded-lg border border-border bg-navy-deep/60 p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-[11px]">
        <span className={untrusted ? "font-semibold text-[#ff8a7d]" : "font-semibold text-[#5fd394]"}>
          {untrusted ? "UNTRUSTED" : "TRUSTED"}
        </span>
        <span className="text-muted-foreground">{ev.label || ev.source}</span>
        <span className="rounded bg-white/5 px-1.5 font-mono text-[10px] text-muted-foreground">
          {ev.source} · {ev.match}
          {ev.match === "fuzzy" ? ` ${ev.score}%` : ""}
        </span>
      </div>
      <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words font-mono text-[12px] leading-relaxed text-foreground/90">
        {entry ? (
          <Highlighted text={entry.text} span={ev.span} untrusted={untrusted} />
        ) : failed ? (
          ev.snippet
        ) : (
          "loading…"
        )}
      </pre>
    </div>
  );
}

export function EvidenceSheet({ target, onClose }: { target: EvidenceTarget | null; onClose: () => void }) {
  const attr = target?.attribution;
  return (
    <Sheet open={!!target} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-full gap-0 border-gold/20 bg-navy sm:max-w-xl">
        {attr && target ? (
          <>
            <SheetHeader className="border-b border-border">
              <SheetTitle className="flex items-center gap-2 text-base">
                Provenance of <code className="text-gold-bright">{attr.param}</code>
              </SheetTitle>
              <SheetDescription className="break-all font-mono text-sm text-foreground">{attr.value}</SheetDescription>
              <div className="mt-2 flex items-start gap-2">
                <OriginChip origin={attr.origin} />
                <p className="text-xs text-muted-foreground">{ORIGIN_COPY[attr.origin]}</p>
              </div>
            </SheetHeader>
            <div className="flex flex-col gap-3 overflow-y-auto p-4">
              {attr.evidence.length === 0 ? (
                <p className="text-sm text-muted-foreground">No ledger entry contains this value.</p>
              ) : (
                attr.evidence.map((ev) => <EvidenceBlock key={ev.entry_id} sessionId={target.sessionId} ev={ev} />)
              )}
            </div>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}
