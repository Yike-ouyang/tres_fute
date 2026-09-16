"""HeuristicPolicy: prioritised preferences, fallbacks, reproducibility, full games."""

from __future__ import annotations

import copy
import random

import pytest

from game_engine.engine import GameEngine
from game_engine.legal import legal_actions
from game_engine.reducer import game_reducer
from game_engine.rules import turquoise_companion_count
from simulation.policy import (
    BLUE_RIGHT_POSITIONS,
    HeuristicPolicy,
    blue_on_right,
    brown_position_avoided,
    nombre_retires,
    remaining_after,
    run_autoplay,
)

from tests.helpers import all_dice, base_state, empty_board


class _SeqRng(random.Random):
    """Deterministic RNG: fixed ``random()`` sequence, first-element choice/sample."""

    def __init__(self, values: list[float]) -> None:
        super().__init__(0)
        self._values = list(values)
        self.calls = 0

    def random(self) -> float:  # type: ignore[override]
        value = self._values[self.calls % len(self._values)]
        self.calls += 1
        return value

    def choice(self, seq):  # type: ignore[override]
        return list(seq)[0]

    def sample(self, seq, k):  # type: ignore[override]
        return list(seq)[:k]


def _active(dice, round_n: int = 1, boards=None):
    return base_state(
        phase={"kind": "active", "player": 1, "round": round_n},
        dice=dice,
        boards=boards or {1: empty_board(), 2: empty_board()},
    )


# --------------------------------------------------------------------- Rule 1

def test_nombre_retires_example_from_spec():
    # values 1,2,4,4,5,6: choosing a 4 removes the chosen 4, the 1 and the 2 → 3.
    dice = all_dice(
        {
            "yellow": {"value": 1, "location": "available"},
            "turquoise": {"value": 2, "location": "available"},
            "darkblue": {"value": 4, "location": "available"},
            "brown": {"value": 4, "location": "available"},
            "pink": {"value": 5, "location": "available"},
            "white": {"value": 6, "location": "available"},
        }
    )
    assert nombre_retires(dice, "darkblue") == 3
    assert nombre_retires(dice, "brown") == 3
    assert nombre_retires(dice, "white") == 6
    assert nombre_retires(dice, "yellow") == 1


def test_round1_keeps_at_most_three_removed():
    dice = all_dice(
        {
            "yellow": {"value": 1, "location": "available"},
            "turquoise": {"value": 2, "location": "available"},
            "darkblue": {"value": 3, "location": "available"},
            "brown": {"value": 4, "location": "available"},
            "white": {"value": 4, "location": "available"},
            "pink": {"value": 5, "location": "available"},
        }
    )
    policy = HeuristicPolicy(seed=0)
    for _ in range(20):
        action = policy.choisir_action(_active(dice, round_n=1))
        assert action is not None and action["type"] == "select_die"
        assert nombre_retires(dice, action["color"]) <= 3
        assert action["color"] not in ("brown", "white", "pink")


def test_round1_falls_back_when_every_move_removes_four_or_more():
    dice = all_dice(
        {
            "yellow": {"value": 5, "location": "available"},
            "turquoise": {"value": 5, "location": "available"},
            "darkblue": {"value": 5, "location": "available"},
            "brown": {"value": 5, "location": "available"},
            "pink": {"value": 5, "location": "available"},
            "white": {"value": 5, "location": "available"},
        }
    )
    state = _active(dice, round_n=1)
    cands = [
        {"die": c, "acting": c, "legal": ["yellow-r1-c5"], "max_pick": 1} for c in ("yellow", "turquoise")
    ]
    assert HeuristicPolicy(seed=0)._pref_first_round(state, cands) == cands


# --------------------------------------------------------------------- Rule 2/3

