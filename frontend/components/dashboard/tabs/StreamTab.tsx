"use client";

import { useEffect, useRef, useState } from "react";
import { Filter } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import EventCard from "@/components/events/EventCard";
import type { AnyEvent } from "@/lib/events";

interface Props { events: AnyEvent[] }

const KIND_FILTERS: { value: string; label: string }[] = [
  { value: "all", label: "all" },
  { value: "thinking", label: "thoughts" },
  { value: "decision", label: "decisions" },
  { value: "file_written", label: "files" },
  { value: "debate_turn", label: "debate" },
  { value: "verification_signal", label: "signals" },
  { value: "tool_call", label: "tools" },
  { value: "metric", label: "metrics" },
];

export default function StreamTab({ events }: Props) {
  const [filter, setFilter] = useState<string>("all");
  const [autoscroll, setAutoscroll] = useState(true);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!autoscroll) return;
    const el = ref.current?.querySelector("[data-radix-scroll-area-viewport]") as HTMLDivElement | null;
    if (el) el.scrollTop = el.scrollHeight;
  }, [events, autoscroll]);

  const filtered = filter === "all" ? events : events.filter((e) => e.kind === filter);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 mb-3">
        <Filter className="h-3 w-3 text-muted-foreground" />
        <div className="flex flex-wrap gap-1">
          {KIND_FILTERS.map((f) => {
            const count = f.value === "all" ? events.length : events.filter((e) => e.kind === f.value).length;
            const active = filter === f.value;
            return (
              <button
                key={f.value}
                onClick={() => setFilter(f.value)}
                className={
                  active
                    ? "px-2 py-0.5 rounded text-[11px] bg-primary/15 text-primary border border-primary/30"
                    : "px-2 py-0.5 rounded text-[11px] bg-secondary/40 text-muted-foreground border border-border hover:text-foreground"
                }
              >
                {f.label} <span className="opacity-60 tabular-nums">{count}</span>
              </button>
            );
          })}
        </div>
        <label className="ml-auto flex items-center gap-1.5 text-[11px] text-muted-foreground cursor-pointer">
          <input
            type="checkbox" checked={autoscroll}
            onChange={(e) => setAutoscroll(e.target.checked)}
            className="accent-primary"
          />
          autoscroll
        </label>
      </div>
      <ScrollArea ref={ref} className="flex-1 rounded-md border border-border bg-card/40">
        <div className="p-3 divide-y divide-border/50">
          {filtered.length === 0 ? (
            <div className="text-center text-xs text-muted-foreground py-12">
              waiting for the swarm to start...
            </div>
          ) : (
            filtered.map((e, i) => <EventCard key={i} event={e} />)
          )}
        </div>
      </ScrollArea>
      <div className="text-[10px] text-muted-foreground text-right mt-1">
        showing {filtered.length} / {events.length} events
        {filter !== "all" && (
          <Badge variant="outline" className="ml-2 text-[9px]">filter: {filter}</Badge>
        )}
      </div>
    </div>
  );
}
