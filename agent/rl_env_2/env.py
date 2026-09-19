"""``DiceGameEnv2``: observation/action v2 environment, agent vs fixed opponent.

Subclasses :class:`rl_env.env.DiceGameEnv` (same engine driving, seeds, trace and
opponent flow) but overrides the action catalogue (v2, factorised), the
observation (v2, agent-centric) and the reward (the four-term sequence).
``gamma`` is stored for the training script only; Gymnasium never sees it.
"""

from __future__ import annotations

import random
from typing import Any

import numpy as np
from gymnasium import spaces

from game_engine.engine import GameEngine
from game_engine.serialize import observe as observe_state
from rl_env.env import DiceGameEnv
from rl_env.observations import decision_kind

from .actions import (
    ACTION_VERSION_2,
    BLUE_BONUS_CELL_COUNT,
    BLUE_BONUS_CELL_OFFSET,
    N_ACTIONS_2,
    TURQUOISE_BONUS_ROW_COUNT,
    TURQUOISE_BONUS_ROW_OFFSET,
    Pending,
    build_legal_decisions,
    decode,
    label,
    legal_action_mask,
)
from .observations import OBSERVATION_VERSION_2, ZONE_THRESHOLDS, encode_observation_2, observation_space_2, zone_scores
from .opponents import make_opponent_2
from .rewards import REWARD_MODES, SequenceReward, StepStats

DEFAULT_GAMMA = 0.999