def test_round2_leaves_at_least_one_die():
    dice = all_dice(
        {
            "yellow": {"value": 6, "location": "available"},
            "turquoise": {"value": 1, "location": "available"},
            "darkblue": {"value": 1, "location": "available"},
            "brown": {"value": 1, "location": "available"},
            "pink": {"value": 1, "location": "available"},
            "white": {"value": 1, "location": "available"},
        }
    )
    state = _active(dice, round_n=2)
    cands = [{"die": c, "acting": c, "legal": ["x"], "max_pick": 1} for c in dice]
    kept = HeuristicPolicy(seed=0)._pref_second_round(state, cands)
    assert "yellow" not in {c["die"] for c in kept}
    assert remaining_after(dice, "turquoise")  # sanity


def test_round2_then_prefers_keeping_rose_white_yellow():
    # brown=5 eliminates all red dice and only darkblue survives → no red left.
    dice = all_dice(
        {
            "yellow": {"value": 3, "location": "available"},
            "turquoise": {"value": 1, "location": "available"},
            "darkblue": {"value": 6, "location": "available"},
            "brown": {"value": 5, "location": "available"},
            "pink": {"value": 3, "location": "available"},
            "white": {"value": 3, "location": "available"},
        }
    )
    state = _active(dice, round_n=2)
    cands = [{"die": c, "acting": c, "legal": ["x"], "max_pick": 1} for c in dice]
    kept = HeuristicPolicy(seed=0)._pref_second_round(state, cands)
    dies = {c["die"] for c in kept}
    assert dies == {"yellow", "turquoise", "pink", "white"}  # darkblue (0 left) and brown (no red) dropped


def test_round2_falls_back_when_no_choice_keeps_a_die():
    dice = all_dice({c: {"value": 6, "location": "available"} for c in all_dice()})
    state = _active(dice, round_n=2)
    cands = [{"die": c, "acting": c, "legal": ["x"], "max_pick": 1} for c in dice]
    assert HeuristicPolicy(seed=0)._pref_second_round(state, cands) == cands


# --------------------------------------------------------------------- Rule 4

def test_brown_position_is_not_printed_value():
    assert brown_position_avoided("brown-cell-4") is True
    assert brown_position_avoided("brown-cell-5") is True
    assert brown_position_avoided("brown-cell-6") is True
    # printed value 4 also appears at position 7 (grey square is not a destination cell)
    assert brown_position_avoided("brown-cell-7") is False
    assert brown_position_avoided("brown-cell-3") is False
    assert brown_position_avoided("yellow-r1-c4") is False


def test_brown_destination_prefers_non_avoided_positions():
    policy = HeuristicPolicy(seed=0)
    cand = {
        "die": "brown",
        "acting": "brown",
        "legal": ["brown-cell-4", "brown-cell-7", "brown-cell-12"],
        "max_pick": 1,
    }
    for _ in range(10):
        assert policy._plan_destinations(_active(all_dice()), cand)[0] in ("brown-cell-7", "brown-cell-12")


def test_brown_falls_back_to_avoided_when_no_alternative():
    policy = HeuristicPolicy(seed=0)
    only_avoided = [{"die": "brown", "acting": "brown", "legal": ["brown-cell-4"], "max_pick": 1}]
    assert policy._pref_brown(only_avoided) == only_avoided


# --------------------------------------------------------------------- Rule 5

def test_blue_branch_positions():
    assert blue_on_right("blue-cell-8") is True
    assert blue_on_right("blue-cell-13") is True
    assert blue_on_right("blue-cell-6") is False
    assert blue_on_right("blue-cell-7") is False
    assert BLUE_RIGHT_POSITIONS == (8, 9, 10, 11, 12, 13)


def test_blue_prefers_right_branch_destination():
    policy = HeuristicPolicy(seed=0)
    cand = {"die": "darkblue", "acting": "darkblue", "legal": ["blue-cell-6", "blue-cell-8"], "max_pick": 1}
    for _ in range(10):
        assert policy._plan_destinations(_active(all_dice()), cand)[0] == "blue-cell-8"


