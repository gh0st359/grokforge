"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Sparkles, Rocket, Beaker, Cpu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const EXAMPLES: { label: string; icon: any; spec: string }[] = [
  {
    label: "Orbital simulator",
    icon: Rocket,
    spec: "Build a real-time orbital mechanics simulator as a FastAPI service. POST /world creates a body system, POST /step advances by dt seconds with velocity-Verlet under Newtonian gravity, GET /energy returns kinetic+potential. Conserve total energy within 1e-3 over 50 steps for an Earth–Moon test.",
  },
  {
    label: "Photo-z processor",
    icon: Beaker,
    spec: "Build a FastAPI service that ingests a CSV of photometric measurements (id,u,g,r,i,z) and returns photo-z estimates plus a 50-bin histogram. Reject malformed CSVs with 400. Tests should cover the full ingest→estimate→histogram flow.",
  },
  {
    label: "Training coordinator",
    icon: Cpu,
    spec: "Build a small training-pipeline coordinator. POST /jobs accepts dataset_size+world_size+batch_size, returns shard ranges. POST /heartbeat updates per-worker throughput. GET /jobs/{id} returns aggregate throughput plus a stragglers list (>2σ below median).",
  },
];

interface Props {
  onSubmit: (spec: string) => Promise<void>;
  busy?: boolean;
}

export default function SpecForm({ onSubmit, busy }: Props) {
  const [spec, setSpec] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    if (!spec.trim()) return;
    setSubmitting(true);
    try { await onSubmit(spec); } finally { setSubmitting(false); }
  };

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
      <Card className="gradient-border">
        <CardContent className="p-6">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">describe what to build</h2>
            <Badge variant="info" className="ml-auto">grok-powered</Badge>
          </div>
          <Textarea
            value={spec}
            onChange={(e) => setSpec(e.target.value)}
            placeholder="Build a real-time orbital mechanics simulator with energy conservation tests..."
            className="min-h-[140px] font-mono text-sm resize-none"
            disabled={busy || submitting}
          />
          <div className="flex flex-wrap gap-2 mt-4">
            {EXAMPLES.map((ex) => {
              const Icon = ex.icon;
              return (
                <button
                  key={ex.label}
                  onClick={() => setSpec(ex.spec)}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-border bg-secondary/40 text-xs text-muted-foreground hover:text-foreground hover:border-primary/40 hover:bg-primary/5 transition-colors"
                  type="button"
                  disabled={busy || submitting}
                >
                  <Icon className="h-3 w-3" />
                  {ex.label}
                </button>
              );
            })}
          </div>
          <div className="mt-5 flex items-center justify-between">
            <p className="text-xs text-muted-foreground">
              the swarm will plan, code, test, debate, verify, and ship.
            </p>
            <Button onClick={submit} disabled={!spec.trim() || busy || submitting} size="lg" className="gap-2">
              <Sparkles className="h-4 w-4" />
              {submitting ? "submitting…" : "Forge it"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
