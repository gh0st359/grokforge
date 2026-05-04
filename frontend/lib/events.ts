// Event type definitions matching the Python AgentEvent payload schema.

export type AgentName =
  | "planner" | "coder" | "tester" | "reviewer" | "verifier" | "deployer"
  | "orchestrator";

export const AGENTS: AgentName[] = [
  "planner", "coder", "tester", "reviewer", "verifier", "deployer",
];

export const STAGES = [
  "queued", "planning", "coding", "testing", "reviewing", "verifying",
  "deploying", "succeeded",
] as const;
export type Stage = (typeof STAGES)[number];

export interface BaseEvent {
  ts: string;
  agent: AgentName;
  kind: string;
  payload: any;
}

export interface ThinkingEvent extends BaseEvent {
  kind: "thinking";
  payload: { content: string; scope?: string };
}
export interface DecisionEvent extends BaseEvent {
  kind: "decision";
  payload: { decision: string; rationale: string; alternatives?: string[] };
}
export interface CodeChunkEvent extends BaseEvent {
  kind: "code_chunk";
  payload: { path: string; content: string; language: string; complete?: boolean };
}
export interface FileWrittenEvent extends BaseEvent {
  kind: "file_written";
  payload: { path: string; content: string; language: string; lines: number; bytes: number };
}
export interface DebateTurnEvent extends BaseEvent {
  kind: "debate_turn";
  payload: { role: "proponent" | "skeptic" | "judge"; round: number; content: string; target?: string };
}
export interface VerificationSignalEvent extends BaseEvent {
  kind: "verification_signal";
  payload: { name: string; value: number; passed: boolean; detail: string };
}
export interface ToolCallEvent extends BaseEvent {
  kind: "tool_call";
  payload: { name: string; args: any; result?: any };
}
export interface MetricEvent extends BaseEvent {
  kind: "metric";
  payload: { name: string; value: number; unit?: string };
}
export interface CostEvent extends BaseEvent {
  kind: "cost";
  payload: { delta_usd: number };
}
export interface StatusEvent extends BaseEvent {
  kind: "status";
  payload: any;
}
export interface LogEvent extends BaseEvent {
  kind: "log";
  payload: { line: string };
}
export interface IssueEvent extends BaseEvent {
  kind: "issue";
  payload: { severity: "high" | "med" | "low"; path: string; summary: string; fix?: string };
}

export type AnyEvent =
  | ThinkingEvent | DecisionEvent | CodeChunkEvent | FileWrittenEvent
  | DebateTurnEvent | VerificationSignalEvent | ToolCallEvent | MetricEvent
  | CostEvent | StatusEvent | LogEvent | IssueEvent | BaseEvent;

export const KIND_LABEL: Record<string, string> = {
  thinking: "thinks",
  decision: "decides",
  tool_call: "tool",
  code_chunk: "code",
  file_written: "wrote",
  debate_turn: "debate",
  verification_signal: "signal",
  metric: "metric",
  cost: "cost",
  status: "status",
  log: "log",
  issue: "issue",
  error: "error",
  artifact: "artifact",
};

export const ALL_EVENT_KINDS = [
  "thinking", "decision", "tool_call", "code_chunk", "file_written",
  "debate_turn", "verification_signal", "metric", "cost", "status",
  "log", "issue", "error", "artifact",
];
