"""Planner agent.

Reads the user spec, narrates its decision-making, and emits a structured
plan: milestones with objective acceptance criteria, target stack, and a
one-line summary.

The Planner is verbose by design — the user sees it pick a stack, weigh
trade-offs, and decompose the spec into milestones with concrete success
checks before the Coder writes a single line.
"""

from __future__ import annotations

import json
from typing import Any

from .base import Agent, AgentRequest
from .router import ModelRouter

SYSTEM_PROMPT = """You are the Planner agent in grokforge.
Translate the user's natural-language spec into a strict JSON plan with:
- milestones: array of {id, title, acceptance, rationale}
- stack: one of "python+fastapi", "rust+axum", "typescript+next"
- summary: one-line restatement of the user's goal
- assumptions: array of inferred assumptions you made
- risks: array of {risk, mitigation}

Return only valid JSON. Acceptance criteria must be objectively verifiable
by an automated tester (e.g. "GET /health returns 200 with body 'ok'").
Each milestone must include a 'rationale' explaining why it exists.
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

        self.think(
            f"Reading the spec: \"{spec[:200]}{'…' if len(spec) > 200 else ''}\"",
            scope="ingest",
        )
        self.think(
            "I need to (1) pick a stack, (2) decompose this into milestones with "
            "objective acceptance criteria, and (3) flag assumptions and risks "
            "so downstream agents don't silently invent requirements.",
            scope="approach",
        )

        stack = self._infer_stack(spec)
        self.decide(
            f"target stack = {stack}",
            self._stack_rationale(stack, spec),
            alternatives=[s for s in ("python+fastapi", "rust+axum", "typescript+next") if s != stack],
        )

        self.tool_call("grok.chat", {
            "stage": "planner",
            "messages": 2,
            "json_mode": True,
        })
        try:
            text, cost, model = await self.router.chat(
                "planner",
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Stack hint: {stack}\n\nSpec:\n{spec}"},
                ],
                temperature=0.1,
                max_tokens=1500,
                json_mode=True,
            )
            self.cost_usd += cost
            self.metric("tokens_cost_usd", round(cost, 4), "$")
            self.tool_call("grok.chat.return", {"model": model, "cost_usd": cost})
        except Exception as e:
            self.think(f"LLM call failed ({e}); proceeding with deterministic plan", scope="fallback")
            text = ""

        plan = _safe_json(text) or {}
        plan.setdefault("stack", stack)
        plan.setdefault("summary", spec[:200])
        plan.setdefault("milestones", self._fallback_milestones(spec))
        plan.setdefault("assumptions", self._infer_assumptions(spec))
        plan.setdefault("risks", self._infer_risks(spec))
        plan["spec"] = spec

        # Surface every milestone as its own decision event so the timeline reads narratively.
        for i, m in enumerate(plan["milestones"], 1):
            self.decide(
                f"milestone {i}: {m.get('title', '?')}",
                m.get("rationale") or m.get("acceptance", ""),
            )

        for a in plan["assumptions"]:
            self.think(f"assumption: {a}", scope="assumption")
        for r in plan["risks"]:
            self.think(f"risk: {r.get('risk')} — mitigation: {r.get('mitigation')}", scope="risk")

        self.metric("milestones", len(plan["milestones"]), "")
        return plan

    async def confidence(self, output: dict[str, Any]) -> float:
        ms = output.get("milestones") or []
        if not ms:
            return 0.3
        if all("acceptance" in m and "title" in m for m in ms):
            return 0.85
        return 0.55

    # ─── heuristics used in mock mode and as scaffolding for the LLM ──

    def _infer_stack(self, spec: str) -> str:
        s = spec.lower()
        if any(k in s for k in ("real-time ui", "react", "next.js", "dashboard", "frontend")):
            return "typescript+next"
        if any(k in s for k in ("ultra-low latency", "embedded", "kernel", "wasm runtime")):
            return "rust+axum"
        return "python+fastapi"

    def _stack_rationale(self, stack: str, spec: str) -> str:
        base = {
            "python+fastapi": "FastAPI gives the fastest path from spec to a typed, async, "
                              "OpenAPI-documented HTTP service. The ecosystem covers physics, "
                              "ML, and data tooling — well-suited to the demo track.",
            "rust+axum": "Rust + Axum is the right call when the spec demands deterministic "
                         "latency, zero-GC, or sandboxed execution paths.",
            "typescript+next": "Next.js is the right pick when the spec foregrounds an interactive "
                               "UI rather than a headless service.",
        }[stack]
        return base + f" Spec keywords also align: \"{spec[:80].replace(chr(10), ' ')}…\""

    def _infer_assumptions(self, spec: str) -> list[str]:
        out = ["Single-tenant local deployment unless the spec says otherwise.",
               "No persistent database is required unless the spec names one."]
        s = spec.lower()
        if "real-time" in s:
            out.append("'Real-time' means soft real-time (≤100 ms median) — not hard real-time guarantees.")
        if any(k in s for k in ("physics", "orbit", "n-body")):
            out.append("Numeric correctness is verified against conservation laws via symbolic checks.")
        return out

    def _infer_risks(self, spec: str) -> list[dict[str, str]]:
        risks = [
            {"risk": "LLM hallucinates package names",
             "mitigation": "Reviewer's static scan + Tester's actual install + Verifier debate"},
            {"risk": "Acceptance criteria drift from user intent",
             "mitigation": "Each milestone's 'acceptance' is a single objective check"},
        ]
        s = spec.lower()
        if any(k in s for k in ("auth", "secret", "credential", "password")):
            risks.append({"risk": "Auth/secret handling is easy to get subtly wrong",
                          "mitigation": "Reviewer dangerous-pattern scan + symbolic invariants"})
        return risks

    def _fallback_milestones(self, spec: str) -> list[dict[str, Any]]:
        s = spec.lower()
        if any(k in s for k in ("orbit", "n-body", "physics", "gravity")):
            return [
                {"id": "m1", "title": "Project scaffold + /health",
                 "acceptance": "GET /health returns {'status': 'ok'} with status 200",
                 "rationale": "Establishes the service boots and is observable before adding physics."},
                {"id": "m2", "title": "World model + integrator",
                 "acceptance": "POST /world creates a body list; POST /step advances state by dt",
                 "rationale": "Core simulation loop must work before tests can verify conservation laws."},
                {"id": "m3", "title": "Conservation tests",
                 "acceptance": "pytest verifies total energy conserved within 1e-6 over 1000 steps",
                 "rationale": "Symbolic-grade correctness check; the Verifier's symbolic engine reads this."},
            ]
        return [
            {"id": "m1", "title": "Project scaffold",
             "acceptance": "FastAPI app boots; /health returns 200 with JSON body.",
             "rationale": "Smallest verifiable unit; gates everything else."},
            {"id": "m2", "title": "Core endpoint",
             "acceptance": "POST /compute returns expected JSON shape for sample input.",
             "rationale": "Implements the user-visible behaviour described in the spec."},
            {"id": "m3", "title": "Tests",
             "acceptance": "pytest -q exits 0 with at least 3 distinct test cases.",
             "rationale": "Gives the Tester something to run; gates Verifier confidence."},
        ]


def _safe_json(text: str) -> dict[str, Any]:
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {}
