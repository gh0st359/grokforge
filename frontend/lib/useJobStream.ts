"use client";

import { useEffect, useRef, useState } from "react";
import type { AnyEvent } from "./events";
import { ALL_EVENT_KINDS } from "./events";

export interface JobInfo {
  id: string;
  spec: string;
  status: string;
  confidence: number;
  cost_usd: number;
  debate_rounds: number;
}

export interface JobStreamState {
  job: JobInfo | null;
  events: AnyEvent[];
  connected: boolean;
}

export function useJobStream(jobId: string | null, coreUrl: string): JobStreamState {
  const [job, setJob] = useState<JobInfo | null>(null);
  const [events, setEvents] = useState<AnyEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!jobId) return;

    let stopped = false;

    // Polling for job summary state.
    const pollJob = async () => {
      try {
        const r = await fetch(`${coreUrl}/jobs/${jobId}`);
        if (r.ok && !stopped) setJob(await r.json());
      } catch {}
    };
    pollJob();
    const id = setInterval(pollJob, 1500);

    // SSE for the rich event stream.
    const es = new EventSource(`${coreUrl}/jobs/${jobId}/events`);
    esRef.current = es;
    const handle = (ev: MessageEvent) => {
      try {
        const parsed = JSON.parse(ev.data) as AnyEvent;
        setEvents((prev) => {
          const next = [...prev, parsed];
          return next.length > 1500 ? next.slice(-1500) : next;
        });
      } catch {}
    };
    ALL_EVENT_KINDS.forEach((k) => es.addEventListener(k, handle as EventListener));
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);

    return () => {
      stopped = true;
      clearInterval(id);
      es.close();
    };
  }, [jobId, coreUrl]);

  return { job, events, connected };
}

export function fileMapFromEvents(events: AnyEvent[]): Record<string, { content: string; language: string; lines: number }> {
  const out: Record<string, { content: string; language: string; lines: number }> = {};
  for (const e of events) {
    if (e.kind === "file_written") {
      const p = e.payload;
      out[p.path] = { content: p.content, language: p.language, lines: p.lines };
    }
  }
  return out;
}
