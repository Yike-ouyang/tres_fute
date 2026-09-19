"""Adversary adapters used by :class:`rl_env.env.DiceGameEnv`.

An opponent is a small object exposing ``act(state) -> engine action``. Two are
provided:

* :class:`HeuristicOpponent` wraps the project's real heuristic policy
  (:class:`simulation.policy.HeuristicPolicy`), the same policy used for the web
  "fast advance".
* :class:`RandomOpponent` chooses uniformly among the **currently legal engine
  actions**. This sampling is uniform over *atomic engine commands*, not over
  strategies or complete moves; a move split into several commands therefore gets
  several chances. It is meant for smoke tests and to check masking, not as a
  strong baseline.
"""

from __future__ import annotations

import random

from game_engine.legal import legal_actions
from game_engine.types import Action, GameState
from simulation.policy import HeuristicPolicy

OPPONENT_KINDS = ("heuristic", "random")


class HeuristicOpponent:
    name = "heuristic"

    def __init__(self, seed: int | None = None) -> None:
        self.policy = HeuristicPolicy(seed=seed)

    def act(self, state: GameState) -> Action | None:
        return self.policy.choisir_action(state)


class RandomOpponent:
    name = "random"

    def __init__(self, seed: int | None = None) -> None:
        self.rng = random.Random(seed)

    def act(self, state: GameState) -> Action | None:
        legal = legal_actions(state)
        if not legal:
            return None
        return self.rng.choice(legal)


def make_opponent(kind: str, seed: int | None = None):
    """Factory: ``"heuristic"`` (default) or ``"random"``."""
    if kind == "heuristic":
        return HeuristicOpponent(seed=seed)
    if kind == "random":
        return RandomOpponent(seed=seed)
    raise ValueError(f"unknown opponent kind {kind!r}; expected one of {OPPONENT_KINDS}")
