"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { API_URL, api } from "./api";
import type { Decision, KavachEvent, Lane, LaneSummary } from "./types";

/** Live SSE feed from the gateway, hydrated with the last run so a refresh never loses the demo. */
export function useEventStream() {
  const [events, setEvents] = useState<KavachEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const seen = useRef(new Set<number>());

  useEffect(() => {
    let source: EventSource | null = null;
    let cancelled = false;

    const push = (incoming: KavachEvent[]) => {
      const fresh = incoming.filter((e) => !seen.current.has(e.seq));
      if (!fresh.length) return;
      fresh.forEach((e) => seen.current.add(e.seq));
      setEvents((prev) => [...prev, ...fresh].sort((a, b) => a.seq - b.seq));
    };

    api<{ events: KavachEvent[] }>("/demo/last")
      .then((last) => !cancelled && push(last.events))
      .catch(() => undefined)
      .finally(() => {
        if (cancelled) return;
        const since = Math.max(0, ...Array.from(seen.current));
        source = new EventSource(`${API_URL}/events?since=${since}`);
        source.onopen = () => setConnected(true);
        source.onerror = () => setConnected(false);
        source.onmessage = (msg) => {
          try {
            push([JSON.parse(msg.data) as KavachEvent]);
          } catch {
            /* ignore malformed frames */
          }
        };
      });

    return () => {
      cancelled = true;
      source?.close();
    };
  }, []);

  return { events, connected };
}

export interface Card {
  key: string;
  thought: string;
  decision: Decision;
  error: string | null;
}

export interface LaneView {
  cards: Card[];
  summary: LaneSummary | null;
}

export interface RunView {
  runId: string | null;
  status: "idle" | "running" | "finished" | "failed";
  lanes: Record<Lane, LaneView>;
}

/** Fold the raw event stream into per-lane cards for the latest run. */
export function useLatestRun(events: KavachEvent[]): RunView {
  return useMemo(() => {
    const started = [...events].reverse().find((e) => e.kind === "run_started");
    const empty = (): LaneView => ({ cards: [], summary: null });
    const view: RunView = { runId: started?.run_id ?? null, status: "idle", lanes: { off: empty(), on: empty() } };
    if (!started) return view;
    view.status = "running";
    const pending: Record<Lane, string> = { off: "", on: "" };
    for (const e of events) {
      if (e.run_id !== started.run_id) continue;
      if (e.kind === "thought" && e.lane) pending[e.lane] = String(e.data.text ?? "");
      if (e.kind === "decision" && e.lane) {
        const decision = e.data.decision as Decision;
        view.lanes[e.lane].cards.push({
          key: decision.call_id,
          thought: pending[e.lane],
          decision,
          error: (e.data.error as string | null) ?? null,
        });
        pending[e.lane] = "";
      }
      if (e.kind === "run_finished") {
        view.status = "finished";
        for (const lane of ["off", "on"] as Lane[]) {
          view.lanes[lane].summary = (e.data[lane] as LaneSummary) ?? null;
        }
      }
      if (e.kind === "run_failed") view.status = "failed";
    }
    return view;
  }, [events]);
}
