"use client";

import { useEffect, useRef, useState } from "react";

export type CoreStatus = "checking" | "online" | "offline";

export interface CoreHealth {
  status: CoreStatus;
  lastError?: string;
  lastChecked?: number;
  retryNow: () => void;
}

/**
 * Polls the core's `/health` endpoint at 3s intervals (faster while offline so
 * the banner clears the moment the user starts the service). Surfaces a
 * `CoreStatus` so UI can show a clear "core is offline — here's how to fix it"
 * banner instead of silent fetch failures in the console.
 */
export function useCoreHealth(coreUrl: string): CoreHealth {
  const [status, setStatus] = useState<CoreStatus>("checking");
  const [lastError, setLastError] = useState<string | undefined>();
  const [lastChecked, setLastChecked] = useState<number | undefined>();
  const tick = useRef<() => Promise<void>>(async () => {});

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const check = async () => {
      try {
        const ctrl = new AbortController();
        const t = setTimeout(() => ctrl.abort(), 2500);
        const r = await fetch(`${coreUrl}/health`, {
          signal: ctrl.signal,
          cache: "no-store",
        });
        clearTimeout(t);
        if (cancelled) return;
        if (r.ok) {
          setStatus("online");
          setLastError(undefined);
        } else {
          setStatus("offline");
          setLastError(`core returned HTTP ${r.status}`);
        }
      } catch (e: any) {
        if (cancelled) return;
        setStatus("offline");
        setLastError(e?.message ?? "connection refused");
      }
      setLastChecked(Date.now());
      // Faster poll while offline so the banner clears quickly once the user fixes it.
      const delay = cancelled ? 0 : status === "offline" ? 2000 : 5000;
      timer = setTimeout(check, delay);
    };

    tick.current = check;
    check();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [coreUrl]);

  return {
    status,
    lastError,
    lastChecked,
    retryNow: () => tick.current(),
  };
}
