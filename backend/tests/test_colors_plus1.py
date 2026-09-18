"""Turquoise groups, blue branches, brown skips, counters, +1 chain (N-05…N-08, N-12)."""

from __future__ import annotations

import random

from game_engine.bonuses import TOTAL_JOKERS, TOTAL_PLUS1, TOTAL_RELANCE, apply_unlocks, empty_bonus_state
from game_engine.legal import legal_actions
from game_engine.reducer import game_reducer
from game_engine.rules import legal_destinations
from game_engine.score import compute_score

from tests.helpers import all_dice, base_state, empty_board


def _rng() -> random.Random:
    return random.Random(0)


def test_counter_tracks_are_length_7():
    assert TOTAL_RELANCE == 7
    assert TOTAL_JOKERS == 7
    assert TOTAL_PLUS1 == 7


def test_seventh_relance_unlocks_fox():
    board = empty_board()
    board["bonuses"] = {**empty_bonus_state(), "relance": {"unlocked": 7, "used": 0}}
    next_board, die_bonuses = apply_unlocks(board)
    assert next_board["bonuses"]["slots_unlocked"].get("counter-relance-all") is True
    assert die_bonuses == []
    assert compute_score(next_board)["fox_count"] == 1


def test_brown_die_at_7_jokers_not_4():
    board = empty_board()
    board["bonuses"] = {**empty_bonus_state(), "joker": {"unlocked": 4, "used": 0}}
    nxt, dice = apply_unlocks(board)
    assert not nxt["bonuses"]["slots_unlocked"].get("counter-joker-all")
    assert dice == []
    board["bonuses"] = {**empty_bonus_state(), "joker": {"unlocked": 7, "used": 0}}
    nxt, dice = apply_unlocks(board)
    assert nxt["bonuses"]["slots_unlocked"]["counter-joker-all"] is True
    assert dice == ["brown"]


def test_pink_die_at_7_plus1():
    board = empty_board()
    board["bonuses"] = {**empty_bonus_state(), "plus1": {"unlocked": 7, "used": 0}}
    nxt, dice = apply_unlocks(board)
    assert nxt["bonuses"]["slots_unlocked"]["counter-plus1-all"] is True
    assert dice == ["pink"]


def test_n05_turquoise_active_counts_chosen_this_turn():
    board = empty_board()
    board["chosen_this_turn"] = [{"color": "yellow", "value": 4}]
    ctx = {
        "mode": "active",
        "board": board,
        "dice": all_dice({"turquoise": {"value": 4, "location": "available"}}),
        "round": 2,
        "selected_color": "turquoise",
    }
    assert legal_destinations("turquoise", 4, ctx)["max_pick"] == 2
    assert len(legal_destinations("turquoise", 4, ctx)["legal"]) == 5


def test_n05_turquoise_passive_same_discarded_group():
    board = empty_board()
    ctx = {
        "mode": "passive",
        "board": board,
        "dice": all_dice(
            {
                "turquoise": {"value": 4, "location": "discarded"},
                "pink": {"value": 4, "location": "discarded"},
                "brown": {"value": 3, "location": "discarded"},
            }
        ),
        "round": 0,
        "selected_color": "turquoise",
    }
    assert legal_destinations("turquoise", 4, ctx)["max_pick"] == 2


def test_n05_turquoise_plus1_counts_chosen_group_only():
    board = empty_board()
    ctx = {
        "mode": "passive",
        "board": board,
        "dice": all_dice(
            {
                "turquoise": {"value": 4, "location": "chosen"},
                "yellow": {"value": 4, "location": "chosen"},
                "pink": {"value": 4, "location": "discarded"},
                "brown": {"value": 4, "location": "discarded"},
            }
        ),
        "round": 0,
        "selected_color": "turquoise",
    }
    assert legal_destinations("turquoise", 4, ctx)["max_pick"] == 2


