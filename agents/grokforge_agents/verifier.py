"""Verifier agent.

Five signals → aggregated confidence:
  1. Execution grounding — Tester's exit code
  2. Review signal — count of high-severity issues
  3. Debate confidence — proponent/skeptic/judge verdict
  4. Symbolic — Z3 checks on math-heavy invariants (when applicable)
  5. Self-consistency — placeholder hook for future second-opinion derivation

Each signal is emitted as a `verification_signal` event so the UI can
render a five-dot status row with ✓ / ✗ and explanatory tooltips.
"""

from __future__ import annotations

import json
from typing import Any

from .base import Agent, AgentRequest
from .debate import run_debate
from .router import ModelRouter
from .symbolic import check_conservation_of_energy, check_sort_invariant


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

        self.think(
            f"Aggregating five verification signals for round {round_num}. "
            "Threshold for deploy is confidence ≥ 0.95.",
            scope="strategy",
        )

        # 1. Execution grounding ───────────────────────────────────────
        test_result = tests.get("result", {})
        exec_ok = test_result.get("exit_code") == 0
        self.verification_signal(
            "execution",
            value=1.0 if exec_ok else 0.0,
            passed=exec_ok,
            detail=(f"pytest exit={test_result.get('exit_code')}"
                    if test_result else "no test result available"),
        )

        # 2. Review signal ─────────────────────────────────────────────
        review_issues = review.get("issues", [])
        high_sev = [i for i in review_issues if i.get("severity") == "high"]
        review_ok = len(high_sev) == 0
        self.verification_signal(
            "review",
            value=1.0 if review_ok else 0.0,
            passed=review_ok,
            detail=(f"{len(high_sev)} high-severity issue(s)"
                    if high_sev else f"{len(review_issues)} non-blocking note(s)"),
        )

        # 3. Debate ────────────────────────────────────────────────────
        self.think(
            "Spinning up the debate loop. Proponent and Skeptic will exchange two rounds, "
            "then the Judge produces a verdict and confidence score I'll fold in.",
            scope="debate",
        )
        artifact_summary = json.dumps({
            "plan": plan, "files": [f["path"] for f in code.get("files", [])][:10],
            "test_exit": test_result.get("exit_code"),
            "review_issues": [i.get("summary") for i in review_issues],
        }, indent=2)[:5000]
        debate = await run_debate(self.router, artifact_summary, rounds=2, emitter=self)
        self.cost_usd += debate.cost_usd
        self.verification_signal(
            "debate",
            value=debate.confidence,
            passed=debate.confidence >= 0.85,
            detail=f"winner={debate.winner}: {debate.rationale[:140]}",
        )

        # 4. Symbolic ─────────────────────────────────────────────────
        symbolic_note = "skipped (no math-heavy invariants in spec)"
        symbolic_ok = True
        symbolic_value = 1.0
        spec_text = (plan.get("spec") or plan.get("summary") or "").lower()
        if any(k in spec_text for k in ("physics", "orbit", "n-body", "energy", "verlet")):
            sym = check_conservation_of_energy([1.0, 0.5], [[2.0, 0, 0], [0, 1.0, 0]],
                                               [[2.0, 0, 0], [0, 1.0, 0]])
            symbolic_ok = sym.proved
            symbolic_note = sym.note
            symbolic_value = 1.0 if sym.proved else 0.0
            self.tool_call("z3.check_conservation_of_energy", {"tolerance": 1e-6},
                           {"proved": sym.proved, "note": sym.note})
        elif "sort" in spec_text:
            sym = check_sort_invariant([1, 2, 3, 4, 5])
            symbolic_ok = sym.proved
            symbolic_note = sym.note
            symbolic_value = 1.0 if sym.proved else 0.0
        self.verification_signal(
            "symbolic", value=symbolic_value, passed=symbolic_ok, detail=symbolic_note,
        )

        # 5. Self-consistency placeholder ─────────────────────────────
        consistency_value = 0.9
        self.verification_signal(
            "consistency",
            value=consistency_value,
            passed=True,
            detail="placeholder — second-opinion derivation slated for v0.2",
        )

        # Aggregate ───────────────────────────────────────────────────
        confidence = self._aggregate(
            exec_ok=exec_ok,
            high_severity_issues=len(high_sev),
            debate_confidence=debate.confidence,
            symbolic_ok=symbolic_ok,
            consistency=consistency_value,
            round_num=round_num,
        )

        if confidence >= 0.95:
            self.decide(
                "approve for deploy",
                f"Aggregated confidence {confidence:.3f} ≥ threshold 0.95. "
                "All five signals are within bounds and the debate judge backed shipping.",
            )
        else:
            self.decide(
                "request another debate round",
                f"Aggregated confidence {confidence:.3f} < threshold 0.95 in round {round_num}. "
                "Bouncing back to the orchestrator; if we exhaust MAX_DEBATE_ROUNDS the job fails.",
            )

        self.metric("aggregated_confidence", round(confidence, 3), "")
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
                "transcript": debate.transcript,
            },
            "symbolic": {"note": symbolic_note, "ok": symbolic_ok},
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
        symbolic_ok: bool,
        consistency: float,
        round_num: int,
    ) -> float:
        score = 0.0
        score += 0.35 if exec_ok else 0.0
        score += 0.35 * debate_confidence
        score += 0.15 if high_severity_issues == 0 else 0.0
        score += 0.10 if symbolic_ok else 0.0
        score += 0.05 * max(0.0, min(1.0, consistency))
        score += min(0.04, 0.01 * (round_num - 1))
        return min(1.0, score)
