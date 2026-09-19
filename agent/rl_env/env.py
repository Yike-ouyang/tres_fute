"""``DiceGameEnv``: a Gymnasium environment for the full two-player game.

One instance is a complete two-player match driven directly against the Python
engine (no HTTP, no browser, no shared store). The externally-trained agent owns
one player (configurable); a fixed Python opponent owns the other. The
environment advances the opponent and all automatic/forced engine actions until
the agent must decide again.

Rewards belong to :mod:`rl_env.rewards`, never to the engine.
"""

from __future__ import annotations

import copy
import random
from typing import Any

import numpy as np
from gymnasium import Env, spaces

from game_engine.engine import GameEngine
from game_engine.serialize import observe as observe_state
from simulation.policy import fingerprint

from .actions import ACTION_VERSION, N_ACTIONS, decode, label, legal_action_mask
from .observations import OBSERVATION_VERSION, decision_kind, encode_observation, observation_space
from .opponents import make_opponent
from .rewards import RewardCalculator

MAX_INTERNAL_STEPS = 100_000
_NO_ACTION_LIMIT = "engine exposes no legal action while the game is not over"
_NO_PROGRESS = "engine state did not change after an accepted action"


class DiceGameEnv(Env):
    """Full Très Futé game, agent versus a fixed opponent."""

    metadata = {"render_modes": ["human", "ansi"], "render_fps": 4}

    def __init__(
        self,
        agent_player: int | str = 1,
        opponent: str = "heuristic",
        opponent_seed: int | None = None,
        reward_mode: str = "score_delta",
        reward_scale: float = 1.0,
        max_steps: int | None = None,
        log_engine_actions: bool = False,
        render_mode: str | None = None,
        trace: bool = False,
    ) -> None:
        super().__init__()
        if agent_player not in (1, 2, "random"):
            raise ValueError("agent_player must be 1, 2 or 'random'")
        if max_steps is not None and max_steps <= 0:
            raise ValueError("max_steps must be a positive integer or None")
        self.agent_player_config = agent_player
        self.opponent_kind = opponent
        self.opponent_seed = opponent_seed
        self.reward_calculator = RewardCalculator(reward_mode, reward_scale)
        self.max_steps = max_steps
        self.log_engine_actions = log_engine_actions
        self.render_mode = render_mode
        # When enabled, every atomic engine action applied is recorded (see ``_apply``).
        self.trace_enabled = trace
        self.trace: list[dict[str, Any]] = []

        self.action_space = spaces.Discrete(N_ACTIONS)
        self.observation_space = observation_space()

        # Persistent source so successive seedless resets differ (never a constant).
        self._seed_source = random.Random()
        self._seed: int | None = None

        self.engine: GameEngine | None = None
        self.agent_player: int = 1
        self.opponent = None
        self._terminated = True
        self._truncated = False
        self._steps = 0
        self._score_at_observation = 0
        self._applied = 0
        self._opponent_applied = 0

    # ------------------------------------------------------------------ seed

    @staticmethod
    def _derive(seed: int, index: int) -> int:
        return random.Random(seed + index * 1_000_003).randrange(2**31)

    def _rollback_seed(self, seed: int | None) -> int:
        if seed is not None:
            return int(seed)
        return self._seed_source.randrange(2**31)

    # ------------------------------------------------------------------ reset

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        master = self._rollback_seed(seed)
        self._seed = master
        engine_seed = self._derive(master, 1)
        opponent_seed = self._derive(master, 2)
        position_seed = self._derive(master, 3)

        if self.agent_player_config == "random":
            self.agent_player = random.Random(position_seed).choice([1, 2])
        else:
            self.agent_player = int(self.agent_player_config)

        if self.opponent_seed is not None:
            opponent_seed = self.opponent_seed
        self.opponent = make_opponent(self.opponent_kind, seed=opponent_seed)

        self.engine = GameEngine(seed=engine_seed, log_actions=self.log_engine_actions)
        self._terminated = False
        self._truncated = False
        self._steps = 0
        self._applied = 0
        self._opponent_applied = 0
        self.trace = []
        self.trace_initial = observe_state(self.engine.state)["state"] if self.trace_enabled else None

        self._advance_until_agent_or_done()
        self._score_at_observation = self._agent_score()
        return self._observation(), self._info()

    # ------------------------------------------------------------------ step

    def step(self, action_id: int):
        if self.engine is None or self._terminated or self._truncated:
            raise RuntimeError("step() called after the episode ended; call reset() first")
        mask = self.action_masks()
        action_id = int(action_id)
        if not (0 <= action_id < N_ACTIONS):
            raise ValueError(f"action id {action_id} outside [0, {N_ACTIONS})")
        if not mask[action_id]:
            raise ValueError(
                f"action id {action_id} is masked (illegal) in the current decision {self._current_kind()}"
            )

        # Counters describe this transition only ("since the last return").
        self._applied = 0
        self._opponent_applied = 0

        assert self.engine is not None
        sequence = decode(self.engine.state, action_id)
        rl_info = {"id": action_id, "label": label(action_id)}
        for i, action in enumerate(sequence):
            self._apply(action, role="agent", rl=rl_info if i == 0 else None)

        self._advance_until_agent_or_done()
        self._steps += 1

        score_after = self._agent_score()
        reward = self.reward_calculator.compute(
            score_before=self._score_at_observation,
            score_after=score_after,
            terminated=self._terminated,
        )
        self._score_at_observation = score_after

        if not self._terminated and self.max_steps is not None and self._steps >= self.max_steps:
            self._truncated = True

        return self._observation(), reward, self._terminated, self._truncated, self._info()

    # ------------------------------------------------------------------ driving

    def _apply(self, action: dict[str, Any], *, role: str, rl: dict[str, Any] | None = None) -> None:
        """Apply one atomic engine action.

        ``role`` is ``"agent"``, ``"opponent"`` or ``"auto"`` (forced/technical).
        When tracing is enabled, the atomic transition is appended to ``self.trace``.
        """
        assert self.engine is not None
        decision_before = self._current_kind()
        actor_before = self.engine.current_decision().get("actor")
        before = fingerprint(self.engine.state)
        events = self.engine.step(action)
        if not events:
            raise RuntimeError(f"engine rejected action {action!r} during {decision_before}")
        if fingerprint(self.engine.state) == before:
            raise RuntimeError(f"{_NO_PROGRESS}: {action!r}")
        self._applied += 1
        if role == "opponent":
            self._opponent_applied += 1
        if self.trace_enabled:
            view = observe_state(self.engine.state)
            self.trace.append(
                {
                    "index": len(self.trace),
                    "role": role,
                    "actor": actor_before,
                    "decision_kind": decision_before,
                    "action": copy.deepcopy(action),
                    "state": view["state"],
                    "decision": view["decision"],
                    "scores": view["scores"],
                    "message": view["state"].get("message"),
                    "rl": copy.deepcopy(rl),
                }
            )

    def _advance_until_agent_or_done(self) -> None:
        assert self.engine is not None
        for _ in range(MAX_INTERNAL_STEPS):
            if self.engine.is_over():
                self._terminated = True
                return
            legal = self.engine.legal_actions()
            if not legal:
                raise RuntimeError(f"{_NO_ACTION_LIMIT} ({self._current_kind()})")
            if len(legal) == 1:
                # Forced or purely technical command: apply automatically.
                self._apply(legal[0], role="auto")
                continue
            actor = self.engine.current_decision().get("actor")
            if actor == self.agent_player:
                if not legal_action_mask(self.engine.state).any():
                    raise RuntimeError(
                        f"agent decision {self._current_kind()} maps to no catalogue action; "
                        "extend rl_env/actions.py"
                    )
                return
            if actor is None:
                raise RuntimeError(
                    f"engine decision {self._current_kind()} has no attributable actor while "
                    f"{len(legal)} actions are legal"
                )
            assert self.opponent is not None
            action = self.opponent.act(self.engine.state)
            if action is None:
                raise RuntimeError("opponent returned no action")
            self._apply(action, role="opponent")
        raise RuntimeError("internal loop exceeded MAX_INTERNAL_STEPS (possible engine inconsistency)")

    # ------------------------------------------------------------------ spaces

    def action_masks(self) -> np.ndarray:
        """Boolean legal-action mask of shape ``(N_ACTIONS,)`` for the current decision."""
        if self.engine is None or self._terminated or self._truncated:
            return np.zeros(N_ACTIONS, dtype=bool)
        return legal_action_mask(self.engine.state).astype(bool)

    # ------------------------------------------------------------------ helpers

    def _agent_score(self) -> int:
        assert self.engine is not None
        return int(self.engine.scores()[self.agent_player]["total"])

    def _current_kind(self) -> str:
        return decision_kind(self.engine.state) if self.engine is not None else "none"

    def _observation(self) -> dict[str, np.ndarray]:
        assert self.engine is not None
        return encode_observation(self.engine.state, self.agent_player)

    def _info(self) -> dict[str, Any]:
        assert self.engine is not None
        state = self.engine.state
        scores = self.engine.scores()
        adversary = 2 if self.agent_player == 1 else 1
        info: dict[str, Any] = {
            "seed": self._seed,
            "agent_player": self.agent_player,
            "turn": state["global_turn"],
            "round": state["phase"].get("round", 0) or 0,
            "phase": state["phase"]["kind"],
            "decision": self._current_kind(),
            "scores": {
                "agent": scores[self.agent_player]["total"],
                "adversary": scores[adversary]["total"],
            },
            "scores_full": {str(p): scores[p] for p in (1, 2)},
            "engine_actions": self._applied,
            "opponent_actions": self._opponent_applied,
            "steps": self._steps,
            "rules_version": self.engine.rules_version,
            "observation_version": OBSERVATION_VERSION,
            "action_version": ACTION_VERSION,
            "action_mask": self.action_masks(),
        }
        if self._terminated:
            info["final_scores"] = {
                "agent": scores[self.agent_player]["total"],
                "adversary": scores[adversary]["total"],
            }
            info["result"] = (
                "win"
                if scores[self.agent_player]["total"] > scores[adversary]["total"]
                else "loss"
                if scores[self.agent_player]["total"] < scores[adversary]["total"]
                else "draw"
            )
        return info

    # ------------------------------------------------------------------ render

    def render(self):
        if self.engine is None:
            text = "DiceGameEnv (not reset)"
        else:
            state = self.engine.state
            scores = self.engine.scores()
            adversary = 2 if self.agent_player == 1 else 1
            text = (
                f"turn={state['global_turn']} phase={state['phase']['kind']} "
                f"decision={self._current_kind()} | "
                f"agent(P{self.agent_player})={scores[self.agent_player]['total']} "
                f"adversary(P{adversary})={scores[adversary]['total']}"
            )
        if self.render_mode == "ansi":
            return text
        print(text)
        return None

    def close(self) -> None:
        self.engine = None
        self.opponent = None