def test_n06_blue_uses_discarded_white_partner():
    ctx = {
        "mode": "active",
        "board": empty_board(),
        "dice": all_dice(
            {
                "darkblue": {"value": 3, "location": "chosen"},
                "white": {"value": 5, "location": "discarded"},
            }
        ),
        "round": 2,
        "selected_color": "darkblue",
    }
    legal = legal_destinations("darkblue", 3, ctx)["legal"]
    assert "blue-cell-8" in legal
    assert "blue-cell-6" not in legal


def test_n07_blue_wildcard_7_restarts_branch():
    board = empty_board()
    board["values"] = {"blue-cell-8": 8}
    from game_engine.rules import blue_bonus_options
    from game_engine.score import compute_score as score

    opts = blue_bonus_options(board)
    assert any(o["cell_id"] == "blue-cell-9" and o["value"] == 7 for o in opts)
    board["values"]["blue-cell-9"] = 7
    # two cells on the right branch → 6 progression points
    assert score(board)["blue"] == 6
    opts2 = blue_bonus_options(board)
    assert any(o["cell_id"] == "blue-cell-10" and o["value"] == 8 for o in opts2)
    assert any(o["cell_id"] == "blue-cell-10" and o["value"] == 7 for o in opts2)


def test_blue_bonus_stepped_value_allowed_up_to_12():
    from game_engine.rules import blue_bonus_options

    # ref = 11 on the right branch: the stepped value 12 is still legal alongside 7.
    board = empty_board()
    board["values"] = {f"blue-cell-{p}": p for p in range(8, 12)}  # 8,9,10,11
    opts = blue_bonus_options(board)
    assert {"cell_id": "blue-cell-12", "value": 12} in opts
    assert {"cell_id": "blue-cell-12", "value": 7} in opts


def test_blue_bonus_never_exceeds_12():
    from game_engine.rules import blue_bonus_options

    # ref = 12 on the right branch: 13 is impossible (a sum is at most 12), only 7.
    board = empty_board()
    board["values"] = {f"blue-cell-{p}": p for p in range(8, 13)}  # 8..12
    opts = blue_bonus_options(board)
    assert {"cell_id": "blue-cell-13", "value": 7} in opts
    assert all(o["value"] <= 12 for o in opts)
    assert not any(o["cell_id"] == "blue-cell-13" and o["value"] == 13 for o in opts)


def test_blue_bonus_options_are_within_1_to_12():
    from game_engine.rules import blue_bonus_options

    boards = []
    for filled in range(0, 7):  # right branch filled with increasing values
        b = empty_board()
        b["values"] = {f"blue-cell-{p}": p for p in range(8, 8 + filled)}
        boards.append(b)
    for b in boards:
        for o in blue_bonus_options(b):
            assert 1 <= o["value"] <= 12


def test_n08_brown_skipped_cells():
    state = base_state(
        dice=all_dice({"brown": {"value": 4, "location": "available"}}),
        selection={
            "color": "brown",
            "value": 4,
            "acting_color": "brown",
            "legal": ["brown-cell-4"],
            "picked": ["brown-cell-4"],
            "max_pick": 1,
            "elimination_value": 4,
        },
    )
    after = game_reducer(state, {"type": "confirm_move"}, _rng())
    assert after["boards"][1]["checks"]["brown-cell-4"] is True
    assert after["boards"][1]["brown_last_checked"] == 4
    assert after["boards"][1]["brown_disabled"]["brown-cell-1"] is True
    assert after["boards"][1]["brown_disabled"]["brown-cell-2"] is True
    assert after["boards"][1]["brown_disabled"]["brown-cell-3"] is True
    assert compute_score(after["boards"][1])["brown"] == 3


