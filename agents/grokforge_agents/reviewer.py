"""Reviewer agent.

Performs static security scan + LLM critique. Each finding becomes its
own typed event so the UI can render them as a triaged list with
severity badges.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .base import Agent, AgentRequest
from .router import ModelRouter

SYSTEM_PROMPT = """You are the Reviewer agent in grokforge.
Read the plan, generated code, and test results. Return strict JSON:
{
  "issues": [{"severity": "high|med|low", "path": "...", "summary": "...", "fix": "..."}],
  "approved": bool,
  "confidence": 0.0..1.0,
  "rationale": "one paragraph"
}
Be concrete. No nitpicks below 'med' unless they're security or correctness.
"""

DANGEROUS_PATTERNS = [
    (r"\beval\s*\(", "high", "use of eval()"),
    (r"\bexec\s*\(", "high", "use of exec()"),
    (r"shell\s*=\s*True", "high", "subprocess shell=True"),
    (r"pickle\.loads?\(", "high", "pickle.loads on untrusted input is RCE"),
    (r"verify\s*=\s*False", "med", "TLS verification disabled"),
    (r"DEBUG\s*=\s*True", "low", "DEBUG=True in production code"),
    (r"sql\s*=.*\+.*request", "high", "string-concatenated SQL likely vulnerable to injection"),
    (r"hardcoded.{0,20}(secret|password|token|key)", "high", "possible hard-coded credential"),
]


class ReviewerAgent(Agent):
    name = "reviewer"

    def __init__(self, router: ModelRouter) -> None:
        super().__init__()
        self.router = router

    async def run(self, req: AgentRequest) -> dict[str, Any]:
        bundle = req.input or {}
        code = bundle.get("code", {})
        files = code.get("files", []) if isinstance(code, dict) else []

        self.think(
            f"Reviewing {len(files)} file(s). I'll run a regex-based dangerous-pattern scan first "
            "(deterministic, fast), then ask the primary model for a structured critique. "
            "I block deploy on any high-severity issue regardless of LLM verdict.",
            scope="strategy",
        )

        static_issues = self._static_scan(files)
        for iss in static_issues:
            self._emit("issue", iss)
            self.think(f"static scan flagged {iss['severity']} in {iss['path']}: {iss['summary']}",
                       scope="static")
        self.metric("static_issues", len(static_issues), "")

        if self.router.client.configured:
            self.tool_call("grok.chat", {"stage": "reviewer", "json_mode": True})
            try:
                text, cost, model = await self.router.chat(
                    "reviewer",
                    [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": json.dumps({
                            "plan": bundle.get("plan", {}),
                            "test_result": (bundle.get("tests") or {}).get("result", {}),
                            "files": [{"path": f["path"], "content": f["content"][:4000]}
                                      for f in files][:8],
                        })},
                    ],
                    temperature=0.2, max_tokens=2000, json_mode=True,
                )
                self.cost_usd += cost
                self.metric("tokens_cost_usd", round(cost, 4), "$")
                self.tool_call("grok.chat.return", {"model": model, "cost_usd": cost})
                llm = _safe_json(text)
            except Exception as e:
                self.think(f"LLM review skipped: {e}", scope="fallback")
                llm = self._heuristic_review(files, bundle)
        else:
            llm = self._heuristic_review(files, bundle)

        for iss in llm.get("issues", []):
            self._emit("issue", {**iss, "source": "llm"})

        all_issues = static_issues + list(llm.get("issues", []))
        approved = bool(llm.get("approved", True)) and not any(
            i.get("severity") == "high" for i in all_issues
        )
        confidence = float(llm.get("confidence", 0.6))
        if any(i.get("severity") == "high" for i in static_issues):
            confidence = min(confidence, 0.4)
            self.decide(
                "block deploy on high-severity static finding",
                "Static signal trumps LLM approval — Reviewer's job is to be the paranoid one.",
            )
        elif approved:
            self.decide("approve for verification", llm.get("rationale", "no high-severity issues"))
        else:
            self.decide("flag for revision", llm.get("rationale", "issues require fixing"))

        self.metric("review_confidence", round(confidence, 3), "")
        return {
            "issues": all_issues,
            "approved": approved,
            "rationale": llm.get("rationale", ""),
            "review_confidence": confidence,
        }

    async def confidence(self, output: dict[str, Any]) -> float:
        if not output.get("approved"):
            return 0.4
        return float(output.get("review_confidence", 0.7))

    def _static_scan(self, files: list[dict[str, str]]) -> list[dict[str, Any]]:
        issues = []
        for f in files:
            content = f.get("content", "")
            for pattern, severity, summary in DANGEROUS_PATTERNS:
                if re.search(pattern, content):
                    issues.append({
                        "severity": severity,
                        "path": f["path"],
                        "summary": summary,
                        "fix": "review and remove or replace with a safe alternative",
                        "source": "static",
                    })
        return issues

    def _heuristic_review(self, files: list[dict[str, str]], bundle: dict[str, Any]) -> dict[str, Any]:
        tests = (bundle.get("tests") or {}).get("result", {})
        ok = tests.get("exit_code") == 0
        return {
            "issues": [],
            "approved": ok,
            "confidence": 0.85 if ok else 0.55,
            "rationale": (
                "tests passed and no high-severity static issues" if ok
                else "tests did not pass cleanly — revisit before deploy"
            ),
        }


def _safe_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"issues": [], "approved": True, "confidence": 0.5}
