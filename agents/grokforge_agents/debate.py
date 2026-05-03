"""Multi-agent debate loop.

Two roles — `proponent` and `skeptic` — argue over a contested claim. A
neutral `judge` reads the transcript and returns a verdict + confidence.
This is the only place in grokforge where the LLM is used adversarially:
the skeptic is explicitly prompted to find every possible failure mode.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .router import ModelRouter

PROPONENT_PROMPT = """You are the Proponent in a grokforge debate.
You believe the artifact under review is correct and meets the spec.
State the strongest concrete arguments — cite specific files, function
names, and test results. Do NOT concede unless presented with proof."""

SKEPTIC_PROMPT = """You are the Skeptic in a grokforge debate.
Find every plausible failure mode in the artifact: logic bugs, race
conditions, missing edge cases, hallucinated APIs, off-by-one errors,
spec drift. Be specific. Cite files and lines. Do NOT make up issues —
only ones grounded in the actual code shown."""

JUDGE_PROMPT = """You are the impartial Judge.
Read the proponent and skeptic's arguments and the underlying artifact.
Return strict JSON: {"winner": "proponent|skeptic|tie", "confidence": 0.0..1.0,
"rationale": "...", "blocking_issues": ["..."]}.
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


async def run_debate(
    router: ModelRouter,
    artifact_summary: str,
    rounds: int = 2,
    *,
    log: list[str] | None = None,
) -> DebateResult:
    log = log if log is not None else []
    transcript: list[dict[str, str]] = []
    total_cost = 0.0

    pro_msgs = [
        {"role": "system", "content": PROPONENT_PROMPT},
        {"role": "user", "content": f"Artifact under review:\n{artifact_summary}"},
    ]
    skep_msgs = [
        {"role": "system", "content": SKEPTIC_PROMPT},
        {"role": "user", "content": f"Artifact under review:\n{artifact_summary}"},
    ]

    for r in range(rounds):
        pro_text, c1, _ = await router.chat("verifier", pro_msgs, temperature=0.3, max_tokens=800)
        total_cost += c1
        transcript.append({"role": "proponent", "round": str(r), "content": pro_text})
        log.append(f"debate r{r}: proponent ({len(pro_text)} chars)")

        skep_msgs.append({"role": "user", "content": f"Proponent says:\n{pro_text}"})
        skep_text, c2, _ = await router.chat("verifier", skep_msgs, temperature=0.4, max_tokens=800)
        total_cost += c2
        transcript.append({"role": "skeptic", "round": str(r), "content": skep_text})
        log.append(f"debate r{r}: skeptic ({len(skep_text)} chars)")

        pro_msgs.append({"role": "user", "content": f"Skeptic says:\n{skep_text}"})

    judge_msgs = [
        {"role": "system", "content": JUDGE_PROMPT},
        {"role": "user", "content": f"Artifact:\n{artifact_summary}\n\n"
                                     f"Transcript:\n{json.dumps(transcript, indent=2)[:8000]}"},
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

    return DebateResult(
        winner=verdict.get("winner", "tie"),
        confidence=float(verdict.get("confidence", 0.5)),
        rationale=verdict.get("rationale", ""),
        blocking_issues=list(verdict.get("blocking_issues", [])),
        transcript=transcript,
        cost_usd=total_cost,
    )