def test_plus1_chains_same_actor():
    board = empty_board()
    board["bonuses"] = {**empty_bonus_state(), "plus1": {"unlocked": 2, "used": 0}}
    board2 = empty_board()
    board2["bonuses"] = {**empty_bonus_state(), "plus1": {"unlocked": 1, "used": 0}}
    state = base_state(
        phase={"kind": "plus1", "order": [1, 2], "current": 0},
        boards={1: board, 2: board2},
        dice=all_dice(
            {
                "yellow": {"value": 6, "location": "discarded"},
                "brown": {"value": 5, "location": "discarded"},
            }
        ),
        selection={
            "color": "yellow",
            "value": 6,
            "acting_color": "yellow",
            "legal": ["yellow-r1-c6"],
            "picked": ["yellow-r1-c6"],
            "max_pick": 1,
            "elimination_value": 6,
        },
        plus1_active=1,
    )
    after = game_reducer(state, {"type": "confirm_move"}, _rng())
    assert after["boards"][1]["checks"]["yellow-r1-c6"] is True
    assert after["boards"][1]["bonuses"]["plus1"]["used"] == 1
    assert after["plus1_used_dice"][1] == ["yellow"]
    assert after["plus1_active"] is None
    assert after["phase"] == {"kind": "plus1", "order": [1, 2], "current": 0}
    acts = legal_actions(after)
    assert any(a["type"] == "begin_plus1" for a in acts)
    assert any(a["type"] == "skip_plus1" for a in acts)

    state = game_reducer(after, {"type": "begin_plus1"}, _rng())
    rejected = game_reducer(state, {"type": "select_die", "color": "yellow"}, _rng())
    assert rejected is state
    allowed = game_reducer(state, {"type": "select_die", "color": "brown"}, _rng())
    assert allowed["selection"]["color"] == "brown"

    # other player may still target yellow
    skipped = game_reducer(after, {"type": "skip_plus1"}, _rng())
    skipped = game_reducer(skipped, {"type": "begin_plus1"}, _rng())
    assert skipped["plus1_active"] == 2
    picked = game_reducer(skipped, {"type": "select_die", "color": "yellow"}, _rng())
    assert picked["selection"]["color"] == "yellow"


def test_n12_passive_fallback_to_chosen():
    # discarded dice have no legal yellow/turquoise/etc. — force chosen yellow 6
    dice = all_dice(
        {
            "yellow": {"value": 6, "location": "chosen"},
            "turquoise": {"value": 1, "location": "discarded"},
            "darkblue": {"value": 1, "location": "discarded"},
            "brown": {"value": 2, "location": "discarded"},
            "pink": {"value": 1, "location": "discarded"},
            "white": {"value": 1, "location": "discarded"},
        }
    )
    # fill turquoise col 1 so discarded 1s aren't turquoise-playable? white 1 and turq 1
    # would still have turquoise col 1 free. Fill all turquoise-*-c1.
    board = empty_board()
    for r in range(1, 6):
        board["checks"][f"turquoise-r{r}-c1"] = True
    # yellow-r3-c1 (passive 1) already need to block discarded 1s for yellow
    board["checks"]["yellow-r3-c1"] = True
    # brown 2: brown-cell-2 is 5 printed, brown 2 printed is cell 5 — discarded brown 2 can play cell 5.
    # Block all brown cells matching discarded values... easier: fill pink and make brown last checked 12
    board["brown_last_checked"] = 12
    for i in range(1, 13):
        board["checks"][f"brown-cell-{i}"] = True
        board["values"][f"pink-cell-{i}"] = 1
    # blue: discarded 1s don't play blue unless sum is legal. darkblue 1 + white 1 = 2, left wants 6. not legal.
    state = base_state(
        phase={"kind": "passive", "player": 1, "done": False},
        boards={1: board, 2: empty_board()},
        dice=dice,
    )
    acts = legal_actions(state)
    assert all(a.get("color") != "turquoise" for a in acts if a["type"] == "select_die")
    colors = [a["color"] for a in acts if a["type"] == "select_die"]
    assert colors == ["yellow"]
    picked = game_reducer(state, {"type": "select_die", "color": "yellow"}, _rng())
    # passive yellow 6 → yellow-r1-c6
    assert picked["selection"]["legal"] == ["yellow-r1-c6"]
    assert picked["message"]  # fallback message
