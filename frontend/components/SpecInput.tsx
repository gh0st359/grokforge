"use client";

import { useState } from "react";

const EXAMPLES = [
  "Build a real-time orbital mechanics simulator with N-body gravity and a /step endpoint that advances dt seconds.",
  "Build a FastAPI service that ingests a CSV of redshift measurements and returns a photometric-z histogram.",
  "Build a small training-pipeline coordinator that shards a dataset across workers and reports throughput.",
];

interface Props {
  onSubmit: (spec: string) => void;
  disabled?: boolean;
}

export default function SpecInput({ onSubmit, disabled }: Props) {
  const [spec, setSpec] = useState("");

  return (
    <section className="bg-forge-panel border border-forge-border rounded-lg p-6">
      <label className="block text-sm font-medium text-zinc-300 mb-2">Project spec</label>
      <textarea
        className="w-full h-32 bg-forge-bg border border-forge-border rounded-md p-3 font-mono text-sm focus:outline-none focus:border-forge-accent"
        placeholder="Describe the software you want grokforge to build..."
        value={spec}
        onChange={(e) => setSpec(e.target.value)}
        disabled={disabled}
      />
      <div className="mt-3 flex flex-wrap gap-2">
        {EXAMPLES.map((ex, i) => (
          <button
            key={i}
            type="button"
            className="text-xs px-2 py-1 rounded bg-forge-bg border border-forge-border text-zinc-400 hover:text-forge-accent hover:border-forge-accent"
            onClick={() => setSpec(ex)}
          >
            example {i + 1}
          </button>
        ))}
      </div>
      <div className="mt-4 flex justify-end">
        <button
          type="button"
          className="px-5 py-2 rounded-md bg-forge-accent text-black font-medium hover:opacity-90 disabled:opacity-50"
          disabled={!spec.trim() || disabled}
          onClick={() => onSubmit(spec)}
        >
          Forge it
        </button>
      </div>
    </section>
  );
}
