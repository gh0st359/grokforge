"use client";

import { motion } from "framer-motion";
import {
  Activity, Code2, MessageSquare, ShieldCheck, BarChart3, Wifi, WifiOff,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import ConfidenceGauge from "./ConfidenceGauge";
import CostTicker from "./CostTicker";
import StageProgress from "./StageProgress";
import AgentRoster from "./AgentRoster";
import StreamTab from "./tabs/StreamTab";
import CodeTab from "./tabs/CodeTab";
import DebateTab from "./tabs/DebateTab";
import VerificationTab from "./tabs/VerificationTab";
import MetricsTab from "./tabs/MetricsTab";
import { useJobStream } from "@/lib/useJobStream";
import { fileMapFromEvents } from "@/lib/useJobStream";

interface Props { jobId: string; coreUrl: string }

export default function Dashboard({ jobId, coreUrl }: Props) {
  const { job, events, connected } = useJobStream(jobId, coreUrl);
  const fileCount = Object.keys(fileMapFromEvents(events)).length;
  const debateRounds = events.filter((e) => e.kind === "debate_turn").length;
  const issueCount = events.filter((e) => e.kind === "issue").length;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="grid grid-cols-12 gap-4"
    >
      {/* Top metrics strip */}
      <Card className="col-span-12 p-5">
        <div className="flex flex-col xl:flex-row gap-5 items-start xl:items-center">
          <div className="flex items-center gap-5">
            <ConfidenceGauge value={job?.confidence ?? 0} />
            <Separator orientation="vertical" className="h-16 hidden md:block" />
            <CostTicker value={job?.cost_usd ?? 0} />
            <Separator orientation="vertical" className="h-16 hidden md:block" />
            <div className="flex flex-col gap-1">
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
                debate rounds
              </div>
              <div className="font-mono text-xl font-semibold tabular-nums">
                {job?.debate_rounds ?? 0}
              </div>
            </div>
            <Separator orientation="vertical" className="h-16 hidden md:block" />
            <div className="flex flex-col gap-1">
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
                files emitted
              </div>
              <div className="font-mono text-xl font-semibold tabular-nums">
                {fileCount}
              </div>
            </div>
          </div>
          <div className="xl:ml-auto flex flex-col gap-3 w-full xl:w-auto">
            <div className="flex items-center gap-2">
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground">job</span>
              <code className="text-[10px] font-mono text-muted-foreground truncate max-w-[280px]">
                {jobId}
              </code>
              {connected ? (
                <Badge variant="success" className="ml-auto text-[10px] gap-1">
                  <Wifi className="h-3 w-3" /> live
                </Badge>
              ) : (
                <Badge variant="outline" className="ml-auto text-[10px] gap-1">
                  <WifiOff className="h-3 w-3" /> reconnecting
                </Badge>
              )}
            </div>
            <StageProgress current={job?.status ?? "queued"} />
          </div>
        </div>
      </Card>

      {/* Left: agent roster */}
      <div className="col-span-12 lg:col-span-3">
        <AgentRoster events={events} currentStatus={job?.status ?? "queued"} />
      </div>

      {/* Right: tabbed workspace */}
      <div className="col-span-12 lg:col-span-9">
        <Tabs defaultValue="stream">
          <TabsList>
            <TabsTrigger value="stream">
              <Activity className="h-3.5 w-3.5" /> stream
              <Badge variant="outline" className="ml-1 text-[10px]">{events.length}</Badge>
            </TabsTrigger>
            <TabsTrigger value="code">
              <Code2 className="h-3.5 w-3.5" /> code
              <Badge variant="outline" className="ml-1 text-[10px]">{fileCount}</Badge>
            </TabsTrigger>
            <TabsTrigger value="debate">
              <MessageSquare className="h-3.5 w-3.5" /> debate
              <Badge variant="outline" className="ml-1 text-[10px]">{debateRounds}</Badge>
            </TabsTrigger>
            <TabsTrigger value="verification">
              <ShieldCheck className="h-3.5 w-3.5" /> verification
              {issueCount > 0 && (
                <Badge variant="warning" className="ml-1 text-[10px]">{issueCount}</Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="metrics">
              <BarChart3 className="h-3.5 w-3.5" /> metrics
            </TabsTrigger>
          </TabsList>
          <TabsContent value="stream" className="mt-3">
            <div className="h-[68vh]">
              <StreamTab events={events} />
            </div>
          </TabsContent>
          <TabsContent value="code"><CodeTab events={events} /></TabsContent>
          <TabsContent value="debate"><DebateTab events={events} /></TabsContent>
          <TabsContent value="verification"><VerificationTab events={events} /></TabsContent>
          <TabsContent value="metrics"><MetricsTab events={events} /></TabsContent>
        </Tabs>
      </div>
    </motion.div>
  );
}
