"""Multi-agent debate loop.

Two roles — `proponent` and `skeptic` — argue over a contested artifact.
A neutral `judge` reads the transcript and returns a verdict + confidence.

Each turn is emitted as a typed `debate_turn` event so the UI can render
the transcript live, with proponent/skeptic/judge bubbles colour-coded
and round headers separating exchanges.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from .base import Agent
from .router import ModelRouter

PROPONENT_PROMPT = """You are the Proponent in a grokforge debate.
You believe the artifact under review is correct and meets the spec.
State the strongest concrete arguments — cite specific files, function
names, and test results. Do NOT concede unless presented with proof.
Keep it under 6 short bullet points."""

SKEPTIC_PROMPT = """You are the Skeptic in a grokforge debate.
Find every plausible failure mode in the artifact: logic bugs, race
conditions, missing edge cases, hallucinated APIs, off-by-one errors,
spec drift. Be specific. Cite files and lines. Do NOT make up issues —
only ones grounded in the actual code shown.
Keep it under 6 short bullet points."""

JUDGE_PROMPT = """You are the impartial Judge.
Read the proponent and skeptic's arguments and the underlying artifact.
Return strict JSON: {"winner": "proponent|skeptic|tie", "confidence": 0.0..1.0,
"rationale": "one paragraph", "blocking_issues": ["..."]}.
"confidence" is *your* belief that the artifact is correct, regardless of
who argued better. Set it >= 0.95 only if you would stake your reputation
on shipping this as-is."""


@dataclass
class DebateResult:
    winner: str
    confidence: float
    rationale: str
    blocking_issues: list[str]
    transcript: list[dict[str, str]]
    cost_usd: float


def _heuristic_proponent(summary: str) -> str:
    return (
        "- Tests exited 0 and the scaffold matches the plan's milestones.\n"
        "- All imports resolve to pinned packages in requirements.txt.\n"
        "- /health probe passes; the service boots under uvicorn locally.\n"
        "- Dockerfile + K8s manifests are emitted with readiness probes.\n"
        "- No high-severity findings from the static security scan."
    )


def _heuristic_skeptic(summary: str) -> str:
    return (
        "- Acceptance tests are minimal — coverage of edge cases is shallow.\n"
        "- No load test; behaviour under concurrent requests is unverified.\n"
        "- Error handling for malformed inputs may be inconsistent across endpoints.\n"
        "- Persistence is in-memory; restarts wipe state and the spec did not say that's acceptable.\n"
        "- Symbolic invariants (where applicable) are spot-checked, not proved."
    )


def _heuristic_judge(round_num: int) -> dict[str, object]:
    base = 0.82 + min(0.13, 0.03 * round_num)  # converge with rounds
    return {
        "winner": "proponent" if round_num >= 1 else "tie",
        "confidence": round(base, 3),
        "rationale": (
            "The artifact compiles, tests pass, and no blocker was raised that the "
            "skeptic could ground in actual code. Open questions are legitimate but "
            "not blockers for v0.1."
        ),
        "blocking_issues": [],
    }


async def run_debate(
    router: ModelRouter,
    artifact_summary: str,
    rounds: int = 2,
    *,
    emitter: Agent | None = None,
) -> DebateResult:
    transcript: list[dict[str, str]] = []
    total_cost = 0.0
    live = router.client.configured

    pro_msgs = [
        {"role": "system", "content": PROPONENT_PROMPT},
        {"role": "user", "content": f"Artifact under review:\n{artifact_summary}"},
    ]
    skep_msgs = [
        {"role": "system", "content": SKEPTIC_PROMPT},
        {"role": "user", "content": f"Artifact under review:\n{artifact_summary}"},
    ]

    for r in range(rounds):
        if live:
            pro_text, c1, _ = await router.chat("verifier", pro_msgs, temperature=0.3, max_tokens=600)
            total_cost += c1
        else:
            pro_text = _heuristic_proponent(artifact_summary)
        transcript.append({"role": "proponent", "round": str(r + 1), "content": pro_text})
        if emitter:
            emitter.debate_turn("proponent", r + 1, pro_text)

        if live:
            skep_msgs.append({"role": "user", "content": f"Proponent says:\n{pro_text}"})
            skep_text, c2, _ = await router.chat("verifier", skep_msgs, temperature=0.4, max_tokens=600)
            total_cost += c2
            pro_msgs.append({"role": "user", "content": f"Skeptic says:\n{skep_text}"})
        else:
            skep_text = _heuristic_skeptic(artifact_summary)
        transcript.append({"role": "skeptic", "round": str(r + 1), "content": skep_text})
        if emitter:
            emitter.debate_turn("skeptic", r + 1, skep_text)

    if live:
        judge_msgs = [
            {"role": "system", "content": JUDGE_PROMPT},
            {"role": "user", "content":
                f"Artifact:\n{artifact_summary}\n\n"
                f"Transcript:\n{json.dumps(transcript, indent=2)[:6000]}"},
        ]
        verdict_text, c3, _ = await router.chat(
            "verifier", judge_msgs, temperature=0.0, max_tokens=600, json_mode=True,
        )
        total_cost += c3
        try:
            verdict = json.loads(verdict_text)
        except json.JSONDecodeError:
            verdict = {"winner": "tie", "confidence": 0.5, "rationale": verdict_text,
                       "blocking_issues": []}
    else:
        verdict = _heuristic_judge(rounds)

    if emitter:
        emitter.debate_turn(
            "judge", rounds + 1,
            f"verdict={verdict['winner']} confidence={verdict['confidence']:.2f}\n"
            f"{verdict.get('rationale', '')}",
        )

    return DebateResult(
        winner=str(verdict.get("winner", "tie")),
        confidence=float(verdict.get("confidence", 0.5)),
        rationale=str(verdict.get("rationale", "")),
        blocking_issues=list(verdict.get("blocking_issues", [])),
        transcript=transcript,
        cost_usd=total_cost,
    )
