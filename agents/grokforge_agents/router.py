"""Dynamic model router.

Picks the cheapest model that's plausibly capable of a given turn. The
heuristic is intentionally simple: high-stakes turns (planning, verification)
go to the primary model; low-stakes turns (formatting, summarization,
short reviews) go to the fallback.

Falls back to a deterministic mock generator when no API key is configured —
this lets the entire stack run in CI and on offline laptops.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .grok_client import GrokClient, GrokError


@dataclass
class RouterDecision:
    model: str
    reason: str


class ModelRouter:
    PRIMARY = os.getenv("GROK_PRIMARY_MODEL", "grok-4-3")
    FALLBACK = os.getenv("GROK_FALLBACK_MODEL", "grok-4-mini")

    HIGH_STAKES = {"planner", "verifier", "reviewer"}
    LOW_STAKES = {"deployer"}

    def __init__(self, client: GrokClient) -> None:
        self.client = client

    def pick(self, stage: str, *, retry: int = 0) -> RouterDecision:
        if stage in self.HIGH_STAKES:
            return RouterDecision(self.PRIMARY, "high-stakes stage")
        if stage in self.LOW_STAKES:
            return RouterDecision(self.FALLBACK, "low-stakes stage")
        # Coder + Tester start on fallback, escalate on retry
        if retry == 0:
            return RouterDecision(self.FALLBACK, "default low-cost first attempt")
        return RouterDecision(self.PRIMARY, "escalating after retry")

    async def chat(
        self,
        stage: str,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        json_mode: bool = False,
        retry: int = 0,
    ) -> tuple[str, float, str]:
        """Returns (text, cost_usd, model_used)."""
        if not self.client.configured:
            return _mock_response(stage, messages), 0.0, "mock"
        decision = self.pick(stage, retry=retry)
        try:
            text, cost = await self.client.chat(
                decision.model, messages,
                temperature=temperature, max_tokens=max_tokens, json_mode=json_mode,
            )
            return text, cost, decision.model
        except GrokError:
            if retry == 0:
                return await self.chat(
                    stage, messages,
                    temperature=temperature, max_tokens=max_tokens,
                    json_mode=json_mode, retry=1,
                )
            raise


def _mock_response(stage: str, messages: list[dict[str, str]]) -> str:
    """Deterministic offline responses so the pipeline still produces artifacts."""
    spec = ""
    for m in messages:
        if m.get("role") == "user":
            spec = m.get("content", "")
            break
    spec_short = spec[:120].replace("\n", " ")

    if stage == "planner":
        return (
            '{"milestones": ['
            '{"id": "m1", "title": "Project scaffold", "acceptance": "FastAPI app boots, /health returns 200"},'
            '{"id": "m2", "title": "Core endpoint", "acceptance": "POST /compute returns expected JSON shape"},'
            '{"id": "m3", "title": "Tests", "acceptance": "pytest -q exits 0 with >=3 tests"}'
            '], "stack": "python+fastapi", "summary": "' + spec_short + '"}'
        )
    if stage == "coder":
        return '{"template": "python_fastapi", "notes": "deterministic scaffold"}'
    if stage == "tester":
        return '{"command": "pytest -q", "expected_pass": 3}'
    if stage == "reviewer":
        return '{"issues": [], "approved": true, "confidence": 0.92}'
    if stage == "verifier":
        return '{"verdict": "consistent", "confidence": 0.96, "symbolic": "n/a"}'
    if stage == "deployer":
        return '{"image": "grokforge/output:latest", "k8s": "manifests written"}'
    return "{}"
