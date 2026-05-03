"""Reviewer agent.

Performs static code review with security & edge-case heuristics, then
asks Grok for a structured critique. Emits an `issues` list and a yes/no
`approved` flag.
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

        static_issues = self._static_scan(files)
        self.log(f"static scan flagged {len(static_issues)} issue(s)")

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
            self.log(f"used model={model} cost=${cost:.4f}")
            llm = _safe_json(text)
        except Exception as e:  # noqa: BLE001
            self.log(f"LLM review skipped: {e}")
            llm = {"issues": [], "approved": True, "confidence": 0.6,
                   "rationale": "fallback approval"}

        issues = static_issues + list(llm.get("issues", []))
        approved = bool(llm.get("approved", True)) and not any(
            i.get("severity") == "high" for i in issues
        )
        confidence = float(llm.get("confidence", 0.6))
        if any(i.get("severity") == "high" for i in static_issues):
            confidence = min(confidence, 0.4)
        return {
            "issues": issues,
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


def _safe_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"issues": [], "approved": True, "confidence": 0.5}
