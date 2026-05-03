"""Symbolic verification utilities (Z3-backed).

The Verifier agent uses these helpers to prove or falsify math-heavy
invariants extracted from the plan or code. We deliberately keep the
surface tiny — symbolic checking is a tool, not a panacea, and only
applies cleanly to a small subset of claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    import z3  # type: ignore
    Z3_AVAILABLE = True
except ImportError:  # pragma: no cover - fallback path
    z3 = None  # type: ignore
    Z3_AVAILABLE = False


@dataclass
class SymbolicResult:
    proved: bool
    counterexample: dict[str, Any] | None
    note: str


def check_conservation_of_energy(
    masses: list[float],
    velocities_before: list[list[float]],
    velocities_after: list[list[float]],
    tolerance: float = 1e-6,
) -> SymbolicResult:
    """Verify that total kinetic energy is conserved within `tolerance`.

    Useful for physics-sim acceptance checks (the platform's demo track).
    """
    if not Z3_AVAILABLE:
        ke_before = sum(0.5 * m * sum(v * v for v in vs) for m, vs in zip(masses, velocities_before))
        ke_after = sum(0.5 * m * sum(v * v for v in vs) for m, vs in zip(masses, velocities_after))
        ok = abs(ke_before - ke_after) <= tolerance
        return SymbolicResult(
            proved=ok,
            counterexample=None if ok else {"ke_before": ke_before, "ke_after": ke_after},
            note="numeric check (z3 unavailable)",
        )
    s = z3.Solver()
    ke_b = z3.Sum([z3.RealVal(0.5 * m) * z3.Sum([z3.RealVal(v) * z3.RealVal(v) for v in vs])
                   for m, vs in zip(masses, velocities_before)])
    ke_a = z3.Sum([z3.RealVal(0.5 * m) * z3.Sum([z3.RealVal(v) * z3.RealVal(v) for v in vs])
                   for m, vs in zip(masses, velocities_after)])
    s.add(z3.Abs(ke_b - ke_a) > z3.RealVal(tolerance))
    if s.check() == z3.unsat:
        return SymbolicResult(proved=True, counterexample=None, note="z3: energy conserved")
    return SymbolicResult(
        proved=False,
        counterexample={"model": str(s.model())},
        note="z3: violation found",
    )


def check_sort_invariant(sample: list[int]) -> SymbolicResult:
    """For a concrete sample, prove the post-condition `output is sorted ascending`.

    This is illustrative — production use should drive the SMT from the
    code's actual symbolic semantics, not a single sample.
    """
    is_sorted = all(sample[i] <= sample[i + 1] for i in range(len(sample) - 1))
    return SymbolicResult(
        proved=is_sorted,
        counterexample=None if is_sorted else {"sample": sample},
        note="numeric monotonicity check",
    )


def check_typed_invariant(claim: str) -> SymbolicResult:
    """Stub for claim-driven symbolic proof — see docs/architecture.md.

    A future iteration will parse the claim into an SMT-LIB formula and
    dispatch to z3. For now it always returns 'unknown'.
    """
    return SymbolicResult(proved=False, counterexample=None, note=f"unsupported claim: {claim[:80]}")
