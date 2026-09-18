"""Checkpoint opponent: an ``rl_env`` (v1) MaskablePPO policy acting inside v2.

**Option B** (chosen over Option A): the observation 1.0 is reconstructed
*directly from the engine state* using ``rl_env.observations.encode_observation``
— an adapter 2.0 -> 1.0 is impossible because v2 deliberately dropped the
adversary board. The checkpoint's scaled observation, action mask and decoding
are all taken from ``rl_env`` (the exact catalogue it was trained on), then the
resulting engine command(s) are applied to the shared engine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

import rl_env.actions as rl_actions
import rl_env.observations as rl_obs
from game_engine.legal import current_decision
from game_engine.types import Action, GameState

DEFAULT_CHECKPOINT = Path(__file__).resolve().parents[2] / "runs" / "essai_01" / "best_model.zip"

_V1_SPACE = rl_obs.observation_space()
_V1_SCALES: dict[str, tuple[np.ndarray, np.ndarray]] = {}
for _key, _space in _V1_SPACE.spaces.items():
    if hasattr(_space, "low") and hasattr(_space, "high"):
        _low = _space.low.astype(np.float32)
        _high = _space.high.astype(np.float32)
        _V1_SCALES[_key] = (_low, np.where(_high > _low, _high - _low, 1.0))


def _scale_v1(obs: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    for key, value in obs.items():
        if key in _V1_SCALES:
            low, span = _V1_SCALES[key]
            out[key] = (np.asarray(value, dtype=np.float32) - low) / span
        else:
            out[key] = np.asarray(value)
    return out


class CheckpointPolicy:
    """Fixed opponent backed by the ``essai_01`` checkpoint (rl_env v1)."""

    name = "checkpoint"

    def __init__(self, checkpoint: str | Path = DEFAULT_CHECKPOINT, device: str = "cpu") -> None:
        path = Path(checkpoint)
        if not path.exists():
            raise FileNotFoundError(
                f"checkpoint introuvable: {path}. Aucun adversaire de substitution n'est appliqué; "
                "précisez --checkpoint ou régénérez essai_01/best_model.zip."
            )
        try:
            from sb3_contrib import MaskablePPO
        except ImportError as exc:  # pragma: no cover
            raise ImportError("sb3-contrib est requis pour l'adversaire checkpoint") from exc

        self.model = MaskablePPO.load(str(path), device=device)
        self.checkpoint = str(path)
        self._check_metadata(self.model)

    @staticmethod
    def _check_metadata(model: Any) -> None:
        expected = {
            "action_version": rl_actions.ACTION_VERSION,
            "observation_version": rl_obs.OBSERVATION_VERSION,
            "n_actions": rl_actions.N_ACTIONS,
        }
        meta = getattr(model, "dice_training_metadata", None) or {}
        got = {
            "action_version": meta.get("action_version"),
            "observation_version": meta.get("observation_version"),
            "n_actions": meta.get("n_actions", model.action_space.n),
        }
        if got != expected:
            raise ValueError(
                "Checkpoint incompatible avec l'environnement rl_env courant. "
                f"attendu={expected}, chargé={got}. Régénérez le checkpoint ou adaptez cet adaptateur."
            )

    def act(self, state: GameState) -> list[Action] | None:
        actor = current_decision(state).get("actor")
        if actor is None:
            return None
        obs = rl_obs.encode_observation(state, actor)  # agent-centric for the checkpoint's seat
        mask = rl_actions.legal_action_mask(state).astype(bool)
        if not mask.any():
            return None
        scaled = _scale_v1(obs)
        action_id, _ = self.model.predict(scaled, deterministic=True, action_masks=mask)
        action_id = int(np.asarray(action_id).item())
        return rl_actions.decode(state, action_id)

    def choose(self, state: GameState, legal_actions: list[Action] | None = None) -> list[Action] | None:
        """Same as :meth:`act` (``legal_actions`` kept for the documented interface)."""
        del legal_actions
        return self.act(state)
