"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, BarChart3, BookLock, PackageCheck, ShieldCheck, UserCheck } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Live Demo", icon: Activity },
  { href: "/approvals", label: "Approvals", icon: UserCheck },
  { href: "/ledger", label: "Evidence Ledger", icon: BookLock },
  { href: "/registry", label: "Tool Registry", icon: PackageCheck },
  { href: "/benchmark", label: "Benchmark", icon: BarChart3 },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col md:flex border-r border-border bg-navy/80 backdrop-blur">
      <div className="flex items-center gap-2.5 px-5 py-6">
        <div className="grid size-9 place-items-center rounded-xl bg-gold/15 ring-1 ring-gold/40">
          <ShieldCheck className="size-5 text-gold-bright" />
        </div>
        <div>
          <div className="text-gold-gradient text-lg font-bold tracking-[0.2em]">KAVACH</div>
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Provable agent trust</div>
        </div>
      </div>
      <nav className="flex flex-col gap-1 px-3">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-gold/15 text-gold-bright ring-1 ring-gold/30"
                  : "text-muted-foreground hover:bg-navy-light hover:text-foreground",
              )}
            >
              <Icon className="size-4" />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto px-5 py-5 text-[11px] leading-relaxed text-muted-foreground">
        agent <span className="text-foreground">support-bot-1</span>
        <br />
        on behalf of <span className="text-foreground">operator@ourbank.in</span>
      </div>
    </aside>
  );
}
