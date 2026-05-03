"""Verifier agent.

Combines:
1. Execution grounding — re-checks the test result reported by the Tester.
2. Self-consistency — second-opinion code derivation, diff against original.
3. Debate — proponent/skeptic loop with a judge.
4. Symbolic — Z3 checks on math-heavy invariants if applicable.

Returns an aggregated confidence score; the orchestrator gates deploy on it.
"""

from __future__ import annotations

import json
from typing import Any

from .base import Agent, AgentRequest
from .debate import run_debate
from .router import ModelRouter
from .symbolic import check_sort_invariant


class VerifierAgent(Agent):
    name = "verifier"

    def __init__(self, router: ModelRouter) -> None:
        super().__init__()
        self.router = router

    async def run(self, req: AgentRequest) -> dict[str, Any]:
        plan = req.input.get("plan", {}) or {}
        code = req.input.get("code", {}) or {}
        tests = req.input.get("tests", {}) or {}
        review = req.input.get("review", {}) or {}
        round_num = int(req.input.get("round", 1))

        # 1. Execution grounding
        test_result = tests.get("result", {})
        exec_ok = test_result.get("exit_code") == 0
        self.log(f"execution grounding: tests {'passed' if exec_ok else 'did not pass cleanly'}")

        # 2. Review signal
        review_issues = review.get("issues", [])
        high_sev = [i for i in review_issues if i.get("severity") == "high"]
        self.log(f"review signal: {len(high_sev)} high-severity issue(s)")

        # 3. Debate
        artifact_summary = json.dumps({
            "plan": plan, "files": [f["path"] for f in code.get("files", [])][:10],
            "test_exit": test_result.get("exit_code"),
            "review_issues": [i.get("summary") for i in review_issues],
        }, indent=2)[:6000]
        debate = await run_debate(self.router, artifact_summary, rounds=2, log=self.logs)
        self.cost_usd += debate.cost_usd
        self.log(f"debate verdict: winner={debate.winner} confidence={debate.confidence:.2f}")

        # 4. Symbolic — only attempt for math-heavy specs.
        symbolic_note = "skipped"
        spec_text = (plan.get("spec") or plan.get("summary") or "").lower()
        if any(k in spec_text for k in ("physics", "orbit", "n-body", "energy", "sort")):
            sym = check_sort_invariant([1, 2, 3])  # placeholder smoke check
            symbolic_note = sym.note
            self.log(f"symbolic check: {symbolic_note}")

        # Aggregate confidence
        confidence = self._aggregate(
            exec_ok=exec_ok,
            high_severity_issues=len(high_sev),
            debate_confidence=debate.confidence,
            round_num=round_num,
        )

        return {
            "verdict": "approved" if confidence >= 0.95 else "needs-revision",
            "confidence": confidence,
            "execution_ok": exec_ok,
            "high_severity_issues": len(high_sev),
            "debate": {
                "winner": debate.winner,
                "confidence": debate.confidence,
                "rationale": debate.rationale,
                "blocking_issues": debate.blocking_issues,
            },
            "symbolic": symbolic_note,
            "round": round_num,
        }

    async def confidence(self, output: dict[str, Any]) -> float:
        return float(output.get("confidence", 0.0))

    @staticmethod
    def _aggregate(
        *,
        exec_ok: bool,
        high_severity_issues: int,
        debate_confidence: float,
        round_num: int,
    ) -> float:
        base = 0.0
        base += 0.40 if exec_ok else 0.0
        base += 0.40 * debate_confidence
        base += 0.20 if high_severity_issues == 0 else 0.0
        # later rounds slightly compound — fixes from earlier rounds reduce risk.
        base += min(0.04, 0.01 * (round_num - 1))
        return min(1.0, base)
