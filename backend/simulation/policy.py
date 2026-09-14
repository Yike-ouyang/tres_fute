"""Autoplay policy. The max-die filter on active rounds 1–2 is policy, not legality."""

from __future__ import annotations

import random
from typing import Any

from game_engine.legal import is_global_turn_complete, legal_actions
from game_engine.types import ALL_DIE_COLORS, Action, GameState

AUTOPLAY_STEP_CAP = 8000


def restrict_active_die_select(state: GameState, acts: list[Action]) -> list[Action]:
    select_acts = [a for a in acts if a["type"] == "select_die"]
    rest = [a for a in acts if a["type"] != "select_die"]
    phase = state["phase"]
    if phase["kind"] != "active" or phase["round"] > 2 or state["joker_pending"] or not select_acts:
        return acts
    available = [c for c in ALL_DIE_COLORS if state["dice"][c]["location"] == "available"]
    if not available:
        return acts
    max_phys = max(state["dice"][c]["value"] for c in available)
    lower = [a for a in select_acts if state["dice"][a["color"]]["value"] < max_phys]
    if lower:
        return [*rest, *lower]
    return acts


def pick_autoplay_action(state: GameState, rng: random.Random) -> Action | None:
    raw = legal_actions(state)
    if not raw:
        return None
    if any(a["type"] == "confirm_move" for a in raw):
        return {"type": "confirm_move"}
    acts = restrict_active_die_select(state, raw)
    if not acts:
        return None
    return rng.choice(acts)


def next_autoplay_action(
    state: GameState, completed: int, quota: int, rng: random.Random
) -> tuple[Action | None, bool, str | None]:
    if state["phase"]["kind"] == "game-over":
        return None, True, None
    if is_global_turn_complete(state) and completed >= quota:
        if state["global_turn"] >= 6:
            return {"type": "continue"}, False, None
        return None, True, None
    action = pick_autoplay_action(state, rng)
    if action is None:
        return None, True, "Aucune action autoplay légale."
    return action, False, None


def fingerprint(state: GameState) -> str:
    return repr(
        (
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
            state["global_turn"],
            state["message"],
        )
    )


def run_autoplay(
    engine: Any,
    n_turns: int,
    policy_rng: random.Random,
    step_cap: int = AUTOPLAY_STEP_CAP,
    on_progress: Any | None = None,
) -> dict[str, Any]:
    """Advance up to n_turns global turns. Stops on game-over or anti-loop."""
    completed = 0
    last_fp = fingerprint(engine.state)
    stopped = "quota"
    for step in range(step_cap):
        before_complete = engine.turn_complete()
        action, stop, reason = next_autoplay_action(engine.state, completed, n_turns, policy_rng)
        if stop:
            stopped = reason or "quota"
            break
        events = engine.step(action)
        if not events:
            stopped = "blocage"
            break
        if not before_complete and engine.turn_complete():
            completed += 1
            if on_progress:
                on_progress(completed, n_turns)
        fp = fingerprint(engine.state)
        if fp == last_fp:
            stopped = "blocage"
            break
        last_fp = fp
        if engine.is_over():
            stopped = "game-over"
            break
        if step == step_cap - 1:
            stopped = "step-cap"
    return {"completed": completed, "stopped": stopped, "over": engine.is_over(), "scores": engine.scores()}
