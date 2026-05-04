"use client";

import { useState } from "react";
import { Toaster, toast } from "sonner";
import { Sparkles, Zap, Github } from "lucide-react";
import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import SpecForm from "@/components/dashboard/SpecForm";
import Dashboard from "@/components/dashboard/Dashboard";
import CoreStatusBanner from "@/components/dashboard/CoreStatusBanner";
import { useCoreHealth } from "@/lib/useCoreHealth";

const CORE_URL = process.env.NEXT_PUBLIC_CORE_URL || "http://localhost:8080";

export default function Home() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const health = useCoreHealth(CORE_URL);

  const submit = async (spec: string) => {
    if (health.status !== "online") {
      toast.error("core is offline — fix the banner above first");
      return;
    }
    setBusy(true);
    try {
      const r = await fetch(`${CORE_URL}/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ spec }),
      });
      if (!r.ok) {
        const t = await r.text();
        toast.error(`submit failed: ${t.slice(0, 200)}`);
        return;
      }
      const { id } = await r.json();
      setJobId(id);
      toast.success("forge started — watching the swarm");
    } catch (e: any) {
      toast.error(`network error: ${e?.message ?? e}`);
    } finally {
      setBusy(false);
    }
  };

  const reset = () => setJobId(null);

  return (
    <main className="min-h-screen container py-8 max-w-[1400px]">
      <Toaster position="top-right" theme="dark" richColors />

      <motion.header
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between mb-6"
      >
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-lg bg-gradient-to-br from-primary to-emerald-300 grid place-items-center shadow-lg shadow-primary/30">
            <Zap className="h-5 w-5 text-background" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              <span className="text-primary">grok</span>forge
            </h1>
            <p className="text-xs text-muted-foreground -mt-0.5">
              autonomous multi-agent AI engineering · grok-powered
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <CoreStatusBanner health={health} coreUrl={CORE_URL} />
          <Badge variant="outline" className="gap-1">
            <Sparkles className="h-3 w-3 text-primary" /> v0.1
          </Badge>
          <a
            href="https://github.com/gh0st359/grokforge"
            target="_blank"
            rel="noreferrer"
            className="p-2 rounded-md hover:bg-secondary transition-colors"
          >
            <Github className="h-4 w-4 text-muted-foreground" />
          </a>
          {jobId && (
            <button
              onClick={reset}
              className="text-xs px-3 py-1.5 rounded-md border border-border hover:bg-secondary transition-colors"
            >
              new job
            </button>
          )}
        </div>
      </motion.header>

      {/* Full banner only when offline; the header pill covers the healthy case. */}
      {health.status === "offline" && <CoreStatusBanner health={health} coreUrl={CORE_URL} />}

      {!jobId ? (
        <div className="max-w-3xl mx-auto mt-12">
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="text-center mb-8"
          >
            <h2 className="text-4xl md:text-5xl font-bold tracking-tight mb-3">
              describe it. <span className="text-primary">we build it.</span>
            </h2>
            <p className="text-muted-foreground max-w-xl mx-auto">
              A swarm of specialized agents — Planner, Coder, Tester, Reviewer, Verifier, Deployer —
              works through your spec end to end. Watch every thought, every line of code, every
              debate round live.
            </p>
          </motion.div>
          <SpecForm onSubmit={submit} busy={busy || health.status !== "online"} />
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
            className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-8"
          >
            <Feature
              title="truth-seeking verification"
              body="proponent vs skeptic debate, Z3 symbolic checks, 5-signal confidence aggregation."
            />
            <Feature
              title="live everything"
              body="every agent's reasoning, decisions, code, tests, and debate transcripts streamed in real time."
            />
            <Feature
              title="zero-trust execution"
              body="Rust-supervised sandbox with rlimits, scrubbed env, and hard wall timeouts."
            />
          </motion.div>
        </div>
      ) : (
        <Dashboard jobId={jobId} coreUrl={CORE_URL} />
      )}

      <footer className="mt-16 pt-6 border-t border-border text-xs text-muted-foreground flex justify-between">
        <span>grokforge · MIT · open source</span>
        <span>powered by grok 4.x</span>
      </footer>
    </main>
  );
}

function Feature({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-lg border border-border bg-card/50 p-4">
      <div className="text-sm font-semibold mb-1">{title}</div>
      <div className="text-xs text-muted-foreground leading-relaxed">{body}</div>
    </div>
  );
}