def test_blue_falls_back_to_left_when_only_left():
    policy = HeuristicPolicy(seed=0)
    only_left = [{"die": "darkblue", "acting": "darkblue", "legal": ["blue-cell-6"], "max_pick": 1}]
    assert policy._pref_blue(only_left) == only_left


# --------------------------------------------------------------------- Rule 3 / white

def test_white_is_evaluated_as_brown_and_blue():
    dice = all_dice(
        {
            "white": {"value": 4, "location": "available"},
            "darkblue": {"value": 3, "location": "available"},
        }
    )
    state = _active(dice, round_n=3)
    policy = HeuristicPolicy(seed=0)
    cands = policy._candidates(state, ["white"])
    acting = {c["acting"] for c in cands}
    assert {"brown", "darkblue", "yellow", "turquoise", "pink"} <= acting


def test_white_plan_keeps_a_consistent_acting_colour():
    dice = all_dice(
        {
            "white": {"value": 4, "location": "available"},
            "darkblue": {"value": 3, "location": "available"},
        }
    )
    state = _active(dice, round_n=3)

    forced_family = HeuristicPolicy(seed=0)
    forced_family.rng = _SeqRng([0.5])
    action = forced_family._commit_die(state, [{"type": "select_die", "color": "white"}])
    assert action == {"type": "select_die", "color": "white"}
    assert forced_family._plan["acting"] in ("brown", "darkblue")

    forced_others = HeuristicPolicy(seed=0)
    forced_others.rng = _SeqRng([0.9])
    forced_others._commit_die(state, [{"type": "select_die", "color": "white"}])
    assert forced_others._plan["acting"] in ("yellow", "pink")  # turquoise dropped, no companion


# --------------------------------------------------------------------- Rule 6 (75 %)

def test_maroon_blue_draw_uses_controlled_generator():
    policy = HeuristicPolicy(seed=0)
    cands = [{"acting": "brown"}, {"acting": "yellow"}]

    policy.rng = _SeqRng([0.5])
    family, drew = policy._pref_maroon_blue(cands)
    assert drew is True and family == [cands[0]]

    policy.rng = _SeqRng([0.9])
    others, drew = policy._pref_maroon_blue(cands)
    assert drew is False and others == [cands[1]]


def test_maroon_blue_draw_is_single_and_only_when_both_families():
    policy = HeuristicPolicy(seed=0)
    rng = _SeqRng([0.5, 0.9])
    policy.rng = rng
    policy._pref_maroon_blue([{"acting": "brown"}, {"acting": "yellow"}])
    assert rng.calls == 1

    rng.calls = 0
    policy._pref_maroon_blue([{"acting": "brown"}, {"acting": "darkblue"}])  # family only
    assert rng.calls == 0
    rng.calls = 0
    policy._pref_maroon_blue([{"acting": "yellow"}, {"acting": "pink"}])  # others only
    assert rng.calls == 0


def test_maroon_blue_probability_is_75_percent_not_three_in_four():
    policy = HeuristicPolicy(seed=123)
    cands = [{"acting": "brown"}, {"acting": "yellow"}]
    draws = 4000
    family = sum(1 for _ in range(draws) if policy._pref_maroon_blue(cands)[1])
    ratio = family / draws
    assert 0.72 < ratio < 0.78


# --------------------------------------------------------------------- Rule 7 (pink)

def test_pink_first_cell_applies_halving_without_bonus():
    state = base_state(
        dice=all_dice({"pink": {"value": 4, "location": "available"}}),
        selection={
            "color": "pink",
            "value": 4,
            "acting_color": "pink",
            "legal": ["pink-cell-1"],
            "picked": ["pink-cell-1"],
            "max_pick": 1,
            "elimination_value": 4,
        },
    )
    engine = GameEngine(seed=0, state=copy.deepcopy(state))
    policy = HeuristicPolicy(seed=0)
    action = policy.choisir_action(engine)
    assert action == {"type": "confirm_move"}
    engine.step(action)
    assert engine.state["boards"][1]["values"]["pink-cell-1"] == 2
    assert engine.state["pink_choice"] is None


