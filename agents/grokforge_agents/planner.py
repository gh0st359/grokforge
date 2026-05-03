"""Planner agent.

Reads the user spec from `input` (forwarded by the orchestrator from the
job record) and emits a structured plan: milestones, acceptance criteria,
target stack, and a one-line summary.
"""

from __future__ import annotations

import json
from typing import Any

from .base import Agent, AgentRequest
from .router import ModelRouter

SYSTEM_PROMPT = """You are the Planner agent in grokforge.
Translate the user's natural-language spec into a strict JSON plan with:
- milestones: array of {id, title, acceptance}
- stack: one of "python+fastapi", "rust+axum", "typescript+next"
- summary: one-line restatement of the user's goal

Return only valid JSON. No prose. Acceptance criteria must be objectively
verifiable by an automated tester (e.g. "GET /health returns 200 with body 'ok'").
"""


class PlannerAgent(Agent):
    name = "planner"

    def __init__(self, router: ModelRouter) -> None:
        super().__init__()
        self.router = router

    async def run(self, req: AgentRequest) -> dict[str, Any]:
        spec = (
            req.input.get("spec")
            or req.input.get("user_spec")
            or req.input.get("description")
            or "Build a small FastAPI service with one POST endpoint."
        )
        self.log(f"planning for spec: {spec[:120]}")
        text, cost, model = await self.router.chat(
            "planner",
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": spec},
            ],
            temperature=0.1,
            max_tokens=1500,
            json_mode=True,
        )
        self.cost_usd += cost
        self.log(f"used model={model} cost=${cost:.4f}")
        plan = _safe_json(text)
        plan.setdefault("stack", "python+fastapi")
        plan.setdefault("summary", spec[:200])
        plan["spec"] = spec
        return plan

    async def confidence(self, output: dict[str, Any]) -> float:
        ms = output.get("milestones") or []
        if not ms:
            return 0.3
        if all("acceptance" in m and "title" in m for m in ms):
            return 0.85
        return 0.55


def _safe_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Pull the first {...} block.
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {"raw": text, "milestones": []}
