import { CheckCircle2, CircleAlert, CircleHelp, Eraser, OctagonX, ShieldAlert, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Origin, Verdict } from "@/lib/types";

const VERDICT_STYLE: Record<Verdict, { cls: string; label: string; Icon: typeof Zap }> = {
  ALLOW: { cls: "bg-allow/15 text-[#5fd394] ring-allow/50", label: "ALLOW", Icon: CheckCircle2 },
  SANITISE: { cls: "bg-sanitise/20 text-[#b79cff] ring-sanitise/60", label: "SANITISE", Icon: Eraser },
  ESCALATE: { cls: "bg-escalate/20 text-[#f5b14a] ring-escalate/60", label: "ESCALATE", Icon: ShieldAlert },
  BLOCK: { cls: "bg-block/20 text-[#ff8a7d] ring-block/60", label: "BLOCK", Icon: OctagonX },
  PASSTHROUGH: { cls: "bg-white/5 text-muted-foreground ring-white/15", label: "EXECUTED", Icon: Zap },
};

export function VerdictBadge({ verdict, size = "md" }: { verdict: Verdict; size?: "sm" | "md" }) {
  const { cls, label, Icon } = VERDICT_STYLE[verdict];
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded-md font-semibold tracking-wider ring-1",
        size === "md" ? "px-2 py-0.5 text-[11px]" : "px-1.5 py-px text-[10px]",
        cls,
      )}
    >
      <Icon className={size === "md" ? "size-3.5" : "size-3"} />
      {label}
    </span>
  );
}

const ORIGIN_STYLE: Record<Origin, { cls: string; label: string; Icon: typeof Zap }> = {
  TRUSTED: { cls: "bg-allow/10 text-[#5fd394] ring-allow/40 hover:bg-allow/20", label: "trusted", Icon: CheckCircle2 },
  UNTRUSTED_ONLY: {
    cls: "bg-block/15 text-[#ff8a7d] ring-block/50 hover:bg-block/25",
    label: "untrusted only",
    Icon: CircleAlert,
  },
  UNKNOWN: { cls: "bg-escalate/15 text-[#f5b14a] ring-escalate/50 hover:bg-escalate/25", label: "unknown", Icon: CircleHelp },
};

export function OriginChip({ origin, onClick, source }: { origin: Origin; onClick?: () => void; source?: string }) {
  const { cls, label, Icon } = ORIGIN_STYLE[origin];
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!onClick}
      title="Show provenance evidence"
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ring-1 transition-colors disabled:cursor-default",
        cls,
      )}
    >
      <Icon className="size-3" />
      {label}
      {source ? <span className="opacity-70">· {source}</span> : null}
    </button>
  );
}

export function RuleChip({ rule }: { rule: string }) {
  return (
    <span className="rounded bg-gold/10 px-1.5 py-px font-mono text-[10px] text-gold-bright ring-1 ring-gold/30">
      {rule}
    </span>
  );
}
