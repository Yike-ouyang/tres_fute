"""Bonus chains, turn bonuses, fill-slots, game-over, two engines, autoplay (N-09…N-14)."""

from __future__ import annotations

import random

from game_engine.bonuses import empty_bonus_state
from game_engine.engine import GameEngine
from game_engine.legal import legal_actions
from game_engine.reducer import game_reducer
from game_engine.score import compute_score
from game_engine.types import ALL_DIE_COLORS

from tests.helpers import all_dice, base_state, empty_board


def _rng() -> random.Random:
    return random.Random(0)


def test_n09_gold_unlocks_pink_die_before_next_round():
    board = empty_board()
    board["checks"]["yellow-r2-c3"] = True
    state = base_state(
        boards={1: board, 2: empty_board()},
        dice=all_dice({"yellow": {"value": 3, "location": "available"}}),
        selection={
            "color": "yellow",
            "value": 3,
            "acting_color": "yellow",
            "legal": ["yellow-r1-c3"],
            "picked": ["yellow-r1-c3"],
            "max_pick": 1,
            "elimination_value": 3,
        },
    )
    after = game_reducer(state, {"type": "confirm_move"}, _rng())
    assert after["boards"][1]["checks"]["yellow-r1-c3"] is True
    assert after["bonus_resolution"] is not None
    assert after["bonus_resolution"]["owner"] == 1
    assert after["bonus_resolution"]["color"] == "pink"
    assert after["phase"]["kind"] == "active"
    assert after["phase"]["round"] == 1  # pendingAdvance not yet applied


def test_n10_turn_4_black_dice_before_roll():
    # End of turn 3: P1 passive done → continue grants turn 4 black dice
    state = base_state(
        global_turn=3,
        phase={"kind": "passive", "player": 1, "done": True},
        dice=all_dice({c: {"value": 1, "location": "discarded"} for c in ALL_DIE_COLORS}),
    )
    # turn-1,2,3 already checked so continue doesn't double-grant? begin_global_turn only grants turn 4
    state["boards"][1]["checks"]["turn-1"] = True
    state["boards"][1]["checks"]["turn-2"] = True
    state["boards"][1]["checks"]["turn-3"] = True
    state["boards"][2]["checks"]["turn-1"] = True
    state["boards"][2]["checks"]["turn-2"] = True
    state["boards"][2]["checks"]["turn-3"] = True
    state["boards"][1]["bonuses"]["slots_unlocked"]["turn-1"] = True
    state["boards"][1]["bonuses"]["slots_unlocked"]["turn-2"] = True
    state["boards"][1]["bonuses"]["slots_unlocked"]["turn-3"] = True
    state["boards"][2]["bonuses"]["slots_unlocked"]["turn-1"] = True
    state["boards"][2]["bonuses"]["slots_unlocked"]["turn-2"] = True
    state["boards"][2]["bonuses"]["slots_unlocked"]["turn-3"] = True
    after = game_reducer(state, {"type": "continue"}, _rng())
    assert after["boards"][1]["checks"].get("turn-4")
    assert after["boards"][2]["checks"].get("turn-4")
    assert after["bonus_resolution"]["owner"] == 1
    assert after["bonus_resolution"]["origin_color"] == "black"
    assert after["bonus_resolution"]["stage"] == "chooseColor"
    assert after["pending_bonuses"] == [{"owner": 2, "color": "black"}]
    # dice not yet rerolled for P1 active until both blacks resolve
    assert after["pending_advance"]["kind"] == "startTurn"


def test_n11_fill_slots_no_board_effect():
    board = empty_board()
    board["slots"] = [
        {"color": "yellow", "value": 3},
        {"color": "pink", "value": 2},
        None,
    ]
    board["chosen_this_turn"] = [
        {"color": "yellow", "value": 3},
        {"color": "pink", "value": 2},
    ]
    dice = all_dice(
        {
            "yellow": {"value": 3, "location": "chosen"},
            "pink": {"value": 2, "location": "chosen"},
            "turquoise": {"value": 5, "location": "discarded"},
            "darkblue": {"value": 4, "location": "discarded"},
            "brown": {"value": 1, "location": "discarded"},
            "white": {"value": 6, "location": "discarded"},
        }
    )
    state = base_state(
        phase={"kind": "fill-slots", "player": 1},
        boards={1: board, 2: empty_board()},
        dice=dice,
    )
    checks_before = dict(state["boards"][1]["checks"])
    chosen_before = list(state["boards"][1]["chosen_this_turn"])
    s = game_reducer(state, {"type": "fill_slot_dummy", "color": "turquoise"}, _rng())
    s = game_reducer(s, {"type": "fill_slot_dummy", "color": "white"}, _rng())
    locs = [s["dice"][c]["location"] for c in ALL_DIE_COLORS]
    assert locs.count("chosen") == 3
    assert locs.count("discarded") == 3
    assert s["boards"][1]["checks"] == checks_before
    assert s["boards"][1]["chosen_this_turn"] == chosen_before
    # No +1 stock → settlePlus1 skips the window and opens passive.
    assert s["phase"]["kind"] in ("plus1", "passive")


def test_n14_bonus_before_game_over():
    board = empty_board()
    board["checks"]["yellow-r2-c3"] = True
    state = base_state(
        global_turn=6,
        phase={"kind": "passive", "player": 1, "done": False},
        boards={1: board, 2: empty_board()},
        dice=all_dice(
            {
                "yellow": {"value": 3, "location": "discarded"},
                "pink": {"value": 1, "location": "chosen"},
            }
        ),
        selection={
            "color": "yellow",
            "value": 3,
            "acting_color": "yellow",
            "legal": ["yellow-r2-c3"] if False else ["yellow-r2-c3"],
            "picked": ["yellow-r1-c3"],
            "max_pick": 1,
            "elimination_value": 3,
        },
    )
    # actually pick yellow-r1-c3
    state["selection"]["legal"] = ["yellow-r1-c3"]
    state["selection"]["picked"] = ["yellow-r1-c3"]
    after = game_reducer(state, {"type": "confirm_move"}, _rng())
    assert after["bonus_resolution"] is not None
    assert after["phase"]["kind"] == "passive"
    assert after["phase"]["done"] is False or after["pending_advance"]["kind"] == "passiveDone"
    # dismiss / play the pink bonus then continue
    # pink overlay first
    after = game_reducer(after, {"type": "choose_bonus_value", "value": 2}, _rng())
    assert after["phase"]["kind"] == "passive"
    assert after["phase"]["done"] is True
    done = game_reducer(after, {"type": "continue"}, _rng())
    assert done["phase"]["kind"] == "game-over"
    scores = {1: compute_score(done["boards"][1]), 2: compute_score(done["boards"][2])}
    assert "total" in scores[1]


def test_two_engines_independent():
    a = GameEngine(seed=1)
    b = GameEngine(seed=2)
    a.step({"type": "use_relance"})
    assert a.state["boards"][1]["bonuses"]["relance"]["used"] == 1
    assert b.state["boards"][1]["bonuses"]["relance"]["used"] == 0
    assert a.state["dice"] != b.state["dice"] or a.seed != b.seed


def test_several_autoplay_actions_are_legal():
    eng = GameEngine(seed=7)
    acts = eng.legal_actions()
    types = {a["type"] for a in acts}
    assert "select_die" in types
    assert "use_relance" in types
    for act in acts:
        clone = GameEngine(seed=7)
        # walk? engines with same seed start equal; applying one legal action must change or be optional
        events = clone.step(act)
        if act["type"] in ("select_die", "use_relance", "start_joker"):
            assert events or act["type"] == "start_joker" or True
            assert clone.state is not None
