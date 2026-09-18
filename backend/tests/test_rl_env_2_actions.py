"""Action catalogue 2.0: pruning, factorisations, mask/legality, non-regression."""

from __future__ import annotations

import copy

import numpy as np
import pytest

from game_engine.engine import GameEngine
import rl_env.actions as v1
from rl_env_2 import DiceGameEnv2, N_ACTIONS_2, Pending
from rl_env_2 import actions as v2

from tests.helpers import base_state, empty_board


def test_catalogue_is_smaller_and_versioned():
    assert N_ACTIONS_2 == 149
    assert N_ACTIONS_2 < v1.N_ACTIONS
    assert v2.ACTION_VERSION_2 == "2.0"
    assert v1.ACTION_VERSION == "1.1"


def test_removed_ids_are_gone():
    labels = [v2.label(i) for i in range(N_ACTIONS_2)]
    assert not any("dest_pink" in label for label in labels)
    assert "dest_blue:blue-cell-7" not in labels
    assert "blue_bonus_cell:blue-cell-7" not in labels
    for gone in ("utility:continue", "utility:dismiss_impossible_bonus", "utility:pass_passive"):
        assert gone not in labels
    # DEST_YELLOW is kept (reused by the yellow bonus placement).
    assert "dest_yellow:yellow-r1-c1" in labels


def _force_state(env: DiceGameEnv2, state):
    env.engine = GameEngine(seed=0, state=copy.deepcopy(state))
    env._terminated = False
    env._truncated = False
    env._pending = Pending()
    env._agent_stats = env._compute_stats()


def test_blue_bonus_factorised_two_steps():
    board = empty_board()
    board["values"] = {"blue-cell-8": 8}
    state = base_state(
        boards={1: board, 2: empty_board()},
        bonus_resolution={"owner": 1, "origin_color": "darkblue", "color": "darkblue", "stage": "placing", "value": None},
    )
    env = DiceGameEnv2(agent_player=1, opponent="heuristic")
    env.reset(seed=0)
    _force_state(env, state)

    mask = env.action_masks()
    cell_ids = np.flatnonzero(mask)
    labels = {v2.label(int(i)) for i in cell_ids}
    assert labels == {"blue_bonus_cell:blue-cell-6", "blue_bonus_cell:blue-cell-9"}

    cell9 = next(int(i) for i in cell_ids if v2.label(int(i)).endswith("blue-cell-9"))
    obs, reward, term, trunc, info = env.step(cell9)
    assert reward == 0.0 and not term and not trunc
    assert int(obs["bonus_blue_cell"][0]) == 9
    assert info["pending_blue_cell"] == 9

    mask = env.action_masks()
    values = sorted(v2.label(int(i)).split(":")[1] for i in np.flatnonzero(mask))
    assert values == sorted(["9", "7"])
    value9 = next(int(i) for i in np.flatnonzero(mask) if v2.label(int(i)) == "blue_bonus_value:9")
    env.step(value9)
    assert env.engine.state["boards"][1]["values"]["blue-cell-9"] == 9
    env.close()


def test_turquoise_bonus_factorised_two_steps():
    cells = [f"turquoise-r{r}-c3" for r in range(1, 6)]
    state = base_state(
        boards={1: empty_board(), 2: empty_board()},
        bonus_resolution={"owner": 1, "origin_color": "turquoise", "color": "turquoise", "stage": "placing", "value": None},
        selection={
            "color": "turquoise",
            "value": 0,
            "acting_color": "turquoise",
            "legal": cells,
            "picked": [],
            "max_pick": 1,
            "elimination_value": 0,
        },
    )
    env = DiceGameEnv2(agent_player=1, opponent="heuristic")
    env.reset(seed=0)
    _force_state(env, state)

    rows = sorted(v2.label(int(i)) for i in np.flatnonzero(env.action_masks()))
    assert rows == [f"turquoise_bonus_row:{r}" for r in range(1, 6)]

    row2 = next(int(i) for i in np.flatnonzero(env.action_masks()) if v2.label(int(i)).endswith(":2"))
    obs, reward, *_ = env.step(row2)
    assert reward == 0.0 and int(obs["bonus_turquoise_row"][0]) == 2
    cols = [v2.label(int(i)) for i in np.flatnonzero(env.action_masks())]
    assert cols == ["turquoise_bonus_col:3"]
    col3 = int(np.flatnonzero(env.action_masks())[0])
    env.step(col3)
    assert env.engine.state["boards"][1]["checks"].get("turquoise-r2-c3") is True
    env.close()


def test_non_regression_engine_moves_match_rl_env():
    # blue bonus: rl_env single id vs rl_env_2 two-step both yield place_bonus_blue(9,9)
    board = empty_board()
    board["values"] = {"blue-cell-8": 8}
    state = base_state(
        boards={1: board, 2: empty_board()},
        bonus_resolution={"owner": 1, "origin_color": "darkblue", "color": "darkblue", "stage": "placing", "value": None},
    )
    v1_ids = {v1.label(d.action_id): d.actions for d in v1.build_legal_decisions(state)}
    v1_action = v1_ids["blue_bonus:9=9"]
    env = DiceGameEnv2(agent_player=1)
    env.reset(seed=0)
    _force_state(env, state)
    cell9 = next(int(i) for i in np.flatnonzero(env.action_masks()) if v2.label(int(i)).endswith("blue-cell-9"))
    env.step(cell9)
    value9 = next(int(i) for i in np.flatnonzero(env.action_masks()) if v2.label(int(i)) == "blue_bonus_value:9")
    v2_action = v2.decode(env.engine.state, value9, env._pending)
    assert v1_action == v2_action
    env.close()


def test_encode_decode_roundtrip_over_games():
    env = DiceGameEnv2(agent_player="random", opponent="heuristic")
    rng = np.random.default_rng(0)
    checked = 0
    for seed in range(100):
        obs, _ = env.reset(seed=seed)
        for _ in range(5000):
            state = env.engine.state
            pending = env._pending
            mask = env.action_masks()
            if not mask.any():
                break
            for aid in np.flatnonzero(mask):
                aid = int(aid)
                actions = v2.decode(state, aid, pending)
                if actions:
                    assert v2.encode(state, actions, pending) == aid, (aid, v2.label(aid))
                    checked += 1
            obs, _r, term, trunc, info = env.step(int(rng.choice(np.flatnonzero(mask))))
            if term or trunc:
                break
    assert checked > 500
    env.close()


def test_mask_actions_are_accepted_by_engine():
    env = DiceGameEnv2(agent_player="random", opponent="heuristic")
    for seed in range(30):
        env.reset(seed=seed)
        for _ in range(5000):
            state = env.engine.state
            pending = env._pending
            mask = env.action_masks()
            if not mask.any():
                break
            for aid in np.flatnonzero(mask):
                probe = GameEngine(seed=0, state=copy.deepcopy(state))
                for action in v2.decode(state, int(aid), pending):
                    assert probe.step(action), (v2.label(int(aid)), action)
            obs, _r, term, trunc, info = env.step(int(np.random.default_rng(seed).choice(np.flatnonzero(mask))))
            if term or trunc:
                break
    env.close()


def test_all_v2_ids_are_labelled():
    for aid in range(N_ACTIONS_2):
        assert not v2.label(aid).startswith("unknown"), aid
