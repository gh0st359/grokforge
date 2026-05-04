"""Shared types and the abstract Agent base class.

Each agent emits a stream of *typed events* during a run. Events are richer
than free-form log lines — they carry structure (thinking, decision,
file_written, debate_turn, verification_signal) so the frontend can render
them as first-class UI rather than a wall of text.
"""

from __future__ import annotations

import abc
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    job_id: UUID
    stage: str
    input: dict[str, Any] = Field(default_factory=dict)


class AgentEvent(BaseModel):
    """One typed event emitted by an agent during a stage run."""
    kind: str  # thinking | decision | tool_call | code_chunk | file_written
               # | debate_turn | verification_signal | metric | log
    agent: str
    ts: str  # ISO8601 UTC
    payload: dict[str, Any]


class AgentResponse(BaseModel):
    stage: str
    output: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    cost_usd: float = 0.0
    logs: list[str] = Field(default_factory=list)
    events: list[AgentEvent] = Field(default_factory=list)


class Agent(abc.ABC):
    """Base class for all grokforge agents.

    Subclasses implement `run()`. They report progress with the typed
    helpers below; each helper appends an `AgentEvent` to `self.events`
    that will be forwarded to the SSE stream by the orchestrator.
    """

    name: str = "agent"

    def __init__(self) -> None:
        self.logs: list[str] = []
        self.events: list[AgentEvent] = []
        self.cost_usd: float = 0.0

    # ─── event helpers ───────────────────────────────────────────────

    def _emit(self, kind: str, payload: dict[str, Any], *, agent: str | None = None) -> None:
        self.events.append(AgentEvent(
            kind=kind,
            agent=agent or self.name,
            ts=datetime.now(timezone.utc).isoformat(),
            payload=payload,
        ))

    def log(self, line: str) -> None:
        """Plain text log line — kept for backward compatibility."""
        self.logs.append(line)
        self._emit("log", {"line": line})

    def think(self, content: str, *, scope: str | None = None) -> None:
        """First-person reasoning the agent wants the user to see.

        Renders as a 'thinking bubble' in the UI. Use plenty of these —
        the user wants to understand why, not just what.
        """
        self._emit("thinking", {"content": content, "scope": scope})

    def decide(self, decision: str, rationale: str, *, alternatives: list[str] | None = None) -> None:
        """A concrete choice with reasoning, optionally listing what was rejected."""
        self._emit("decision", {
            "decision": decision,
            "rationale": rationale,
            "alternatives": alternatives or [],
        })

    def tool_call(self, name: str, args: dict[str, Any], result: dict[str, Any] | None = None) -> None:
        """Invocation of an external tool (LLM, sandbox exec, web fetch, etc.)."""
        self._emit("tool_call", {"name": name, "args": args, "result": result})

    def code_chunk(self, path: str, content: str, language: str = "python", *, complete: bool = False) -> None:
        """A chunk of generated code being streamed in.

        Set `complete=True` on the final chunk for that file.
        """
        self._emit("code_chunk", {
            "path": path, "content": content, "language": language, "complete": complete,
        })

    def file_written(self, path: str, content: str, language: str = "python") -> None:
        """A complete file was just produced. Triggers FileTree update + viewer refresh."""
        self._emit("file_written", {
            "path": path,
            "content": content,
            "language": language,
            "lines": content.count("\n") + 1,
            "bytes": len(content),
        })

    def debate_turn(self, role: str, round_num: int, content: str, *,
                    target: str | None = None) -> None:
        """One turn in the debate transcript.

        role ∈ {"proponent", "skeptic", "judge"}.
        target identifies what's being debated (e.g. "code:app/main.py").
        """
        self._emit("debate_turn", {
            "role": role, "round": round_num, "content": content, "target": target,
        })

    def verification_signal(self, name: str, value: float, *, passed: bool, detail: str = "") -> None:
        """One signal feeding the aggregated confidence score.

        name ∈ {"execution", "review", "debate", "symbolic", "consistency"}.
        value ∈ [0, 1].
        """
        self._emit("verification_signal", {
            "name": name, "value": value, "passed": passed, "detail": detail,
        })

    def metric(self, name: str, value: float, unit: str = "") -> None:
        self._emit("metric", {"name": name, "value": value, "unit": unit})

    # ─── lifecycle ────────────────────────────────────────────────────

    @abc.abstractmethod
    async def run(self, req: AgentRequest) -> dict[str, Any]:
        """Return this agent's structured output. Confidence is reported separately."""

    async def confidence(self, output: dict[str, Any]) -> float:
        return 0.5

    async def execute(self, req: AgentRequest) -> AgentResponse:
        self.logs = []
        self.events = []
        self.cost_usd = 0.0

        started = time.monotonic()
        self.think(f"starting {self.name} stage", scope="lifecycle")
        try:
            output = await self.run(req)
        except Exception as e:
            self._emit("error", {"message": str(e), "type": type(e).__name__})
            raise
        elapsed = time.monotonic() - started

        confidence = await self.confidence(output)
        self.metric("stage_seconds", round(elapsed, 3), "s")
        self.metric("stage_confidence", round(confidence, 3), "")

        return AgentResponse(
            stage=self.name,
            output=output,
            confidence=confidence,
            cost_usd=self.cost_usd,
            logs=list(self.logs),
            events=list(self.events),
        )
