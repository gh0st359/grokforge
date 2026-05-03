"use client";

import { useEffect, useRef, useState } from "react";

interface Event {
  ts: string;
  agent: string;
  kind: string;
  payload: any;
}

interface Props { jobId: string; coreUrl: string }

const AGENT_COLORS: Record<string, string> = {
  planner: "text-sky-400",
  coder: "text-emerald-400",
  tester: "text-amber-400",
  reviewer: "text-fuchsia-400",
  verifier: "text-rose-400",
  deployer: "text-cyan-400",
  orchestrator: "text-zinc-400",
};

export default function AgentLog({ jobId, coreUrl }: Props) {
  const [events, setEvents] = useState<Event[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const es = new EventSource(`${coreUrl}/jobs/${jobId}/events`);
    const onAny = (ev: MessageEvent) => {
      try {
        const parsed = JSON.parse(ev.data);
        setEvents((prev) => [...prev, parsed].slice(-500));
      } catch {}
    };
    ["log", "status", "artifact", "cost", "error", "verdict"].forEach((k) =>
      es.addEventListener(k, onAny as EventListener)
    );
    es.onerror = () => { /* SSE auto-reconnects */ };
    return () => es.close();
  }, [jobId, coreUrl]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [events]);

  return (
    <section className="bg-forge-panel border border-forge-border rounded-lg p-5">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-medium text-zinc-300">live agent log</h2>
        <span className="text-xs text-zinc-500">{events.length} events</span>
      </div>
      <div
        ref={scrollRef}
        className="h-[60vh] overflow-y-auto font-mono text-xs bg-forge-bg border border-forge-border rounded p-3 space-y-1"
      >
        {events.length === 0 && (
          <div className="text-zinc-600">waiting for the swarm to start...</div>
        )}
        {events.map((ev, i) => (
          <Line key={i} ev={ev} />
        ))}
      </div>
    </section>
  );
}

function Line({ ev }: { ev: Event }) {
  const color = AGENT_COLORS[ev.agent] || "text-zinc-300";
  const t = new Date(ev.ts).toLocaleTimeString();
  let body = "";
  if (ev.kind === "log") body = ev.payload?.line ?? "";
  else if (ev.kind === "status") body = `→ ${JSON.stringify(ev.payload)}`;
  else if (ev.kind === "cost") body = `+$${ev.payload?.delta_usd?.toFixed?.(4) ?? "0"}`;
  else if (ev.kind === "error") body = `ERROR ${JSON.stringify(ev.payload)}`;
  else body = `${ev.kind} ${shortJson(ev.payload)}`;
  return (
    <div className="flex gap-3">
      <span className="text-zinc-600 shrink-0">{t}</span>
      <span className={`${color} shrink-0 w-20`}>{ev.agent}</span>
      <span className="text-zinc-300 break-words">{body}</span>
    </div>
  );
}

function shortJson(p: any): string {
  try {
    const s = JSON.stringify(p);
    return s.length > 200 ? s.slice(0, 200) + "..." : s;
  } catch { return ""; }
}