class DiceGameEnv2(DiceGameEnv):
    def __init__(
        self,
        agent_player: int | str = 1,
        opponent: str = "heuristic",
        opponent_seed: int | None = None,
        reward_mode: str = "score_delta_normalized",
        max_steps: int | None = None,
        log_engine_actions: bool = False,
        render_mode: str | None = None,
        trace: bool = False,
        gamma: float = DEFAULT_GAMMA,
        opponent_kwargs: dict[str, Any] | None = None,
    ) -> None:
        if reward_mode not in REWARD_MODES:
            raise ValueError(f"reward_mode must be one of {REWARD_MODES}")
        if not 0.0 < gamma <= 1.0:
            raise ValueError("gamma must be in (0, 1]")
        # Base __init__ validates the seat and sets seeds/trace; opponent kind is
        # overridden below because v2 adds the "checkpoint" opponent.
        super().__init__(
            agent_player=agent_player,
            opponent="heuristic",
            opponent_seed=opponent_seed,
            reward_mode="score_delta",
            reward_scale=1.0,
            max_steps=max_steps,
            log_engine_actions=log_engine_actions,
            render_mode=render_mode,
            trace=trace,
        )
        self.opponent_kind = opponent
        self.opponent_kwargs = opponent_kwargs or {}
        self.gamma = float(gamma)
        self.sequence_reward = SequenceReward(reward_mode)
        self.reward_mode_2 = reward_mode
        self.action_space = spaces.Discrete(N_ACTIONS_2)
        self.observation_space = observation_space_2()
        self._pending = Pending()
        self._agent_stats: StepStats | None = None

    # ------------------------------------------------------------------ reset

    def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
        super(DiceGameEnv, self).reset(seed=seed)  # gymnasium bookkeeping only
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
        opp_seed = self.opponent_kwargs.get("seed", opponent_seed)
        self.opponent = make_opponent_2(self.opponent_kind, seed=opp_seed, **{
            k: v for k, v in self.opponent_kwargs.items() if k != "seed"
        })

        self.engine = GameEngine(seed=engine_seed, log_actions=self.log_engine_actions)
        self._terminated = False
        self._truncated = False
        self._steps = 0
        self._applied = 0
        self._opponent_applied = 0
        self.trace = []
        self.trace_initial = observe_state(self.engine.state)["state"] if self.trace_enabled else None
        self._pending = Pending()

        self._advance_until_agent_or_done()
        self._agent_stats = self._compute_stats()
        return self._observation(), self._info()

    # ------------------------------------------------------------------ step

    def step(self, action_id: int):
        if self.engine is None or self._terminated or self._truncated:
            raise RuntimeError("step() called after the episode ended; call reset() first")
        action_id = int(action_id)
        if not (0 <= action_id < N_ACTIONS_2):
            raise ValueError(f"action id {action_id} outside [0, {N_ACTIONS_2})")

        self._applied = 0
        self._opponent_applied = 0
        before = self._agent_stats

        # --- second half of a factorised decision -------------------------
        if self._pending.blue_cell is not None or self._pending.turquoise_row is not None:
            if not self.action_masks()[action_id]:
                raise ValueError(f"action id {action_id} is masked in the factorised sub-decision")
            sequence = decode(self.engine.state, action_id, self._pending)
            rl_info = {"id": action_id, "label": label(action_id)}
            self._pending = Pending()
            for i, action in enumerate(sequence):
                self._apply(action, role="agent", rl=rl_info if i == 0 else None)
            self._advance_until_agent_or_done()
            return self._finish_step(before)

        if not self.action_masks()[action_id]:
            raise ValueError(f"action id {action_id} is masked (illegal) in the current decision {self._current_kind()}")

        # --- first half of a factorised decision --------------------------
        if BLUE_BONUS_CELL_OFFSET <= action_id < BLUE_BONUS_CELL_OFFSET + BLUE_BONUS_CELL_COUNT:
            self._pending = Pending(blue_cell=self._factorised_choice(action_id, "blue-bonus-cell"))
            return self._observation(), 0.0, False, False, self._info()
        if TURQUOISE_BONUS_ROW_OFFSET <= action_id < TURQUOISE_BONUS_ROW_OFFSET + TURQUOISE_BONUS_ROW_COUNT:
            self._pending = Pending(turquoise_row=self._factorised_choice(action_id, "turquoise-bonus-row"))
            return self._observation(), 0.0, False, False, self._info()

        sequence = decode(self.engine.state, action_id, self._pending)
        rl_info = {"id": action_id, "label": label(action_id)}
        for i, action in enumerate(sequence):
            self._apply(action, role="agent", rl=rl_info if i == 0 else None)

        self._advance_until_agent_or_done()
        return self._finish_step(before)

    def _factorised_choice(self, action_id: int, prefix: str) -> int:
        for decision in build_legal_decisions(self.engine.state, self._pending):
            if decision.action_id == action_id:
                return int(decision.label.split(":", 1)[1])
        raise ValueError(f"factorised action {action_id} not legal")

    def _finish_step(self, before: StepStats | None):
        self._steps += 1
        after = self._compute_stats()
        scores = self.engine.scores()
        adversary = 2 if self.agent_player == 1 else 1
        result = None
        if self._terminated:
            a, b = scores[self.agent_player]["total"], scores[adversary]["total"]
            result = "win" if a > b else "loss" if a < b else "draw"
        reward = self.sequence_reward.compute(before or after, after, terminated=self._terminated, result=result)
        self._agent_stats = after
        if not self._terminated and self.max_steps is not None and self._steps >= self.max_steps:
            self._truncated = True
        return self._observation(), reward, self._terminated, self._truncated, self._info()

    # ------------------------------------------------------------------ driving

    def _advance_until_agent_or_done(self) -> None:
        assert self.engine is not None
        for _ in range(100_000):
            if self.engine.is_over():
                self._terminated = True
                return
            legal = self.engine.legal_actions()
            if not legal:
                raise RuntimeError(f"engine exposes no legal action ({self._current_kind()})")
            if len(legal) == 1:
                self._apply(legal[0], role="auto")
                continue
            actor = self.engine.current_decision().get("actor")
            if actor == self.agent_player:
                if not legal_action_mask(self.engine.state, self._pending).any():
                    raise RuntimeError(f"agent decision {self._current_kind()} maps to no catalogue 2.0 action")
                return
            if actor is None:
                raise RuntimeError(f"decision {self._current_kind()} has no attributable actor")
            assert self.opponent is not None
            action = self.opponent.act(self.engine.state)
            if action is None:
                raise RuntimeError("opponent returned no action")
            if isinstance(action, list):
                for a in action:
                    self._apply(a, role="opponent")
            else:
                self._apply(action, role="opponent")
        raise RuntimeError("internal loop exceeded 100000 steps")

    # ------------------------------------------------------------------ spaces / helpers

    def action_masks(self) -> np.ndarray:
        if self.engine is None or self._terminated or self._truncated:
            return np.zeros(N_ACTIONS_2, dtype=bool)
        return legal_action_mask(self.engine.state, self._pending).astype(bool)

    def _compute_stats(self) -> StepStats:
        assert self.engine is not None
        board = self.engine.state["boards"][self.agent_player]
        scores = self.engine.scores()[self.agent_player]
        zones = zone_scores(board)  # type: ignore[arg-type]
        completed = sum(1 for z in zones if zones[z] >= ZONE_THRESHOLDS[z])
        return StepStats(
            score=int(scores["total"]),
            fox=int(scores["fox_count"]),
            zones_completed=completed,
            min_zone=min(zones.values()),
        )

    def _observation(self) -> dict[str, np.ndarray]:
        assert self.engine is not None
        return encode_observation_2(self.engine.state, self.agent_player, self._pending.blue_cell, self._pending.turquoise_row)

    def _info(self) -> dict[str, Any]:
        info = super()._info()
        info["observation_version"] = OBSERVATION_VERSION_2
        info["action_version"] = ACTION_VERSION_2
        info["n_actions"] = N_ACTIONS_2
        info["gamma"] = self.gamma
        info["reward_mode"] = self.reward_mode_2
        info["pending_blue_cell"] = self._pending.blue_cell
        info["pending_turquoise_row"] = self._pending.turquoise_row
        return info

    def close(self) -> None:  # pragma: no cover - trivial
        super().close()