def test_pink_choice_always_takes_bonus():
    policy = HeuristicPolicy(seed=0)
    legal = [
        {"type": "choose_pink_option", "option": "points"},
        {"type": "choose_pink_option", "option": "bonus"},
    ]
    assert policy._handle_pink_choice(legal) == {"type": "choose_pink_option", "option": "bonus"}
    assert policy.choisir_action(base_state(pink_choice={
        "owner": 1,
        "cell_id": "pink-cell-3",
        "position": 3,
        "effective_value": 6,
        "multiplier": 2,
        "bonus_slot_id": "pink-3",
        "bonus_effect": {"kind": "cumulative", "bonus": "relance"},
        "resume": {},
    })) == {"type": "choose_pink_option", "option": "bonus"}


def test_pink_choice_without_bonus_uses_points():
    state = base_state(pink_choice={
        "owner": 1,
        "cell_id": "pink-cell-2",
        "position": 2,
        "effective_value": 4,
        "multiplier": 1,
        "bonus_slot_id": None,
        "bonus_effect": {"kind": "none"},
        "resume": {},
    })
    assert HeuristicPolicy(seed=0).choisir_action(state) == {"type": "choose_pink_option", "option": "points"}


# --------------------------------------------------------------------- Rule 8 (turquoise)

def test_turquoise_companion_active_uses_chosen_this_turn():
    board = empty_board()
    board["chosen_this_turn"] = [{"color": "yellow", "value": 4}]
    ctx = {
        "mode": "active",
        "board": board,
        "dice": all_dice({"turquoise": {"value": 4, "location": "available"}}),
        "round": 3,
        "selected_color": "turquoise",
    }
    assert turquoise_companion_count(ctx, 4) == 1


