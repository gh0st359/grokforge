"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface Props {
  value: number; // 0..1
  threshold?: number; // 0..1
  label?: string;
}

export default function ConfidenceGauge({ value, threshold = 0.95, label = "confidence" }: Props) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  const r = 42;
  const circ = 2 * Math.PI * r;
  const dash = circ * (1 - value);
  const passed = value >= threshold;
  const color = passed ? "hsl(159 81% 58%)" : value > 0.7 ? "hsl(38 92% 60%)" : "hsl(350 89% 65%)";

  return (
    <div className="relative inline-flex flex-col items-center justify-center">
      <svg width="110" height="110" className="-rotate-90">
        <circle cx="55" cy="55" r={r} stroke="hsl(var(--border))" strokeWidth="6" fill="none" />
        <motion.circle
          cx="55" cy="55" r={r}
          stroke={color}
          strokeWidth="6"
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circ}
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: dash }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          style={{ filter: `drop-shadow(0 0 6px ${color}66)` }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={cn("text-2xl font-bold tabular-nums", passed ? "text-primary" : "text-foreground")}>
          {pct}%
        </span>
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</span>
      </div>
      <div className="mt-1 text-[10px] text-muted-foreground">
        threshold {Math.round(threshold * 100)}%
      </div>
    </div>
  );
}
