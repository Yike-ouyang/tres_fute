"""Règles joker (valeur au choix, tout contexte) et portée des +1 (RULES 1.2)."""

from __future__ import annotations

import random

from game_engine.bonuses import empty_bonus_state
from game_engine.legal import current_decision, legal_actions
from game_engine.reducer import game_reducer
from tests.helpers import all_dice, base_state, empty_board


def _rng() -> random.Random:
    return random.Random(0)


def _board_with_joker(unlocked: int = 5, used: int = 0, used_tokens=None):
    board = empty_board()
    board["bonuses"] = {
        **empty_bonus_state(),
        "joker": {"unlocked": unlocked, "used": used, "used_tokens": list(used_tokens or [])},
    }
    return board


def _set_values(state) -> set[int]:
    return {a["value"] for a in legal_actions(state) if a["type"] == "set_joker_value"}


def test_joker_value_is_chosen_and_out_of_order() -> None:
    board = _board_with_joker(unlocked=5)
    state = base_state(
        boards={1: board, 2: empty_board()},
        dice=all_dice({"yellow": {"value": 1, "location": "available"}}),
    )
    # Starting a joker always asks for a value first.
    state = game_reducer(state, {"type": "start_joker"}, _rng())
    assert state["joker_pending"] == {"token_index": None, "value": None}
    assert _set_values(state) == {1, 2, 3, 4, 5, 6}  # numbered 3-6 + wild

    # Pick 4 first (out of order): consumes the token whose printed value is 4.
    state = game_reducer(state, {"type": "set_joker_value", "value": 4}, _rng())
    assert state["joker_pending"] == {"token_index": 1, "value": 4}
    state = game_reducer(state, {"type": "select_die", "color": "yellow"}, _rng())
    assert state["boards"][1]["bonuses"]["joker"]["used"] == 1
    assert state["boards"][1]["bonuses"]["joker"]["used_tokens"] == [1]
    assert state["selection"]["value"] == 4


def test_joker_value_3_after_4() -> None:
    # unlocked=4: tokens 3,4,5,6 only (no wild).
    board = _board_with_joker(unlocked=4, used=1, used_tokens=[1])  # "4" consumed
    state = base_state(
        boards={1: board, 2: empty_board()},
        dice=all_dice({"yellow": {"value": 1, "location": "available"}}),
    )
    state = game_reducer(state, {"type": "start_joker"}, _rng())
    assert _set_values(state) == {3, 5, 6}  # 4 no longer offered
    state = game_reducer(state, {"type": "set_joker_value", "value": 3}, _rng())
    assert state["joker_pending"]["token_index"] == 0


def test_joker_wild_can_reoffer_value() -> None:
    # With a wild token unlocked, a consumed numbered value is still selectable.
    board = _board_with_joker(unlocked=5, used=1, used_tokens=[1])
    state = base_state(
        boards={1: board, 2: empty_board()},
        dice=all_dice({"yellow": {"value": 1, "location": "available"}}),
    )
    state = game_reducer(state, {"type": "start_joker"}, _rng())
    assert _set_values(state) == {1, 2, 3, 4, 5, 6}
    # Choosing 4 must fall back to the wild token (index 4), not the consumed one.
    state = game_reducer(state, {"type": "set_joker_value", "value": 4}, _rng())
    assert state["joker_pending"]["token_index"] == 4


def test_joker_usable_in_passive() -> None:
    board = _board_with_joker(unlocked=1)
    state = base_state(
        boards={1: board, 2: empty_board()},
        dice=all_dice({"yellow": {"value": 1, "location": "discarded"}}),
        phase={"kind": "passive", "player": 1, "done": False},
    )
    actions = legal_actions(state)
    assert any(a["type"] == "start_joker" for a in actions)
    assert any(a["type"] == "select_die" and a["color"] == "yellow" for a in actions)

    state = game_reducer(state, {"type": "start_joker"}, _rng())
    assert current_decision(state)["actor"] == 1
    state = game_reducer(state, {"type": "set_joker_value", "value": 3}, _rng())
    state = game_reducer(state, {"type": "select_die", "color": "yellow"}, _rng())
    assert state["dice"]["yellow"]["joker_value"] == 3
    assert state["boards"][1]["bonuses"]["joker"]["used"] == 1


def test_joker_usable_in_plus1() -> None:
    board = _board_with_joker(unlocked=1)
    state = base_state(
        boards={1: board, 2: empty_board()},
        dice=all_dice({"yellow": {"value": 1, "location": "chosen"}}),
        phase={"kind": "plus1", "order": [1, 2], "current": 0},
        plus1_active=1,
    )
    actions = legal_actions(state)
    assert any(a["type"] == "start_joker" for a in actions)
    state = game_reducer(state, {"type": "start_joker"}, _rng())
    state = game_reducer(state, {"type": "set_joker_value", "value": 3}, _rng())
    state = game_reducer(state, {"type": "select_die", "color": "yellow"}, _rng())
    assert state["dice"]["yellow"]["joker_value"] == 3


def test_joker_usable_in_fill_slots() -> None:
    board = _board_with_joker(unlocked=1)
    state = base_state(
        boards={1: board, 2: empty_board()},
        dice=all_dice({"yellow": {"value": 1, "location": "discarded"}}),
        phase={"kind": "fill-slots", "player": 1},
    )
    actions = legal_actions(state)
    assert any(a["type"] == "fill_slot_dummy" for a in actions)
    assert any(a["type"] == "start_joker" for a in actions)

    state = game_reducer(state, {"type": "start_joker"}, _rng())
    state = game_reducer(state, {"type": "set_joker_value", "value": 3}, _rng())
    state = game_reducer(state, {"type": "select_die", "color": "yellow"}, _rng())
    assert state["dice"]["yellow"]["joker_value"] == 3
    assert state["boards"][1]["bonuses"]["joker"]["used"] == 1
    state = game_reducer(state, {"type": "fill_slot_dummy", "color": "yellow"}, _rng())
    assert state["dice"]["yellow"]["location"] == "chosen"


def test_plus1_scope_is_chosen_and_discarded_only() -> None:
    state = base_state(
        boards={1: empty_board(), 2: empty_board()},
        dice=all_dice(
            {
                "yellow": {"value": 1, "location": "chosen"},
                "turquoise": {"value": 1, "location": "discarded"},
                "brown": {"value": 1, "location": "available"},
            }
        ),
        phase={"kind": "plus1", "order": [1, 2], "current": 0},
        plus1_active=1,
    )
    colors = {a["color"] for a in legal_actions(state) if a["type"] == "select_die"}
    assert "yellow" in colors  # active player's chosen die
    assert "turquoise" in colors  # grey zone
    assert "brown" not in colors  # available dice are excluded from +1


def test_catalogue_exposes_joker_in_fill_slots() -> None:
    from rl_env_2.actions import build_legal_decisions, label

    board = _board_with_joker(unlocked=1)
    state = base_state(
        boards={1: board, 2: empty_board()},
        dice=all_dice({"yellow": {"value": 1, "location": "discarded"}}),
        phase={"kind": "fill-slots", "player": 1},
    )
    labels = {label(d.action_id) for d in build_legal_decisions(state)}
    assert "utility:start_joker" in labels
    assert any(name.startswith("fill_slot:") for name in labels)
