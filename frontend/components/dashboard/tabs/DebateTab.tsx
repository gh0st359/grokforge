"use client";

import { motion } from "framer-motion";
import { MessageSquare, Gavel } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { AnyEvent } from "@/lib/events";

interface Props { events: AnyEvent[] }

interface Turn { role: "proponent" | "skeptic" | "judge"; round: number; content: string; ts: string }

export default function DebateTab({ events }: Props) {
  const turns: Turn[] = events
    .filter((e) => e.kind === "debate_turn")
    .map((e) => ({
      role: e.payload.role,
      round: e.payload.round,
      content: e.payload.content,
      ts: e.ts,
    }));

  // Group turns by round.
  const rounds = new Map<number, Turn[]>();
  for (const t of turns) {
    if (!rounds.has(t.round)) rounds.set(t.round, []);
    rounds.get(t.round)!.push(t);
  }

  if (turns.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-[40vh] text-muted-foreground">
        <MessageSquare className="h-12 w-12 opacity-30 mb-3" />
        <div className="text-sm">no debate yet</div>
        <div className="text-xs mt-1">the Verifier spins up the proponent/skeptic loop after the Reviewer</div>
      </div>
    );
  }

  return (
    <ScrollArea className="h-[60vh]">
      <div className="space-y-6 pr-3">
        {Array.from(rounds.entries())
          .sort(([a], [b]) => a - b)
          .map(([round, ts]) => (
            <div key={round}>
              <div className="flex items-center gap-2 mb-3">
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  round {round}
                </div>
                <div className="flex-1 h-px bg-border" />
              </div>
              <div className="space-y-3">
                {ts.map((t, i) => <Turn key={i} turn={t} />)}
              </div>
            </div>
          ))}
      </div>
    </ScrollArea>
  );
}

function Turn({ turn }: { turn: Turn }) {
  const isJudge = turn.role === "judge";
  const isPro = turn.role === "proponent";
  const align = isJudge ? "justify-center" : isPro ? "justify-start" : "justify-end";
  const bg =
    isJudge ? "bg-violet-500/10 border-violet-500/30 text-violet-100" :
    isPro   ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-50" :
              "bg-rose-500/10 border-rose-500/30 text-rose-50";

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={cn("flex", align)}
    >
      <Card className={cn("max-w-[85%] p-4", bg, "border")}>
        <div className="flex items-center gap-2 mb-2">
          {isJudge ? <Gavel className="h-4 w-4" /> : <MessageSquare className="h-4 w-4" />}
          <Badge variant="outline" className="uppercase text-[10px]">{turn.role}</Badge>
        </div>
        <div className="text-sm whitespace-pre-wrap leading-relaxed">{turn.content}</div>
      </Card>
    </motion.div>
  );
}
