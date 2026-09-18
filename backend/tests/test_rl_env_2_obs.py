"""Observation 2.0: space conformity, stability, removed keys, computed features."""

from __future__ import annotations

import numpy as np
import pytest

from game_engine.score import compute_score
from rl_env.observations import encode_observation as encode_v1
from rl_env_2 import DiceGameEnv2, observation_space_2
from rl_env_2.observations import ZONE_THRESHOLDS, ZONES, encode_observation_2, zone_scores, zones_completed

REMOVED_KEYS = {
    "selection_legal",
    "selection_picked",
    "chosen_colors",
    "chosen_values",
    "slot_colors",
    "slot_values",
    "pending_bonus_colors",
    "pending_bonus_owner_is_agent",
}

NEW_FEATURES = (
    "agent_min_zone",
    "agent_max_zone",
    "agent_zones_completed",
    "opp_score_total",
    "opp_fox_count",
    "opp_min_zone",
    "opp_max_zone",
    "opp_zones_completed",
)


def _rollout(env: DiceGameEnv2, steps: int, seed: int):
    obs, info = env.reset(seed=seed)
    space = observation_space_2()
    rng = np.random.default_rng(seed)
    shapes = {key: tuple(obs[key].shape) for key in obs}
    done = 0
    while done < steps:
        assert space.contains(obs), info["decision"]
        # manual reference on the same state, from rl_env v1 + compute_score
        state = env.engine.state
        agent = env.agent_player
        adversary = 2 if agent == 1 else 1
        obs1 = encode_v1(state, agent)
        manual = {
            "agent_min_zone": min(zone_scores(state["boards"][agent]).values()),
            "agent_max_zone": max(zone_scores(state["boards"][agent]).values()),
            "agent_zones_completed": zones_completed(state["boards"][agent]),
            "opp_score_total": int(obs1["score_total"][1]),
            "opp_fox_count": int(obs1["fox_count"][1]),
            "opp_min_zone": min(zone_scores(state["boards"][adversary]).values()),
            "opp_max_zone": max(zone_scores(state["boards"][adversary]).values()),
            "opp_zones_completed": zones_completed(state["boards"][adversary]),
        }
        for key, expected in manual.items():
            assert int(obs[key][0]) == expected, (key, int(obs[key][0]), expected)

        mask = env.action_masks()
        obs, _r, term, trunc, info = env.step(int(rng.choice(np.flatnonzero(mask))))
        done += 1
        for key, shape in shapes.items():
            assert tuple(obs[key].shape) == shape, key
        if term or trunc:
            obs, info = env.reset(seed=seed + done)
    env.close()


def test_observation_space_conformity_and_features():
    env = DiceGameEnv2(agent_player="random", opponent="heuristic")
    _rollout(env, steps=100, seed=0)


def test_removed_keys_are_absent():
    env = DiceGameEnv2(agent_player=1, opponent="random")
    obs, _ = env.reset(seed=3)
    assert REMOVED_KEYS.isdisjoint(obs.keys())
    # adversary board axis is gone: agent board keys are 1-D
    assert obs["yellow_checks"].shape == (18,)
    assert obs["blue_values"].shape == (13,)
    for key in NEW_FEATURES:
        assert key in obs
    env.close()


def test_zone_thresholds_are_the_table_maxima():
    from game_engine.score import BLUE_BRANCH, BLUE_SPECIAL, BROWN_TOTAL, TURQUOISE_ROW, YELLOW_ROW

    assert ZONE_THRESHOLDS["yellow"] == 3 * YELLOW_ROW[6]
    assert ZONE_THRESHOLDS["turquoise"] == 5 * TURQUOISE_ROW[6]
    assert ZONE_THRESHOLDS["blue"] == 2 * BLUE_BRANCH[6] + 4 * len(BLUE_SPECIAL)
    assert ZONE_THRESHOLDS["brown"] == BROWN_TOTAL[12]
    assert ZONE_THRESHOLDS["pink"] == 129


def test_features_on_empty_boards():
    from tests.helpers import base_state, empty_board

    state = base_state(boards={1: empty_board(), 2: empty_board()})
    obs = encode_observation_2(state, 1)
    assert int(obs["agent_min_zone"][0]) == 0
    assert int(obs["agent_max_zone"][0]) == 0
    assert int(obs["agent_zones_completed"][0]) == 0
    assert int(obs["opp_zones_completed"][0]) == 0
    assert int(obs["bonus_blue_cell"][0]) == 0
    assert int(obs["bonus_turquoise_row"][0]) == 0
    assert set(ZONES) == {"yellow", "turquoise", "blue", "brown", "pink"}


def test_pending_fields_reflect_factorised_subdecision():
    from tests.helpers import base_state, empty_board

    state = base_state(boards={1: empty_board(), 2: empty_board()})
    obs = encode_observation_2(state, 1, pending_blue_cell=9, pending_turquoise_row=4)
    assert int(obs["bonus_blue_cell"][0]) == 9
    assert int(obs["bonus_turquoise_row"][0]) == 4
