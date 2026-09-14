"""Shared fixtures for engine tests: empty boards and imposed dice (no RNG)."""

from __future__ import annotations

from typing import Any

from game_engine.bonuses import empty_bonus_state
from game_engine.types import ALL_DIE_COLORS, DieColor, DieRuntime, GameState, PlayerBoard, empty_plus1_used_dice


def empty_board() -> PlayerBoard:
    return {
        "checks": {},
        "values": {},
        "brown_last_checked": None,
        "brown_disabled": {},
        "chosen_this_turn": [],
        "slots": [None, None, None],
        "bonuses": empty_bonus_state(),
    }


def all_dice(overrides: dict[DieColor, DieRuntime] | None = None) -> dict[DieColor, DieRuntime]:
    overrides = overrides or {}
    return {c: overrides.get(c) or {"value": 1, "location": "available"} for c in ALL_DIE_COLORS}


def base_state(**overrides: Any) -> GameState:
    state: GameState = {
        "global_turn": 1,
        "phase": {"kind": "active", "player": 1, "round": 1},
        "boards": {1: empty_board(), 2: empty_board()},
        "dice": all_dice({"pink": {"value": 4, "location": "available"}}),
        "selection": None,
        "message": None,
        "plus1_active": None,
        "plus1_used_dice": empty_plus1_used_dice(),
        "joker_pending": None,
        "pending_bonuses": [],
        "bonus_resolution": None,
        "pink_choice": None,
        "pending_advance": None,
    }
    state.update(overrides)  # type: ignore[typeddict-item]
    return state
