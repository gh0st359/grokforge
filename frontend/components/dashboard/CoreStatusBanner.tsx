"use client";

import { motion, AnimatePresence } from "framer-motion";
import { AlertCircle, CheckCircle2, Loader2, RefreshCcw, Terminal } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { CoreHealth } from "@/lib/useCoreHealth";

interface Props {
  health: CoreHealth;
  coreUrl: string;
}

/**
 * Renders a sticky banner when the core service is unreachable. Tells the user
 * exactly what to run to get it back. Stays out of the way (collapsed status
 * pill) while the service is healthy.
 */
export default function CoreStatusBanner({ health, coreUrl }: Props) {
  if (health.status === "online") {
    return (
      <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
        <CheckCircle2 className="h-3 w-3 text-primary" />
        <span>core online</span>
        <span className="font-mono opacity-60">{coreUrl.replace(/^https?:\/\//, "")}</span>
      </div>
    );
  }

  if (health.status === "checking") {
    return (
      <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" />
        <span>checking core…</span>
      </div>
    );
  }

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -8 }}
      >
        <Card className={cn(
          "border-destructive/40 bg-destructive/5 p-4 mb-6",
        )}>
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-semibold text-sm">core service is offline</span>
                <Badge variant="destructive" className="text-[10px]">
                  {health.lastError ?? "ECONNREFUSED"}
                </Badge>
                <code className="text-[11px] font-mono text-muted-foreground">{coreUrl}</code>
                <Button
                  size="sm"
                  variant="outline"
                  className="ml-auto h-7 gap-1.5"
                  onClick={health.retryNow}
                >
                  <RefreshCcw className="h-3 w-3" />
                  retry now
                </Button>
              </div>
              <p className="text-xs text-muted-foreground mt-1.5">
                The frontend can&apos;t reach the Rust orchestrator. The swarm runs
                inside the <code className="text-foreground">core</code> service —
                without it, jobs cannot be submitted.
              </p>
              <div className="mt-3 grid gap-2">
                <Step
                  n={1}
                  label="Confirm the core container is running"
                  cmd="docker compose ps core"
                  hint="STATUS should say 'Up' and have a healthcheck of 'healthy'"
                />
                <Step
                  n={2}
                  label="If it's not up, start it"
                  cmd="docker compose up -d --build core"
                  hint="first build takes 3–6 min — Rust compiles from source"
                />
                <Step
                  n={3}
                  label="Tail core logs to see why it crashed"
                  cmd="docker compose logs -f core"
                  hint="look for 'api listening' to confirm it bound :8080"
                />
                <Step
                  n={4}
                  label="Sanity check from your shell"
                  cmd={`curl -fsS ${coreUrl}/health`}
                  hint="should print 'ok'"
                />
              </div>
            </div>
          </div>
        </Card>
      </motion.div>
    </AnimatePresence>
  );
}

function Step({ n, label, cmd, hint }: { n: number; label: string; cmd: string; hint: string }) {
  const copy = () => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(cmd).catch(() => {});
    }
  };
  return (
    <div className="rounded-md border border-border bg-card/50 p-2.5">
      <div className="flex items-start gap-2">
        <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-secondary text-[10px] font-bold tabular-nums">
          {n}
        </span>
        <div className="flex-1 min-w-0">
          <div className="text-xs font-medium">{label}</div>
          <button
            onClick={copy}
            title="copy command"
            className="mt-1 flex items-center gap-2 w-full text-left rounded bg-background/60 border border-border px-2 py-1 hover:border-primary/40 transition-colors group"
          >
            <Terminal className="h-3 w-3 text-muted-foreground group-hover:text-primary" />
            <code className="font-mono text-xs text-foreground/90 break-all">{cmd}</code>
          </button>
          <div className="text-[10px] text-muted-foreground mt-1">{hint}</div>
        </div>
      </div>
    </div>
  );
}
