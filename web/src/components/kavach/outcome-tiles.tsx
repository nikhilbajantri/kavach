"use client";

import { useEffect, useState } from "react";
import { animate } from "motion/react";
import { FileWarning, IndianRupee, ListChecks } from "lucide-react";
import { formatINR } from "@/lib/api";
import type { LaneSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

function Count({ value, format }: { value: number | null; format: (n: number) => string }) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    if (value === null) return;
    const controls = animate(0, value, { duration: 1.1, ease: "easeOut", onUpdate: (v) => setShown(v) });
    return () => controls.stop();
  }, [value]);
  return <>{value === null ? "—" : format(Math.round(shown))}</>;
}

function Tile({
  icon: Icon,
  label,
  off,
  on,
  format,
  goodWhenZero,
}: {
  icon: typeof IndianRupee;
  label: string;
  off: number | null;
  on: number | null;
  format: (n: number) => string;
  goodWhenZero: boolean;
}) {
  const offBad = goodWhenZero && (off ?? 0) > 0;
  const onGood = goodWhenZero ? on === 0 : on !== null;
  return (
    <div className="flex-1 rounded-xl border border-border bg-navy/90 px-4 py-3">
      <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-muted-foreground">
        <Icon className="size-3.5 text-gold" /> {label}
      </div>
      <div className="mt-1.5 grid grid-cols-2 gap-3">
        <div>
          <div className="text-[10px] text-muted-foreground">Without KAVACH</div>
          <div className={cn("tabular text-2xl font-bold", offBad ? "text-[#ff8a7d]" : "text-foreground")}>
            <Count value={off} format={format} />
          </div>
        </div>
        <div>
          <div className="text-[10px] text-muted-foreground">With KAVACH</div>
          <div className={cn("tabular text-2xl font-bold", onGood ? "text-[#5fd394]" : "text-foreground")}>
            <Count value={on} format={format} />
          </div>
        </div>
      </div>
    </div>
  );
}

export function OutcomeTiles({ off, on }: { off: LaneSummary | null; on: LaneSummary | null }) {
  const total = on?.tasks_total ?? off?.tasks_total ?? 4;
  return (
    <div className="flex flex-col gap-3 md:flex-row">
      <Tile
        icon={IndianRupee}
        label="Money sent to the attacker"
        off={off?.money_to_attacker_inr ?? null}
        on={on?.money_to_attacker_inr ?? null}
        format={formatINR}
        goodWhenZero
      />
      <Tile
        icon={FileWarning}
        label="KYC records leaked"
        off={off?.kyc_records_leaked ?? null}
        on={on?.kyc_records_leaked ?? null}
        format={(n) => String(n)}
        goodWhenZero
      />
      <Tile
        icon={ListChecks}
        label="Legitimate tickets completed"
        off={off?.tasks_completed ?? null}
        on={on?.tasks_completed ?? null}
        format={(n) => `${n}/${total}`}
        goodWhenZero={false}
      />
    </div>
  );
}
