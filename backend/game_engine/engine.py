"""Public GameEngine: seeded RNG per game, decisions, observations, replay log."""

from __future__ import annotations

import copy
import random
from typing import Any

from .legal import current_decision, is_global_turn_complete, legal_actions, remaining_autoplay_turns
from .reducer import create_initial_state, game_reducer
from .score import compute_score
from .serialize import observe as observe_state
from .types import Action, Event, GameState, PlayerId, RULES_VERSION


def _fingerprint(state: GameState) -> str:
    return repr(
        (
            state["global_turn"],
            state["phase"],
            state["dice"],
            state["selection"],
            state["plus1_active"],
            state["plus1_used_dice"],
            state["joker_pending"],
            state["pending_bonuses"],
            state["bonus_resolution"],
            state["pink_choice"],
            state["pending_advance"],
            state["boards"],
            state["message"],
        )
    )


def _events(before: GameState, after: GameState, action: Action) -> list[Event]:
    events: list[Event] = [{"type": "applied", "action": action}]
    if before["phase"] != after["phase"]:
        events.append({"type": "phase", "from": before["phase"], "to": after["phase"]})
    for pid in (1, 2):
        b0, b1 = before["boards"][pid], after["boards"][pid]
        for cid, val in b1["values"].items():
            if b0["values"].get(cid) != val:
                events.append({"type": "wrote_value", "player": pid, "cellId": cid, "value": val})
        for cid, checked in b1["checks"].items():
            if checked and not b0["checks"].get(cid):
                events.append({"type": "checked", "player": pid, "cellId": cid})
    return events


class GameEngine:
    """One match. Dice RNG is isolated; autoplay must use a separate Random."""

    def __init__(self, seed: int | None = None, state: GameState | None = None, log_actions: bool = True) -> None:
        self.seed = seed if seed is not None else random.randrange(2**31)
        self.rng = random.Random(self.seed)
        self.state: GameState = state if state is not None else create_initial_state(self.rng)
        self.action_log: list[Action] = []
        # ``log_actions`` can be disabled by RL training loops to avoid accumulating
        # one dict per applied action across thousands of episodes.
        self.log_actions = log_actions
        self.rules_version = RULES_VERSION

    def new_game(self, seed: int | None = None) -> GameState:
        self.seed = seed if seed is not None else random.randrange(2**31)
        self.rng = random.Random(self.seed)
        self.state = create_initial_state(self.rng)
        self.action_log = []
        return self.state

    def legal_actions(self) -> list[Action]:
        return legal_actions(self.state)

    def current_decision(self) -> dict[str, Any]:
        return current_decision(self.state)

    def step(self, action: Action) -> list[Event]:
        before = self.state
        rng_state = self.rng.getstate()
        after = game_reducer(before, action, self.rng)
        if after is before:
            self.rng.setstate(rng_state)
            return []
        self.state = after
        if self.log_actions:
            self.action_log.append(copy.deepcopy(action))
        return _events(before, after, action)

    def observe(self, player: PlayerId | None = None) -> dict[str, Any]:
        return observe_state(self.state, player)

    def scores(self) -> dict[int, dict[str, int]]:
        return {1: compute_score(self.state["boards"][1]), 2: compute_score(self.state["boards"][2])}

    def is_over(self) -> bool:
        return self.state["phase"]["kind"] == "game-over"

    def fingerprint(self) -> str:
        return _fingerprint(self.state)

    def remaining_turns(self) -> int:
        return remaining_autoplay_turns(self.state)

    def turn_complete(self) -> bool:
        return is_global_turn_complete(self.state)
