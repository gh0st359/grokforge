"use client";

import { motion, animate, useMotionValue, useTransform } from "framer-motion";
import { useEffect } from "react";
import { DollarSign } from "lucide-react";

interface Props { value: number }

export default function CostTicker({ value }: Props) {
  const mv = useMotionValue(0);
  const display = useTransform(mv, (v) => `$${v.toFixed(4)}`);

  useEffect(() => {
    const controls = animate(mv, value, { duration: 0.8, ease: "easeOut" });
    return controls.stop;
  }, [value, mv]);

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground">
        <DollarSign className="h-3 w-3" />
        token spend
      </div>
      <motion.span className="font-mono text-xl font-semibold tabular-nums text-primary">
        {display}
      </motion.span>
    </div>
  );
}
