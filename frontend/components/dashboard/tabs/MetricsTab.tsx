"use client";

import { Card } from "@/components/ui/card";
import { Activity, Clock, Coins, Brain, Wrench } from "lucide-react";
import type { AnyEvent } from "@/lib/events";

interface Props { events: AnyEvent[] }

export default function MetricsTab({ events }: Props) {
  const byAgent: Record<string, { thoughts: number; tools: number; cost: number; durations: number[] }> = {};
  let totalCost = 0;
  let toolCalls = 0;

  for (const e of events) {
    const a = e.agent;
    byAgent[a] ??= { thoughts: 0, tools: 0, cost: 0, durations: [] };
    if (e.kind === "thinking") byAgent[a].thoughts++;
    if (e.kind === "tool_call") { byAgent[a].tools++; toolCalls++; }
    if (e.kind === "cost") {
      const d = e.payload?.delta_usd ?? 0;
      byAgent[a].cost += d;
      totalCost += d;
    }
    if (e.kind === "metric" && e.payload?.name === "stage_seconds") {
      byAgent[a].durations.push(e.payload.value);
    }
  }

  const stats = [
    { label: "events", value: events.length.toLocaleString(), icon: Activity },
    { label: "tool calls", value: toolCalls.toLocaleString(), icon: Wrench },
    { label: "thoughts", value: events.filter((e) => e.kind === "thinking").length.toLocaleString(), icon: Brain },
    { label: "spend", value: `$${totalCost.toFixed(4)}`, icon: Coins },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {stats.map((s) => {
          const Icon = s.icon;
          return (
            <Card key={s.label} className="p-4">
              <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
                <Icon className="h-3 w-3" />
                {s.label}
              </div>
              <div className="font-mono text-2xl font-semibold tabular-nums">{s.value}</div>
            </Card>
          );
        })}
      </div>

      <Card className="p-5">
        <h3 className="text-sm font-semibold mb-3">per-agent breakdown</h3>
        <div className="space-y-2">
          {Object.entries(byAgent).filter(([, v]) => v.thoughts + v.tools > 0).map(([agent, v]) => (
            <div key={agent} className="flex items-center gap-3 text-xs">
              <span className="capitalize w-24 font-medium">{agent}</span>
              <span className="text-muted-foreground">{v.thoughts} thoughts</span>
              <span className="text-muted-foreground">·</span>
              <span className="text-muted-foreground">{v.tools} tool calls</span>
              <span className="text-muted-foreground">·</span>
              {v.durations.length > 0 && (
                <>
                  <span className="text-muted-foreground inline-flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {v.durations[v.durations.length - 1].toFixed(2)}s
                  </span>
                  <span className="text-muted-foreground">·</span>
                </>
              )}
              <span className="text-primary tabular-nums ml-auto">${v.cost.toFixed(4)}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
