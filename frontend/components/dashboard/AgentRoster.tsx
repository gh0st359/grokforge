"use client";

import { motion } from "framer-motion";
import {
  Brain, Code2, FlaskConical, Eye, Scale, Rocket, type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { AnyEvent, AgentName } from "@/lib/events";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

interface Props {
  events: AnyEvent[];
  currentStatus: string;
}

const AGENT_ROLES: { name: AgentName; icon: LucideIcon; role: string; color: string }[] = [
  { name: "planner",  icon: Brain,        role: "decomposes spec into milestones",        color: "agent-planner" },
  { name: "coder",    icon: Code2,        role: "writes production-grade source files",   color: "agent-coder" },
  { name: "tester",   icon: FlaskConical, role: "writes & runs pytest in a sandbox",       color: "agent-tester" },
  { name: "reviewer", icon: Eye,          role: "static + LLM critique with severity",     color: "agent-reviewer" },
  { name: "verifier", icon: Scale,        role: "debate + symbolic + 5-signal aggregate",  color: "agent-verifier" },
  { name: "deployer", icon: Rocket,       role: "Dockerfile + K8s + CI bundle",            color: "agent-deployer" },
];

const STATUS_TO_AGENT: Record<string, AgentName | null> = {
  planning:   "planner",
  coding:     "coder",
  testing:    "tester",
  reviewing:  "reviewer",
  verifying:  "verifier",
  deploying:  "deployer",
};

function counts(events: AnyEvent[], agent: AgentName) {
  let thinks = 0, decisions = 0, files = 0, debate = 0, signals = 0, costUsd = 0;
  for (const e of events) {
    if (e.agent !== agent) continue;
    if (e.kind === "thinking") thinks++;
    else if (e.kind === "decision") decisions++;
    else if (e.kind === "file_written") files++;
    else if (e.kind === "debate_turn") debate++;
    else if (e.kind === "verification_signal") signals++;
    else if (e.kind === "cost") costUsd += e.payload?.delta_usd || 0;
  }
  return { thinks, decisions, files, debate, signals, costUsd };
}

function lastThought(events: AnyEvent[], agent: AgentName): string | null {
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i];
    if (e.agent === agent && e.kind === "thinking") return e.payload?.content ?? null;
  }
  return null;
}

export default function AgentRoster({ events, currentStatus }: Props) {
  const activeAgent = STATUS_TO_AGENT[currentStatus.toLowerCase()];

  return (
    <TooltipProvider delayDuration={150}>
      <div className="flex flex-col gap-2">
        <div className="px-1 py-1 text-[10px] uppercase tracking-wider text-muted-foreground">
          agents
        </div>
        {AGENT_ROLES.map((a, i) => {
          const Icon = a.icon;
          const c = counts(events, a.name);
          const thought = lastThought(events, a.name);
          const isActive = activeAgent === a.name;
          const hasWorked = c.thinks + c.decisions + c.files + c.signals > 0;
          return (
            <motion.div
              key={a.name}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
            >
              <Tooltip>
                <TooltipTrigger asChild>
                  <Card className={cn(
                    "p-3 transition-all hover:border-primary/40",
                    isActive && "border-amber-500/40 shadow-md shadow-amber-500/5",
                    !hasWorked && !isActive && "opacity-60",
                  )}>
                    <div className="flex items-center gap-3">
                      <div className={cn(
                        "h-9 w-9 rounded-md grid place-items-center shrink-0 border",
                        isActive ? "bg-amber-500/10 border-amber-500/30" : "bg-secondary/50 border-border",
                      )}>
                        <Icon className={cn("h-4 w-4", `text-${a.color}`)} style={{ color: `var(--tw-${a.color}, currentColor)` }} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-semibold capitalize">{a.name}</span>
                          {isActive && (
                            <Badge variant="warning" className="text-[10px]">
                              <span className="inline-block h-1.5 w-1.5 rounded-full bg-amber-300 mr-1 animate-pulse" />
                              active
                            </Badge>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground truncate">{a.role}</p>
                        {hasWorked && (
                          <div className="mt-1.5 flex flex-wrap gap-1 text-[10px] tabular-nums">
                            {c.thinks > 0    && <span className="text-muted-foreground">{c.thinks} thoughts</span>}
                            {c.decisions > 0 && <span className="text-muted-foreground">· {c.decisions} decisions</span>}
                            {c.files > 0     && <span className="text-muted-foreground">· {c.files} files</span>}
                            {c.debate > 0    && <span className="text-muted-foreground">· {c.debate} turns</span>}
                            {c.signals > 0   && <span className="text-muted-foreground">· {c.signals} signals</span>}
                            {c.costUsd > 0   && <span className="text-primary">· ${c.costUsd.toFixed(4)}</span>}
                          </div>
                        )}
                      </div>
                    </div>
                  </Card>
                </TooltipTrigger>
                {thought && (
                  <TooltipContent side="right">
                    <span className="text-muted-foreground">last thought:</span> {thought.slice(0, 200)}
                  </TooltipContent>
                )}
              </Tooltip>
            </motion.div>
          );
        })}
      </div>
    </TooltipProvider>
  );
}
