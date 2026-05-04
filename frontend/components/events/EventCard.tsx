"use client";

import { motion } from "framer-motion";
import {
  Brain, GitBranch, Wrench, FileCode2, MessageSquare, ShieldCheck,
  Activity, DollarSign, AlertTriangle, ScrollText,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn, formatTime } from "@/lib/utils";
import type { AnyEvent } from "@/lib/events";
import CodeBlock from "@/components/code/CodeBlock";

const KIND_ICON: Record<string, LucideIcon> = {
  thinking: Brain,
  decision: GitBranch,
  tool_call: Wrench,
  code_chunk: FileCode2,
  file_written: FileCode2,
  debate_turn: MessageSquare,
  verification_signal: ShieldCheck,
  metric: Activity,
  cost: DollarSign,
  issue: AlertTriangle,
  log: ScrollText,
  status: Activity,
  error: AlertTriangle,
  artifact: FileCode2,
};

const AGENT_DOT: Record<string, string> = {
  planner:      "bg-sky-400",
  coder:        "bg-emerald-400",
  tester:       "bg-amber-400",
  reviewer:     "bg-fuchsia-400",
  verifier:     "bg-rose-400",
  deployer:     "bg-cyan-400",
  orchestrator: "bg-zinc-400",
};

interface Props { event: AnyEvent }

export default function EventCard({ event }: Props) {
  const Icon = KIND_ICON[event.kind] ?? ScrollText;
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18 }}
      className="flex gap-3 py-2"
    >
      <div className="flex flex-col items-center pt-1">
        <span className={cn("h-2 w-2 rounded-full", AGENT_DOT[event.agent] ?? "bg-zinc-500")} />
        <div className="w-px flex-1 bg-border mt-1" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <Icon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
          <span className={cn("text-xs font-semibold capitalize", `text-${event.agent}`)} style={{
            color:
              event.agent === "planner" ? "hsl(199 89% 70%)" :
              event.agent === "coder" ? "hsl(160 84% 65%)" :
              event.agent === "tester" ? "hsl(38 92% 65%)" :
              event.agent === "reviewer" ? "hsl(290 84% 70%)" :
              event.agent === "verifier" ? "hsl(350 89% 70%)" :
              event.agent === "deployer" ? "hsl(180 80% 65%)" :
              "hsl(220 10% 70%)",
          }}>
            {event.agent}
          </span>
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">{event.kind.replace("_", " ")}</span>
          <span className="ml-auto text-[10px] text-muted-foreground tabular-nums">{formatTime(event.ts)}</span>
        </div>
        <Body event={event} />
      </div>
    </motion.div>
  );
}

function Body({ event }: { event: AnyEvent }) {
  const p = event.payload || {};
  switch (event.kind) {
    case "thinking":
      return (
        <div className="rounded-md border border-border/60 bg-secondary/30 p-3 italic text-sm text-foreground/85 leading-relaxed">
          <span className="text-muted-foreground not-italic mr-1">∴</span>
          {p.content}
          {p.scope && <span className="ml-2 text-[10px] text-muted-foreground not-italic">[{p.scope}]</span>}
        </div>
      );
    case "decision":
      return (
        <div className="space-y-1.5">
          <div className="text-sm font-medium">→ {p.decision}</div>
          {p.rationale && <div className="text-xs text-muted-foreground leading-relaxed">{p.rationale}</div>}
          {Array.isArray(p.alternatives) && p.alternatives.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {p.alternatives.map((a: string, i: number) => (
                <Badge key={i} variant="outline" className="text-[10px] line-through opacity-60">{a}</Badge>
              ))}
            </div>
          )}
        </div>
      );
    case "tool_call":
      return (
        <div className="text-xs font-mono">
          <span className="text-primary">{p.name}</span>
          <span className="text-muted-foreground">({Object.keys(p.args || {}).slice(0, 4).join(", ")})</span>
          {p.result && <span className="text-muted-foreground"> ⇒ {JSON.stringify(p.result).slice(0, 80)}</span>}
        </div>
      );
    case "file_written":
      return (
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 text-sm">
            <span className="font-mono text-primary">{p.path}</span>
            <Badge variant="outline" className="text-[10px]">{p.language}</Badge>
            <span className="text-[10px] text-muted-foreground">{p.lines} lines · {p.bytes}B</span>
          </div>
          <CodeBlock code={p.content} language={p.language} maxHeight="220px" />
        </div>
      );
    case "code_chunk":
      return (
        <div className="space-y-1">
          <div className="text-xs font-mono text-muted-foreground">{p.path}</div>
          <CodeBlock code={p.content} language={p.language} maxHeight="160px" showLineNumbers={false} />
        </div>
      );
    case "debate_turn": {
      const role = p.role as "proponent" | "skeptic" | "judge";
      const color =
        role === "proponent" ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-200" :
        role === "skeptic"   ? "bg-rose-500/10 border-rose-500/30 text-rose-200" :
        "bg-violet-500/10 border-violet-500/30 text-violet-200";
      return (
        <div className={cn("rounded-md border p-3 text-sm whitespace-pre-wrap leading-relaxed", color)}>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="font-bold uppercase text-[10px] tracking-wider">{role}</span>
            <span className="text-[10px] opacity-70">round {p.round}</span>
          </div>
          {p.content}
        </div>
      );
    }
    case "verification_signal": {
      const v = Math.round((p.value ?? 0) * 100);
      return (
        <div className="flex items-center gap-2">
          <Badge variant={p.passed ? "success" : "destructive"} className="text-[10px] uppercase">
            {p.name}
          </Badge>
          <span className="font-mono text-xs tabular-nums">{v}%</span>
          <span className="text-xs text-muted-foreground truncate">{p.detail}</span>
        </div>
      );
    }
    case "metric":
      return (
        <div className="flex items-center gap-2 text-xs">
          <span className="text-muted-foreground">{p.name}:</span>
          <span className="font-mono tabular-nums text-foreground">{p.value}{p.unit ? ` ${p.unit}` : ""}</span>
        </div>
      );
    case "cost":
      return <div className="text-xs font-mono text-primary">+${(p.delta_usd ?? 0).toFixed(4)}</div>;
    case "issue":
      return (
        <div className="flex items-center gap-2 text-xs">
          <Badge variant={p.severity === "high" ? "destructive" : p.severity === "med" ? "warning" : "outline"}>
            {p.severity}
          </Badge>
          <span className="font-mono text-muted-foreground">{p.path}</span>
          <span>{p.summary}</span>
        </div>
      );
    case "log":
      return <div className="text-xs text-foreground/80 font-mono">{p.line}</div>;
    case "error":
      return (
        <div className="text-xs text-destructive font-mono">
          {p.message || JSON.stringify(p).slice(0, 200)}
        </div>
      );
    default:
      return (
        <div className="text-xs text-muted-foreground font-mono break-all">
          {JSON.stringify(p).slice(0, 240)}
        </div>
      );
  }
}
