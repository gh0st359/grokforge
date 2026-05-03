"use client";

import { useEffect, useState } from "react";

interface Job {
  id: string;
  status: string;
  confidence: number;
  cost_usd: number;
  debate_rounds: number;
}

const STAGES = ["queued", "planning", "coding", "testing", "reviewing", "verifying", "deploying", "succeeded"];

interface Props { jobId: string; coreUrl: string }

export default function SwarmView({ jobId, coreUrl }: Props) {
  const [job, setJob] = useState<Job | null>(null);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const r = await fetch(`${coreUrl}/jobs/${jobId}`);
        if (r.ok && !cancelled) setJob(await r.json());
      } catch {}
    };
    tick();
    const id = setInterval(tick, 1500);
    return () => { cancelled = true; clearInterval(id); };
  }, [jobId, coreUrl]);

  return (
    <aside className="bg-forge-panel border border-forge-border rounded-lg p-5 sticky top-4">
      <div className="text-xs text-zinc-500 mb-3">job</div>
      <div className="font-mono text-xs text-zinc-300 break-all mb-4">{jobId}</div>

      <ul className="space-y-2">
        {STAGES.map((s) => {
          const idx = STAGES.indexOf(s);
          const cur = job ? STAGES.indexOf(job.status) : -1;
          const state = idx < cur ? "done" : idx === cur ? "active" : "pending";
          return (
            <li key={s} className="flex items-center gap-3">
              <span className={
                state === "done" ? "w-2 h-2 rounded-full bg-forge-accent" :
                state === "active" ? "w-2 h-2 rounded-full bg-forge-warn animate-pulse" :
                "w-2 h-2 rounded-full bg-forge-border"
              } />
              <span className={state === "pending" ? "text-zinc-600 text-sm" : "text-zinc-200 text-sm"}>
                {s}
              </span>
            </li>
          );
        })}
      </ul>

      {job && (
        <div className="mt-6 space-y-2 text-xs">
          <Stat label="confidence" value={`${(job.confidence * 100).toFixed(1)}%`} />
          <Stat label="debate rounds" value={`${job.debate_rounds}`} />
          <Stat label="cost" value={`$${job.cost_usd.toFixed(4)}`} />
        </div>
      )}
    </aside>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-zinc-500">{label}</span>
      <span className="font-mono text-zinc-200">{value}</span>
    </div>
  );
}
