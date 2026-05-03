"""Per-job cost ledger.

The Rust core already aggregates cost into job state, but agents track local
cost during a single run so they can decide whether to escalate or abort.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CostLedger:
    spent_usd: float = 0.0
    cap_usd: float = 5.0
    by_model: dict[str, float] = field(default_factory=dict)

    def charge(self, model: str, usd: float) -> None:
        self.spent_usd += usd
        self.by_model[model] = self.by_model.get(model, 0.0) + usd

    def remaining(self) -> float:
        return max(0.0, self.cap_usd - self.spent_usd)

    @property
    def exhausted(self) -> bool:
        return self.spent_usd >= self.cap_usd
