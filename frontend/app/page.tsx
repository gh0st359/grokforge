"use client";

import { useState } from "react";
import SpecInput from "@/components/SpecInput";
import SwarmView from "@/components/SwarmView";
import AgentLog from "@/components/AgentLog";

const CORE_URL = process.env.NEXT_PUBLIC_CORE_URL || "http://localhost:8080";

export default function Home() {
  const [jobId, setJobId] = useState<string | null>(null);

  async function submit(spec: string) {
    const r = await fetch(`${CORE_URL}/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ spec }),
    });
    if (!r.ok) {
      const t = await r.text();
      alert(`submit failed: ${t}`);
      return;
    }
    const { id } = await r.json();
    setJobId(id);
  }

  return (
    <main className="min-h-screen p-8 max-w-7xl mx-auto">
      <header className="mb-8">
        <h1 className="text-4xl font-bold tracking-tight">
          <span className="text-forge-accent">grok</span>forge
        </h1>
        <p className="text-sm text-zinc-400 mt-2">
          Describe a project. Watch the swarm build, test, verify, and ship it.
        </p>
      </header>

      <SpecInput onSubmit={submit} disabled={!!jobId && false} />

      {jobId && (
        <div className="mt-8 grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1">
            <SwarmView jobId={jobId} coreUrl={CORE_URL} />
          </div>
          <div className="lg:col-span-2">
            <AgentLog jobId={jobId} coreUrl={CORE_URL} />
          </div>
        </div>
      )}

      <footer className="mt-16 pt-8 border-t border-forge-border text-xs text-zinc-500">
        grokforge v0.1 — open-source · MIT · Grok-powered
      </footer>
    </main>
  );
}
