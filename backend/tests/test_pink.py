"""REGLES N-01…N-04, N-13, N-15 — rose and joker."""

from __future__ import annotations

import random

from game_engine.bonuses import empty_bonus_state
from game_engine.engine import GameEngine
from game_engine.reducer import empty_board, game_reducer
from game_engine.rules import pink_value
from game_engine.score import compute_score

from tests.helpers import all_dice, base_state, empty_board as helper_empty


def _rng() -> random.Random:
    return random.Random(0)


def _pink_sel(value: int, dest: str = "pink-cell-1", elimination: int | None = None):
    return {
        "color": "pink",
        "value": value,
        "acting_color": "pink",
        "legal": [dest],
        "picked": [dest],
        "max_pick": 1,
        "elimination_value": elimination if elimination is not None else value,
    }


def test_pink_value_ceil_half():
    assert [pink_value(v) for v in range(1, 7)] == [1, 1, 2, 2, 3, 3]


def test_n01_first_pink_even():
    after = game_reducer(base_state(selection=_pink_sel(4)), {"type": "confirm_move"}, _rng())
    assert after["boards"][1]["values"]["pink-cell-1"] == 2
    assert after["pink_choice"] is None
    assert after["boards"][1]["bonuses"] == empty_bonus_state()
    assert compute_score(after["boards"][1])["pink"] == 2


def test_n02_first_pink_odd():
    after = game_reducer(
        base_state(
            dice=all_dice({"pink": {"value": 5, "location": "available"}}),
            selection=_pink_sel(5),
        ),
        {"type": "confirm_move"},
        _rng(),
    )
    assert after["boards"][1]["values"]["pink-cell-1"] == 3
    assert after["pink_choice"] is None
    assert compute_score(after["boards"][1])["pink"] == 3


def test_n03_joker_then_pink_cell_2():
    board = helper_empty()
    board["values"] = {"pink-cell-1": 2}
    board["bonuses"] = {**empty_bonus_state(), "joker": {"unlocked": 1, "used": 0}}
    state = base_state(
        boards={1: board, 2: helper_empty()},
        dice=all_dice({"pink": {"value": 6, "location": "available"}}),
    )
    rng = _rng()
    state = game_reducer(state, {"type": "start_joker", "token_index": 0}, rng)
    assert state["joker_pending"] == {"token_index": None, "value": None}
    state = game_reducer(state, {"type": "set_joker_value", "value": 3}, rng)
    assert state["joker_pending"] == {"token_index": 0, "value": 3}
    state = game_reducer(state, {"type": "select_die", "color": "pink"}, rng)
    assert state["selection"]["value"] == 3
    assert state["selection"]["elimination_value"] == 6
    assert state["boards"][1]["bonuses"]["joker"]["used"] == 1
    assert state["boards"][1]["bonuses"]["joker"]["used_tokens"] == [0]
    state = game_reducer(state, {"type": "confirm_move"}, rng)
    assert "pink-cell-2" not in state["boards"][1]["values"]
    assert state["pink_choice"]["position"] == 2
    assert state["pink_choice"]["effective_value"] == 3
    assert state["pink_choice"]["multiplier"] == 1

    points = game_reducer(state, {"type": "choose_pink_option", "option": "points"}, rng)
    assert points["boards"][1]["values"]["pink-cell-2"] == 3
    assert points["boards"][1]["bonuses"]["relance"]["unlocked"] == 0

    bonus = game_reducer(state, {"type": "choose_pink_option", "option": "bonus"}, rng)
    assert bonus["boards"][1]["values"]["pink-cell-2"] == 2
    assert bonus["boards"][1]["bonuses"]["relance"]["unlocked"] == 1


def test_n04_joker_elimination_uses_physical():
    board = helper_empty()
    board["bonuses"] = {**empty_bonus_state(), "joker": {"unlocked": 1, "used": 1}}
    state = base_state(
        boards={1: board, 2: helper_empty()},
        dice=all_dice(
            {
                "pink": {"value": 6, "location": "available", "joker_value": 3},
                "yellow": {"value": 5, "location": "available"},
                "turquoise": {"value": 2, "location": "available"},
            }
        ),
        selection=_pink_sel(3, "pink-cell-1", elimination=6),
    )
    after = game_reducer(state, {"type": "confirm_move"}, _rng())
    assert after["boards"][1]["values"]["pink-cell-1"] == 2
    assert after["dice"]["pink"]["location"] == "chosen"
    assert after["dice"]["turquoise"]["location"] == "discarded"
    # Physical 6 eliminates 5 (TS / DES-003). REGLES N-04's "jaune reste" would
    # only hold if elimination used the joker 3; the engine does not.
    assert after["dice"]["yellow"]["location"] == "discarded"


def test_n13_pink_fox_option():
    board = helper_empty()
    board["values"] = {f"pink-cell-{i}": 1 for i in range(1, 9)}
    state = base_state(boards={1: board, 2: helper_empty()}, selection=_pink_sel(4, "pink-cell-9"))
    opened = game_reducer(state, {"type": "confirm_move"}, _rng())
    assert opened["pink_choice"]["position"] == 9
    fox_before = compute_score(opened["boards"][1])["fox_count"]

    points = game_reducer(opened, {"type": "choose_pink_option", "option": "points"}, _rng())
    assert points["boards"][1]["values"]["pink-cell-9"] == 12
    assert not points["boards"][1]["bonuses"]["slots_unlocked"].get("pink-9")
    assert compute_score(points["boards"][1])["fox_count"] == fox_before

    bonus = game_reducer(opened, {"type": "choose_pink_option", "option": "bonus"}, _rng())
    assert bonus["boards"][1]["values"]["pink-cell-9"] == 2
    assert bonus["boards"][1]["bonuses"]["slots_unlocked"]["pink-9"] is True
    assert compute_score(bonus["boards"][1])["fox_count"] == fox_before + 1
    assert bonus["bonus_resolution"] is None


def test_n15_pink_score_no_second_division():
    board = helper_empty()
    board["values"] = {"pink-cell-1": 3, "pink-cell-2": 4}
    assert compute_score(board)["pink"] == 7
    assert compute_score(board)["pink"] != pink_value(3)


def test_pink_bonus_die_writes_cell_1():
    after = game_reducer(
        base_state(
            bonus_resolution={
                "owner": 1,
                "origin_color": "pink",
                "color": "pink",
                "stage": "chooseValue",
                "value": None,
            }
        ),
        {"type": "choose_bonus_value", "value": 5},
        _rng(),
    )
    assert after["boards"][1]["values"]["pink-cell-1"] == 3
    assert after["pink_choice"] is None
    assert after["bonus_resolution"] is None


def test_illegal_confirm_is_noop():
    state = base_state()
    after = game_reducer(state, {"type": "confirm_move"}, _rng())
    assert after is state


def test_engine_step_illegal_does_not_consume_rng():
    eng = GameEngine(seed=42)
    before = eng.rng.getstate()
    events = eng.step({"type": "confirm_move"})
    assert events == []
    assert eng.rng.getstate() == before
