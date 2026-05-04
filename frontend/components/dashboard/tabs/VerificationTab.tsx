"use client";

import { motion } from "framer-motion";
import { Check, X, ShieldAlert } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { AnyEvent } from "@/lib/events";

interface Props { events: AnyEvent[] }

interface Signal { name: string; value: number; passed: boolean; detail: string; ts: string }

const SIGNAL_DESCRIPTION: Record<string, string> = {
  execution: "did pytest exit 0 inside the sandbox?",
  review: "did the Reviewer find any high-severity issues?",
  debate: "what confidence did the proponent/skeptic Judge return?",
  symbolic: "did Z3 prove the math-heavy invariants from the spec?",
  consistency: "second-opinion derivation match (placeholder in v0.1)",
};

export default function VerificationTab({ events }: Props) {
  const latest: Record<string, Signal> = {};
  for (const e of events) {
    if (e.kind === "verification_signal") {
      latest[e.payload.name] = {
        name: e.payload.name,
        value: e.payload.value,
        passed: e.payload.passed,
        detail: e.payload.detail,
        ts: e.ts,
      };
    }
  }
  const signals = Object.values(latest);
  const issues = events.filter((e) => e.kind === "issue").map((e) => e.payload);

  if (signals.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-[40vh] text-muted-foreground">
        <ShieldAlert className="h-12 w-12 opacity-30 mb-3" />
        <div className="text-sm">no verification signals yet</div>
        <div className="text-xs mt-1">the Verifier emits these after the Reviewer approves</div>
      </div>
    );
  }

  const passing = signals.filter((s) => s.passed).length;

  return (
    <div className="space-y-4">
      <Card className="p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold">verification signals</h3>
          <Badge variant={passing === signals.length ? "success" : "warning"}>
            {passing}/{signals.length} passing
          </Badge>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {signals.map((s, i) => (
            <motion.div
              key={s.name}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className={cn(
                "rounded-md border p-3 space-y-2",
                s.passed ? "border-primary/30 bg-primary/5" : "border-destructive/30 bg-destructive/5",
              )}
            >
              <div className="flex items-center gap-2">
                {s.passed ? <Check className="h-4 w-4 text-primary" /> : <X className="h-4 w-4 text-destructive" />}
                <span className="text-sm font-semibold capitalize">{s.name}</span>
                <span className="ml-auto font-mono text-xs tabular-nums">
                  {Math.round(s.value * 100)}%
                </span>
              </div>
              <Progress value={s.value * 100} />
              <p className="text-xs text-muted-foreground">{s.detail}</p>
              <p className="text-[10px] text-muted-foreground italic">
                {SIGNAL_DESCRIPTION[s.name] ?? ""}
              </p>
            </motion.div>
          ))}
        </div>
      </Card>

      {issues.length > 0 && (
        <Card className="p-5">
          <h3 className="text-sm font-semibold mb-3">flagged issues</h3>
          <div className="space-y-2">
            {issues.map((iss, i) => (
              <div key={i} className="flex items-start gap-2 text-sm">
                <Badge variant={
                  iss.severity === "high" ? "destructive" :
                  iss.severity === "med" ? "warning" : "outline"
                }>{iss.severity}</Badge>
                <div className="flex-1 min-w-0">
                  <span className="font-mono text-xs text-muted-foreground">{iss.path}</span>
                  <div>{iss.summary}</div>
                  {iss.fix && <div className="text-xs text-muted-foreground italic mt-0.5">fix: {iss.fix}</div>}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
