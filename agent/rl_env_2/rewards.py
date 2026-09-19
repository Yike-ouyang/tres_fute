"""Reward sequence for :mod:`rl_env_2` (the engine never owns rewards).

Four modes, cumulative (run N+1 adds a term to run N):

* ``score_delta_normalized``: ``delta(score) / 100``
* ``fox``: + ``0.5 * delta(fox_count) * min_zone_after``
* ``zone``: + ``0.2 * delta(zones_completed)``
* ``terminal``: + ``+1`` (win) / ``0`` (draw) / ``-1`` (loss) at the very end
"""

from __future__ import annotations

from dataclasses import dataclass

REWARD_MODES = ("score_delta_normalized", "fox", "zone", "terminal")


@dataclass(frozen=True)
class StepStats:
    score: int
    fox: int
    zones_completed: int
    min_zone: int


class SequenceReward:
    def __init__(
        self,
        mode: str = "score_delta_normalized",
        *,
        scale: float = 100.0,
        fox_weight: float = 0.5,
        zone_weight: float = 0.2,
        terminal_weight: float = 1.0,
    ) -> None:
        if mode not in REWARD_MODES:
            raise ValueError(f"unknown reward mode {mode!r}; expected one of {REWARD_MODES}")
        self.mode = mode
        self.scale = float(scale)
        self.fox_weight = float(fox_weight)
        self.zone_weight = float(zone_weight)
        self.terminal_weight = float(terminal_weight)

    def compute(self, before: StepStats, after: StepStats, *, terminated: bool, result: str | None = None) -> float:
        reward = (after.score - before.score) / self.scale
        if self.mode in ("fox", "zone", "terminal"):
            reward += self.fox_weight * (after.fox - before.fox) * after.min_zone
        if self.mode in ("zone", "terminal"):
            reward += self.zone_weight * (after.zones_completed - before.zones_completed)
        if self.mode == "terminal" and terminated:
            reward += self.terminal_weight * {"win": 1.0, "draw": 0.0, "loss": -1.0}.get(result or "", 0.0)
        return float(reward)


def describe(mode: str) -> str:
    return {
        "score_delta_normalized": "r = delta(score)/100",
        "fox": "r = delta(score)/100 + 0.5*delta(fox)*min_zone_after",
        "zone": "r = delta(score)/100 + 0.5*delta(fox)*min_zone_after + 0.2*delta(zones_completed)",
        "terminal": (
            "r = delta(score)/100 + 0.5*delta(fox)*min_zone_after + 0.2*delta(zones_completed) "
            "+ (+1 win / 0 draw / -1 loss at the end)"
        ),
    }[mode]
