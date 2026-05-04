"use client";

import { motion } from "framer-motion";
import { Check, Loader2, Circle } from "lucide-react";
import { cn } from "@/lib/utils";
import { STAGES, Stage } from "@/lib/events";

interface Props { current: string }

const PIPELINE: Stage[] = ["planning", "coding", "testing", "reviewing", "verifying", "deploying"];

export default function StageProgress({ current }: Props) {
  const cur = current.toLowerCase();
  const idx = PIPELINE.indexOf(cur as Stage);
  const succeeded = cur === "succeeded";
  const failed = cur === "failed";

  return (
    <div className="flex items-center gap-1.5">
      {PIPELINE.map((s, i) => {
        const isDone = succeeded || i < idx;
        const isActive = !succeeded && !failed && i === idx;
        const isFailed = failed && i === idx;
        return (
          <div key={s} className="flex items-center gap-1.5">
            <motion.div
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ delay: i * 0.04 }}
              className={cn(
                "flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-xs",
                isDone && "bg-primary/15 border-primary/30 text-primary",
                isActive && "bg-amber-500/15 border-amber-500/40 text-amber-300 animate-pulse-soft",
                isFailed && "bg-destructive/15 border-destructive/40 text-destructive",
                !isDone && !isActive && !isFailed && "bg-secondary/30 border-border text-muted-foreground",
              )}
            >
              {isDone ? <Check className="h-3 w-3" /> :
               isActive ? <Loader2 className="h-3 w-3 animate-spin" /> :
               <Circle className="h-3 w-3" />}
              <span className="capitalize">{s}</span>
            </motion.div>
            {i < PIPELINE.length - 1 && (
              <div className={cn("h-px w-3", isDone ? "bg-primary/40" : "bg-border")} />
            )}
          </div>
        );
      })}
    </div>
  );
}
