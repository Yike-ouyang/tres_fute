"""Reward computation for :mod:`rl_env` (the engine never owns rewards).

Two modes:

* ``score_delta`` (default): ``(score_agent_after - score_agent_before) / scale``.
  The reward is computed over the whole transition of a ``step()`` — including
  automatic consequences and the adversary's actions executed inside that step.
  No extra terminal reward is granted. With ``gamma = 1`` the sum of the deltas
  from the first observation returned by ``reset()`` telescopes exactly to
  ``score_final - score_at_first_observation``. Automatic progress that happens
  *before* that first observation (turn-1 grant, dice roll, opponent start) is
  therefore outside the telescoping window and is documented in the README.
* ``terminal_score``: ``0`` until the game really ends, then ``score_final / scale``.

A ``gamma < 1`` discount is applied by the learning algorithm outside the
environment; its meaning depends on the chosen decision decomposition.
"""

from __future__ import annotations

DEFAULT_REWARD_SCALE = 1.0
REWARD_MODES = ("score_delta", "terminal_score")


class RewardCalculator:
    def __init__(self, mode: str = "score_delta", scale: float = DEFAULT_REWARD_SCALE) -> None:
        if mode not in REWARD_MODES:
            raise ValueError(f"unknown reward mode {mode!r}; expected one of {REWARD_MODES}")
        if scale <= 0:
            raise ValueError("reward_scale must be strictly positive")
        self.mode = mode
        self.scale = float(scale)

    def compute(self, *, score_before: int, score_after: int, terminated: bool) -> float:
        if self.mode == "score_delta":
            return (score_after - score_before) / self.scale
        return (score_after / self.scale) if terminated else 0.0
