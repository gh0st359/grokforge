"""Shared types and the abstract Agent base class."""

from __future__ import annotations

import abc
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    job_id: UUID
    stage: str
    input: dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    stage: str
    output: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    cost_usd: float = 0.0
    logs: list[str] = Field(default_factory=list)


class Agent(abc.ABC):
    """Base class for all grokforge agents.

    Subclasses implement `run()` and may push human-readable strings into
    `self.logs`; the orchestrator forwards them onto the SSE stream.
    """

    name: str = "agent"

    def __init__(self) -> None:
        self.logs: list[str] = []
        self.cost_usd: float = 0.0

    def log(self, line: str) -> None:
        self.logs.append(line)

    @abc.abstractmethod
    async def run(self, req: AgentRequest) -> dict[str, Any]:
        """Return this agent's output dict. Confidence is reported separately."""

    async def confidence(self, output: dict[str, Any]) -> float:
        """Default heuristic confidence — subclasses override with real signals."""
        return 0.5

    async def execute(self, req: AgentRequest) -> AgentResponse:
        self.logs = []
        self.cost_usd = 0.0
        output = await self.run(req)
        return AgentResponse(
            stage=self.name,
            output=output,
            confidence=await self.confidence(output),
            cost_usd=self.cost_usd,
            logs=list(self.logs),
        )
