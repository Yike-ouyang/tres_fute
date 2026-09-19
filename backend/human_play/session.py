"""``HumanGameSession`` : orchestre une partie humaine sur ``GameEngine``.

Le catalogue d'actions est **v2** (``rl_env_2``, 149 ids) : ``legal_actions()``
renvoie des ``{id, label, category, ...}`` et ``step(action_id)`` applique la
décision. L'IA (mode ``ai``) est pilotée par :class:`human_play.opponent.AIPolicy`
et joue automatiquement jusqu'à la prochaine décision humaine (ou la fin).

Les décisions factorisées v2 (bonus bleu/turquoise) sont conservées dans
``self.pending`` : un premier id n'applique aucune commande moteur et arme le
choix ; l'id suivant complète la décision.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from game_engine.engine import GameEngine
from game_engine.legal import current_decision
from game_engine.serialize import observe as observe_state

from rl_env_2.actions import (
    ACTING_COLORS,
    Pending,
    build_legal_decisions,
    label,
)

from .opponent import AIPolicy, find_default_checkpoint

OPPONENT_KINDS = ("human", "ai")
_MAX_INTERNAL_STEPS = 100_000


class HumanGameSession:
    """Une partie : hot-seat (``human``) ou humain contre IA (``ai``)."""

    def __init__(
        self,
        agent_player: int = 1,
        opponent_kind: str = "human",
        checkpoint: str | None = None,
        seed: int | None = None,
        trace: bool = True,
        session_id: str | None = None,
    ) -> None:
        self.trace_enabled = trace
        self.session_id = session_id
        self.reset(agent_player=agent_player, opponent_kind=opponent_kind, checkpoint=checkpoint, seed=seed)

    # ------------------------------------------------------------------ reset
    def reset(
        self,
        agent_player: int = 1,
        opponent_kind: str = "human",
        checkpoint: str | None = None,
        seed: int | None = None,
    ) -> dict[str, Any]:
        if agent_player not in (1, 2):
            raise ValueError("agent_player doit être 1 ou 2")
        if opponent_kind not in OPPONENT_KINDS:
            raise ValueError(f"opponent_kind doit être l'un de {OPPONENT_KINDS}")

        self.human_player = int(agent_player)
        self.opponent_kind = opponent_kind
        self.seed = seed

        self.ai: AIPolicy | None = None
        self.checkpoint: str | None = None
        if opponent_kind == "ai":
            resolved = checkpoint or find_default_checkpoint()
            if resolved is None:
                raise FileNotFoundError(
                    "Aucun best_model.zip v2 trouvé sous agent/runs/{solo_*,shaped_*}; "
                    "précisez checkpoint=... ou --checkpoint."
                )
            self.ai = AIPolicy(resolved)
            self.checkpoint = str(resolved)

        self.engine = GameEngine(seed=seed)
        self.pending = Pending()
        self.trace: list[dict[str, Any]] = []
        self.trace_initial = observe_state(self.engine.state)["state"] if self.trace_enabled else None
        self._human_decisions = 0
        self._last_ai: list[dict[str, Any]] = []

        self._advance()
        return self.state_json()

    # ------------------------------------------------------------------ helpers
    def _is_human(self, player: int | None) -> bool:
        if player is None:
            return False
        if self.opponent_kind == "human":
            return True
        return player == self.human_player

    @property
    def human_decisions(self) -> int:
        return self._human_decisions

    def is_over(self) -> bool:
        return self.engine.is_over()

    def final_scores(self) -> dict[str, Any]:
        scores = self.engine.scores()
        adversary = 2 if self.human_player == 1 else 1
        return {
            "agent": int(scores[self.human_player]["total"]),
            "adversary": int(scores[adversary]["total"]),
            "scores_full": {str(p): scores[p] for p in (1, 2)},
        }

    def opponent_relpath(self) -> str | None:
        """Chemin du checkpoint relatif à ``agent/`` (préfixe ``runs/`` retiré)."""
        if not self.checkpoint:
            return None
        path = Path(self.checkpoint).resolve()
        agent = Path(__file__).resolve().parents[2] / "agent"
        try:
            parts = list(path.relative_to(agent).parts)
        except ValueError:
            return path.name
        if parts and parts[0] == "runs":
            parts = parts[1:]
        return "/".join(parts)

    def opponent_name(self) -> str | None:
        """Nom lisible : ``run / sous-dossier (fichier)``."""
        rel = self.opponent_relpath()
        if rel is None:
            return None
        parts = rel.split("/")
        file = parts[-1]
        if len(parts) == 1:
            return file
        return " / ".join(parts[:-1]) + f" ({file})"

    def cancel(self) -> dict[str, Any]:
        """Annule la sélection en cours (décision factorisée ou sélection moteur)."""
        if self.pending.blue_cell is not None or self.pending.turquoise_row is not None:
            self.pending = Pending()
            return self.state_json()
        if self.engine.state["selection"] is not None:
            self._apply({"type": "cancel_selection"}, role="agent")
            self._advance()
        return self.state_json()

    # ------------------------------------------------------------------ driving
    def _apply(self, action: dict[str, Any], *, role: str, rl: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        decision_before = current_decision(self.engine.state)
        actor_before = decision_before.get("actor")
        events = self.engine.step(dict(action))
        if not events:
            raise RuntimeError(f"le moteur a rejeté l'action {action!r} pendant {decision_before.get('kind')}")
        if self.trace_enabled:
            view = observe_state(self.engine.state)
            self.trace.append(
                {
                    "index": len(self.trace),
                    "role": role,
                    "actor": actor_before,
                    "decision_kind": decision_before.get("kind"),
                    "action": copy.deepcopy(action),
                    "state": view["state"],
                    "decision": view["decision"],
                    "scores": view["scores"],
                    "message": view["state"].get("message"),
                    "rl": copy.deepcopy(rl),
                }
            )
        return events

    def _ai_turn(self) -> list[dict[str, Any]]:
        assert self.ai is not None
        actions, info = self.ai.act(self.engine.state)
        events: list[dict[str, Any]] = []
        if not actions:
            # Première moitié d'une décision factorisée : rien n'est appliqué.
            self._last_ai.append({"kind": "factorised-step1", **info} if info else {"kind": "factorised-step1"})
            return events
        for i, action in enumerate(actions):
            events += self._apply(action, role="opponent", rl=(info if i == 0 else None))
        self._last_ai.append({"kind": "move", "actions": copy.deepcopy(actions), **(info or {})})
        return events

    def _advance(self) -> None:
        for _ in range(_MAX_INTERNAL_STEPS):
            if self.engine.is_over():
                return
            legal = self.engine.legal_actions()
            if not legal:
                raise RuntimeError(
                    f"aucune action légale ({current_decision(self.engine.state).get('kind')})"
                )
            if len(legal) == 1:
                self._apply(legal[0], role="auto")
                continue
            actor = current_decision(self.engine.state).get("actor")
            if actor is None:
                raise RuntimeError("décision sans acteur alors que plusieurs actions sont légales")
            if self._is_human(actor):
                return
            self._ai_turn()
        raise RuntimeError("boucle interne dépassée (incohérence moteur)")

    # ------------------------------------------------------------------ human API
    def legal_actions(self) -> list[dict[str, Any]]:
        if self.engine.is_over():
            return []
        out: list[dict[str, Any]] = []
        for decision in build_legal_decisions(self.engine.state, self.pending):
            name = label(decision.action_id)
            out.append(
                {
                    "id": int(decision.action_id),
                    "label": name,
                    "detail": decision.label,
                    "category": name.split(":", 1)[0],
                    "factorised_step1": not decision.actions,
                }
            )
        return out

    def step(self, action_id: int) -> dict[str, Any]:
        if self.engine.is_over():
            raise RuntimeError("la partie est terminée")
        actor = current_decision(self.engine.state).get("actor")
        if not self._is_human(actor):
            raise RuntimeError(f"ce n'est pas au tour du joueur humain (acteur={actor})")

        decision = next(
            (d for d in build_legal_decisions(self.engine.state, self.pending) if d.action_id == int(action_id)),
            None,
        )
        if decision is None:
            raise ValueError(f"action {action_id} illégale dans la décision courante")

        events: list[dict[str, Any]] = []
        if not decision.actions:
            name = label(decision.action_id).split(":", 1)[0]
            value = int(decision.label.split(":", 1)[1])
            if name == "blue_bonus_cell":
                self.pending = Pending(blue_cell=value)
            elif name == "turquoise_bonus_row":
                self.pending = Pending(turquoise_row=value)
            else:
                raise RuntimeError(f"décision factorisée inattendue {decision.label!r}")
            return self.state_json(events=events)

        self.pending = Pending()
        info = {"id": int(decision.action_id), "label": label(decision.action_id)}
        for i, action in enumerate(decision.actions):
            events += self._apply(action, role="agent", rl=(info if i == 0 else None))
        self._human_decisions += 1
        self._advance()
        return self.state_json(events=events)

    # ------------------------------------------------------------------ JSON
    def state_json(self, events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        snapshot = self.engine.observe()
        actor = current_decision(self.engine.state).get("actor")
        over = self.engine.is_over()
        return {
            "session_id": self.session_id,
            "seed": self.engine.seed,
            "rules_version": self.engine.rules_version,
            "human_player": self.human_player,
            "opponent": self.opponent_kind,
            "checkpoint": self.checkpoint,
            "opponent_name": self.opponent_name(),
            "opponent_relpath": self.opponent_relpath(),
            "is_over": over,
            "human_turn": (not over) and self._is_human(actor),
            "acting_player": actor,
            "awaiting_value": self.pending.blue_cell is not None or self.pending.turquoise_row is not None,
            "human_decisions": self._human_decisions,
            "last_ai_actions": copy.deepcopy(self._last_ai),
            "legal_actions": self.legal_actions(),
            "events": events or [],
            "final_scores": self.final_scores() if over else None,
            **snapshot,
        }


__all__ = ["HumanGameSession", "OPPONENT_KINDS", "ACTING_COLORS"]
