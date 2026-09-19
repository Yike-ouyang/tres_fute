"""Adversaire IA piloté par un checkpoint ``MaskablePPO`` de ``rl_env_2``.

Le catalogue principal est **v2** (149 actions, ``rl_env_2``). Un checkpoint v1
(316 actions, ex. ``essai_01``) est détecté et pris en charge via ``rl_env``.

L'adaptateur ne modifie jamais ``rl_env`` / ``rl_env_2`` : il lit l'état du
moteur partagé, reconstruit l'observation, applique la mise à l'échelle du
training (``FixedBoxScaling2``), puis décode l'identifiant d'action en
commandes moteur. Les décisions factorisées v2 (bonus bleu/turquoise) sont
gardées dans ``self.pending`` entre deux appels ``act``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from game_engine.legal import current_decision
from game_engine.types import Action, GameState

from rl_env_2.actions import (
    N_ACTIONS_2,
    Pending,
    build_legal_decisions,
    label as label_v2,
    legal_action_mask as mask_v2,
)
from rl_env_2.observations import encode_observation_2, observation_space_2

import rl_env.actions as rl_actions_v1
import rl_env.observations as rl_obs_v1


def _scales_from_space(space: Any) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    scales: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for key, sub in space.spaces.items():
        if hasattr(sub, "low") and hasattr(sub, "high"):
            low = np.asarray(sub.low, dtype=np.float32)
            high = np.asarray(sub.high, dtype=np.float32)
            scales[key] = (low, np.where(high > low, high - low, 1.0))
    return scales


_V2_SCALES = _scales_from_space(observation_space_2())
_V1_SCALES = _scales_from_space(rl_obs_v1.observation_space())


def _scale(obs: dict[str, np.ndarray], scales: dict[str, tuple[np.ndarray, np.ndarray]]) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    for key, value in obs.items():
        if key in scales:
            low, span = scales[key]
            out[key] = (np.asarray(value, dtype=np.float32) - low) / span
        else:
            out[key] = np.asarray(value)
    return out


def _base_dir(runs_root: Path | None = None) -> Path:
    """Racine de découverte des runs.

    Par défaut ``agent/`` (les runs peuvent vivre sous ``agent/<run>`` **ou**
    ``agent/runs/<run>``). ``runs_root`` (tests) impose une racine unique.
    """
    if runs_root is not None:
        return Path(runs_root)
    return Path(__file__).resolve().parents[2] / "agent"


def find_default_checkpoint(runs_root: Path | None = None) -> Path | None:
    """Dernier ``best_model.zip`` v2 sous ``agent/{runs/}`` (solo_*/shaped_*).

    ``None`` si aucun modèle n'est présent (les checkpoints v1 ``essai_01`` sont
    volontairement exclus : ce n'est pas le « meilleur modèle » v2).
    """
    base = _base_dir(runs_root)
    candidates: list[Path] = []
    for pattern in ("solo_*/score_delta_solo/best_model.zip", "shaped_*/run_*/best_model.zip"):
        candidates.extend(p for p in base.glob(f"**/{pattern}") if p.is_file())
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def list_checkpoints(runs_root: Path | None = None) -> list[dict[str, Any]]:
    """Checkpoints disponibles (tous les ``best_model.zip`` sous ``agent/{runs/}``).

    Chaque entrée : ``path, relpath, run, subdir, file, mtime, catalogue,
    is_default``. ``relpath`` est relatif à ``agent/`` (préfixe ``runs/`` retiré).
    ``catalogue`` vaut ``v2`` (rl_env_2, 149 actions) sauf ``essai_01`` (v1).
    """
    base = _base_dir(runs_root)
    agent = Path(__file__).resolve().parents[2] / "agent"
    default = find_default_checkpoint(runs_root)
    default_str = str(default.resolve()) if default else None
    models: list[dict[str, Any]] = []
    seen: set[str] = set()
    if not base.exists():
        return models
    for best in sorted(base.rglob("best_model.zip")):
        if not best.is_file():
            continue
        resolved = best.resolve()
        if str(resolved) in seen:
            continue
        seen.add(str(resolved))
        try:
            parts = list(resolved.relative_to(agent.resolve()).parts)
            if parts and parts[0] == "runs":
                parts = parts[1:]
        except ValueError:
            parts = [best.parent.name, best.name]
        models.append(
            {
                "path": str(resolved),
                "relpath": "/".join(parts),
                "run": parts[0] if parts else "",
                "subdir": "/".join(parts[1:-1]),
                "file": parts[-1] if parts else best.name,
                "mtime": best.stat().st_mtime,
                "catalogue": "v1" if "essai_01" in parts else "v2",
                "is_default": str(resolved) == default_str,
            }
        )
    models.sort(key=lambda m: m["mtime"], reverse=True)
    return models


class AIPolicy:
    """Politique MaskablePPO fixe (v2 par défaut, v1 en repli)."""

    def __init__(self, checkpoint: str | Path, device: str = "cpu", model: Any | None = None) -> None:
        path = Path(checkpoint)
        if model is None and not path.is_file():
            raise FileNotFoundError(f"checkpoint introuvable: {path}")
        if model is None:
            try:
                from sb3_contrib import MaskablePPO
            except ImportError as exc:  # pragma: no cover
                raise ImportError("sb3-contrib est requis pour l'adversaire IA") from exc
            model = MaskablePPO.load(str(path), device=device)

        self.model = model
        self.checkpoint = str(path)
        self.n_actions = int(self.model.action_space.n)
        if self.n_actions == N_ACTIONS_2:
            self.catalogue = "v2"
        elif self.n_actions == rl_actions_v1.N_ACTIONS:
            self.catalogue = "v1"
        else:
            raise ValueError(
                f"checkpoint incompatible: n_actions={self.n_actions} "
                f"(attendu {N_ACTIONS_2} pour rl_env_2 ou {rl_actions_v1.N_ACTIONS} pour rl_env)"
            )
        self.pending = Pending()
        self.last: dict[str, Any] | None = None

    def reset(self) -> None:
        self.pending = Pending()
        self.last = None

    # ------------------------------------------------------------------ act
    def act(self, state: GameState) -> tuple[list[Action], dict[str, Any] | None]:
        """Renvoie ``(commandes moteur, info)``.

        ``commandes`` est vide pour la première moitié d'une décision factorisée
        (v2) : ``info`` porte alors l'``id`` et le ``label`` choisis.
        """
        if self.catalogue == "v2":
            return self._act_v2(state)
        return self._act_v1(state)

    def _act_v2(self, state: GameState) -> tuple[list[Action], dict[str, Any] | None]:
        decisions = build_legal_decisions(state, self.pending)
        if not decisions:
            raise RuntimeError("IA (v2) : aucune décision légale")
        mask = mask_v2(state, self.pending).astype(bool)
        if not mask.any():
            raise RuntimeError("IA (v2) : masque vide")
        actor = current_decision(state).get("actor")
        obs = encode_observation_2(state, actor, self.pending.blue_cell, self.pending.turquoise_row)  # type: ignore[arg-type]
        action_id, _ = self.model.predict(_scale(obs, _V2_SCALES), deterministic=True, action_masks=mask)
        action_id = int(np.asarray(action_id).item())
        decision = next((d for d in decisions if d.action_id == action_id), None)
        if decision is None:
            raise RuntimeError(f"IA (v2) : id {action_id} illégal")
        info = {"id": action_id, "label": label_v2(action_id)}
        self.last = info
        if not decision.actions:
            name = label_v2(action_id).split(":", 1)[0]
            value = int(decision.label.split(":", 1)[1])
            if name == "blue_bonus_cell":
                self.pending = Pending(blue_cell=value)
            elif name == "turquoise_bonus_row":
                self.pending = Pending(turquoise_row=value)
            else:
                raise RuntimeError(f"IA (v2) : décision factorisée inattendue {decision.label!r}")
            return [], info
        self.pending = Pending()
        return [dict(a) for a in decision.actions], info

    def _act_v1(self, state: GameState) -> tuple[list[Action], dict[str, Any] | None]:
        actor = current_decision(state).get("actor")
        if actor is None:
            raise RuntimeError("IA (v1) : décision sans acteur")
        obs = rl_obs_v1.encode_observation(state, actor)
        mask = rl_actions_v1.legal_action_mask(state).astype(bool)
        if not mask.any():
            raise RuntimeError("IA (v1) : masque vide")
        action_id, _ = self.model.predict(_scale(obs, _V1_SCALES), deterministic=True, action_masks=mask)
        action_id = int(np.asarray(action_id).item())
        self.last = {"id": action_id, "label": rl_actions_v1.label(action_id)}
        return rl_actions_v1.decode(state, action_id), self.last