def test_turquoise_companion_passive_uses_dice_group():
    ctx = {
        "mode": "passive",
        "board": empty_board(),
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
    assert turquoise_companion_count(ctx, 4) == 1
    assert turquoise_companion_count(ctx, 3) == 1
    assert turquoise_companion_count(ctx, 5) == 0


def test_turquoise_prefers_matching_value_and_drops_lonely_one():
    policy = HeuristicPolicy(seed=0)
    state = base_state(
        phase={"kind": "passive", "player": 1, "done": False},
        dice=all_dice(
            {
                "turquoise": {"value": 4, "location": "discarded"},
                "pink": {"value": 5, "location": "discarded"},
                "yellow": {"value": 6, "location": "chosen"},
            }
        ),
    )
    lonely = {"die": "turquoise", "acting": "turquoise", "legal": ["turquoise-r1-c4"], "max_pick": 1}
    other = {"die": "yellow", "acting": "yellow", "legal": ["yellow-r3-c6"], "max_pick": 1}
    # no companion for another value → drop turquoise, keep the other use
    assert policy._pref_turquoise(state, [lonely, other]) == [other]
    # turquoise alone → fallback, never blocked
    assert policy._pref_turquoise(state, [lonely]) == [lonely]


def test_turquoise_multi_check_takes_max_and_follows_plan():
    board = empty_board()
    board["chosen_this_turn"] = [{"color": "yellow", "value": 4}, {"color": "pink", "value": 4}]
    state = _active(
        all_dice({"turquoise": {"value": 4, "location": "available"}}),
        round_n=3,
        boards={1: board, 2: empty_board()},
    )
    after_select = game_reducer(state, {"type": "select_die", "color": "turquoise"}, random.Random(0))
    assert after_select["selection"]["max_pick"] == 3

    engine = GameEngine(seed=0, state=after_select)
    policy = HeuristicPolicy(seed=0)
    policy._plan = {
        "die": "turquoise",
        "acting": "turquoise",
        "destinations": ["turquoise-r1-c4", "turquoise-r2-c4", "turquoise-r3-c4"],
        "max_pick": 3,
    }
    for _ in range(3):
        action = policy.choisir_action(engine)
        assert action["type"] == "pick_cell"
        assert engine.step(action)
    confirm = policy.choisir_action(engine)
    assert confirm == {"type": "confirm_move"}
    assert engine.step(confirm)
    checks = engine.state["boards"][1]["checks"]
    assert sum(1 for c in ("turquoise-r1-c4", "turquoise-r2-c4", "turquoise-r3-c4") if checks.get(c)) == 3


# --------------------------------------------------------------------- Rule 11 / resources

def test_single_legal_action_is_automatic():
    state = base_state(phase={"kind": "passive", "player": 1, "done": True})
    assert HeuristicPolicy(seed=0).choisir_action(state) == {"type": "continue"}


def test_plus1_is_not_consumed_by_default():
    board = empty_board()
    board["bonuses"] = {**board["bonuses"], "plus1": {"unlocked": 1, "used": 0}}
    state = base_state(phase={"kind": "plus1", "order": [1, 2], "current": 0}, boards={1: board, 2: empty_board()})
    actions = legal_actions(state)
    assert {a["type"] for a in actions} == {"begin_plus1", "skip_plus1"}
    assert HeuristicPolicy(seed=0).choisir_action(state) == {"type": "skip_plus1"}
    assert HeuristicPolicy(seed=0, plus1_probability=1.0).choisir_action(state) == {"type": "begin_plus1"}


def test_fill_slots_picks_a_discarded_die():
    state = base_state(
        phase={"kind": "fill-slots", "player": 1},
        dice=all_dice({"yellow": {"value": 3, "location": "discarded"}}),
    )
    action = HeuristicPolicy(seed=0).choisir_action(state)
    assert action["type"] == "fill_slot_dummy"


def test_action_for_player_matches_actor():
    state = _active(all_dice())
    policy = HeuristicPolicy(seed=0)
    assert policy.action_for_player(state, 2) is None
    action = policy.action_for_player(state, 1)
    assert action is not None and action["type"] == "select_die"


# --------------------------------------------------------------------- Reproducibility & full games

def test_same_seed_is_reproducible():
    run_a, run_b = GameEngine(seed=5), GameEngine(seed=5)
    run_autoplay(run_a, 6, HeuristicPolicy(seed=42))
    run_autoplay(run_b, 6, HeuristicPolicy(seed=42))
    assert run_a.action_log == run_b.action_log
    assert run_a.scores() == run_b.scores()


def test_random_wrapper_keeps_reproducibility():
    run_a, run_b = GameEngine(seed=9), GameEngine(seed=9)
    run_autoplay(run_a, 6, random.Random(7))
    run_autoplay(run_b, 6, random.Random(7))
    assert run_a.action_log == run_b.action_log


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5, 7, 11, 13, 21, 34])
def test_full_automatic_games_have_no_illegal_action(seed):
    engine = GameEngine(seed=seed)
    policy = HeuristicPolicy(seed=seed * 31 + 5)
    for _ in range(20000):
        if engine.is_over():
            break
        legal = legal_actions(engine.state)
        assert legal, f"no legal action at {engine.state['phase']}"
        action = policy.choisir_action(engine)
        assert action is not None
        if action not in legal:
            # Only the turquoise multi-check continuation is emitted directly; the
            # engine's reducer accepts it and it stays inside the legal destination set.
            assert action["type"] == "pick_cell"
            sel = engine.state["selection"]
            assert sel is not None and action["cell_id"] in sel["legal"]
        assert engine.step(action), f"engine rejected {action}"
    assert engine.is_over()


def test_run_autoplay_finishes_without_blockage():
    for seed in range(1, 8):
        summary = run_autoplay(GameEngine(seed=seed), 6, HeuristicPolicy(seed=seed + 2))
        assert summary["over"] is True
        assert summary["stopped"] == "game-over"
        assert summary["completed"] == 6
