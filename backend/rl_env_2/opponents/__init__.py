"""Opponents for :mod:`rl_env_2`.

``heuristic`` and ``random`` reuse :mod:`rl_env.opponents`; ``checkpoint`` loads
the ``essai_01`` MaskablePPO policy (rl_env v1) as a fixed adversary.
"""

from __future__ import annotations

from rl_env.opponents import HeuristicOpponent, RandomOpponent

from .checkpoint_policy import DEFAULT_CHECKPOINT, CheckpointPolicy

OPPONENT_KINDS_2 = ("heuristic", "random", "checkpoint")

__all__ = ["CheckpointPolicy", "DEFAULT_CHECKPOINT", "HeuristicOpponent", "RandomOpponent", "make_opponent_2"]


def make_opponent_2(kind: str, seed: int | None = None, **kwargs):
    if kind == "heuristic":
        return HeuristicOpponent(seed=seed)
    if kind == "random":
        return RandomOpponent(seed=seed)
    if kind == "checkpoint":
        return CheckpointPolicy(checkpoint=kwargs.get("checkpoint", DEFAULT_CHECKPOINT), device=kwargs.get("device", "cpu"))
    raise ValueError(f"unknown opponent kind {kind!r}; expected one of {OPPONENT_KINDS_2}")
