"""Observation 2.0: a simplified, agent-centric flat ``Dict``.

Differences vs ``rl_env`` (observation 1.0):

* no adversary board axis: the agent's board is kept as 1-D arrays, the
  adversary is reduced to 5 scalars (score, foxes, min/max zone score, number of
  completed zones);
* three computed agent features are added: ``agent_min_zone``, ``agent_max_zone``,
  ``agent_zones_completed``;
* redundant/deducible fields are dropped: ``selection_legal``,
  ``selection_picked``, ``chosen_colors``, ``chosen_values``, ``slot_colors``,
  ``slot_values``, ``pending_bonus_colors``, ``pending_bonus_owner_is_agent``;
* two fields expose the intermediate state of the factorised bonus decisions:
  ``bonus_blue_cell`` and ``bonus_turquoise_row``.

A "zone" is one of the five colours; a zone is *completed* when its score reaches
the maximum reachable value of its score table (see ``ZONE_THRESHOLDS``).
"""

from __future__ import annotations

from typing import Any

import numpy as np
from gymnasium import spaces

from game_engine.bonuses import PINK_MULTIPLIERS
from game_engine.score import (
    BLUE_BRANCH,
    BLUE_SPECIAL,
    BROWN_TOTAL,
    TURQUOISE_ROW,
    YELLOW_ROW,
    compute_score,
)
from game_engine.types import GameState, PlayerId
from rl_env.observations import (
    DECISION_KINDS,
    PHASE_KINDS,
    PENDING_BONUS_CAP,
    encode_observation as encode_observation_v1,
)

OBSERVATION_VERSION_2 = "2.0"

N_PLAYERS = 2
YELLOW_SIZE = 18
TURQUOISE_SIZE = 30
BLUE_SIZE = 13
BROWN_SIZE = 12
PINK_SIZE = 12
SLOTS_SIZE = 58
CHOSEN_CAP = 3
BONUS_SLOTS_CAP = 3

ZONES = ("yellow", "turquoise", "blue", "brown", "pink")

# Maximum reachable score per zone (used for "zone completed").
ZONE_THRESHOLDS: dict[str, int] = {
    "yellow": 3 * YELLOW_ROW[6],  # 126
    "turquoise": 5 * TURQUOISE_ROW[6],  # 105
    "blue": 2 * BLUE_BRANCH[6] + 4 * len(BLUE_SPECIAL),  # 68
    "brown": BROWN_TOTAL[12],  # 90
    # pink cell 1 is forced to ceil(value/2) (max 3); cells 2..12 use value x multiplier.
    "pink": 3 + 6 * sum(PINK_MULTIPLIERS[1:]),  # 129
}

# Retained 1-D agent-board fields (read from observation 1.0, axis 0 = agent).
_AGENT_BOARD_KEYS = (
    "yellow_checks",
    "turquoise_checks",
    "blue_values",
    "brown_checks",
    "brown_disabled",
    "pink_values",
    "slots_unlocked",
    "bonuses",
)


def zone_scores(board: dict[str, Any]) -> dict[str, int]:
    score = compute_score(board)  # type: ignore[arg-type]
    return {zone: int(score[zone]) for zone in ZONES}


def zones_completed(board: dict[str, Any]) -> int:
    scores = zone_scores(board)
    return sum(1 for zone in ZONES if scores[zone] >= ZONE_THRESHOLDS[zone])


def min_zone(board: dict[str, Any]) -> int:
    return min(zone_scores(board).values())


def max_zone(board: dict[str, Any]) -> int:
    return max(zone_scores(board).values())


def observation_space_2() -> spaces.Dict:
    int8, int16, int32 = np.int8, np.int16, np.int32
    return spaces.Dict(
        {
            # agent board (1-D)
            "yellow_checks": spaces.MultiBinary([YELLOW_SIZE]),
            "turquoise_checks": spaces.MultiBinary([TURQUOISE_SIZE]),
            "blue_values": spaces.Box(0, 12, (BLUE_SIZE,), dtype=int16),
            "brown_checks": spaces.MultiBinary([BROWN_SIZE]),
            "brown_last_checked": spaces.Box(0, 12, (1,), dtype=int16),
            "brown_disabled": spaces.MultiBinary([BROWN_SIZE]),
            "pink_values": spaces.Box(0, 18, (PINK_SIZE,), dtype=int16),
            "slots_unlocked": spaces.MultiBinary([SLOTS_SIZE]),
            "bonuses": spaces.Box(0, 7, (6,), dtype=int16),
            "chosen_count": spaces.Box(0, CHOSEN_CAP, (1,), dtype=int8),
            "slot_filled": spaces.MultiBinary([BONUS_SLOTS_CAP]),
            # computed agent features
            "agent_min_zone": spaces.Box(0, 10000, (1,), dtype=int32),
            "agent_max_zone": spaces.Box(0, 10000, (1,), dtype=int32),
            "agent_zones_completed": spaces.Box(0, len(ZONES), (1,), dtype=int8),
            "score_total": spaces.Box(0, 10000, (1,), dtype=int32),
            "fox_count": spaces.Box(0, 6, (1,), dtype=int8),
            # adversary summary
            "opp_score_total": spaces.Box(0, 10000, (1,), dtype=int32),
            "opp_fox_count": spaces.Box(0, 6, (1,), dtype=int8),
            "opp_min_zone": spaces.Box(0, 10000, (1,), dtype=int32),
            "opp_max_zone": spaces.Box(0, 10000, (1,), dtype=int32),
            "opp_zones_completed": spaces.Box(0, len(ZONES), (1,), dtype=int8),
            # context
            "turn": spaces.Box(0, 6, (1,), dtype=int8),
            "round": spaces.Box(0, 3, (1,), dtype=int8),
            "phase": spaces.Box(0, len(PHASE_KINDS) - 1, (1,), dtype=int8),
            "decision": spaces.Box(0, len(DECISION_KINDS) - 1, (1,), dtype=int8),
            "actor_is_agent": spaces.MultiBinary([1]),
            "active_is_agent": spaces.MultiBinary([1]),
            # dice
            "dice_values": spaces.Box(1, 6, (6,), dtype=int8),
            "dice_locations": spaces.Box(0, 2, (6,), dtype=int8),
            "dice_joker_values": spaces.Box(0, 6, (6,), dtype=int8),
            "die_selected": spaces.MultiBinary([6]),
            # selection in progress
            "selection_present": spaces.MultiBinary([1]),
            "selection_color": spaces.Box(0, 6, (1,), dtype=int8),
            "selection_acting": spaces.Box(0, 5, (1,), dtype=int8),
            "selection_value": spaces.Box(0, 12, (1,), dtype=int8),
            "selection_max_pick": spaces.Box(0, 5, (1,), dtype=int8),
            "selection_elimination": spaces.Box(0, 6, (1,), dtype=int8),
            # overlays
            "joker_pending": spaces.MultiBinary([1]),
            "joker_pending_value": spaces.Box(0, 6, (1,), dtype=int8),
            "pink_present": spaces.MultiBinary([1]),
            "pink_position": spaces.Box(0, 12, (1,), dtype=int8),
            "pink_effective": spaces.Box(0, 12, (1,), dtype=int8),
            "pink_multiplier": spaces.Box(0, 3, (1,), dtype=int8),
            "pink_bonus_kind": spaces.Box(0, 3, (1,), dtype=int8),
            "pink_owner_is_agent": spaces.MultiBinary([1]),
            "bonus_present": spaces.MultiBinary([1]),
            "bonus_stage": spaces.Box(0, 4, (1,), dtype=int8),
            "bonus_color": spaces.Box(0, 6, (1,), dtype=int8),
            "bonus_value": spaces.Box(0, 6, (1,), dtype=int8),
            "bonus_owner_is_agent": spaces.MultiBinary([1]),
            "pending_bonus_count": spaces.Box(0, PENDING_BONUS_CAP, (1,), dtype=int8),
            # factorised sub-decisions
            "bonus_blue_cell": spaces.Box(0, 13, (1,), dtype=int8),
            "bonus_turquoise_row": spaces.Box(0, 5, (1,), dtype=int8),
        }
    )


def encode_observation_2(
    state: GameState, agent: PlayerId, pending_blue_cell: int | None = None, pending_turquoise_row: int | None = None
) -> dict[str, np.ndarray]:
    """Encode ``state`` as observation 2.0 (agent-centric)."""
    obs1 = encode_observation_v1(state, agent)
    adversary = 2 if agent == 1 else 1
    agent_score = compute_score(state["boards"][agent])
    opp_score = compute_score(state["boards"][adversary])
    agent_zones = {z: int(agent_score[z]) for z in ZONES}
    opp_zones = {z: int(opp_score[z]) for z in ZONES}

    obs: dict[str, np.ndarray] = {}
    for key in _AGENT_BOARD_KEYS:
        obs[key] = np.asarray(obs1[key][0])
    obs["brown_last_checked"] = np.array([int(obs1["brown_last_checked"][0])], dtype=np.int16)
    obs["chosen_count"] = np.array([int(obs1["chosen_count"][0])], dtype=np.int8)
    obs["slot_filled"] = np.asarray(obs1["slot_filled"][0])

    obs["agent_min_zone"] = np.array([min(agent_zones.values())], dtype=np.int32)
    obs["agent_max_zone"] = np.array([max(agent_zones.values())], dtype=np.int32)
    obs["agent_zones_completed"] = np.array(
        [sum(1 for z in ZONES if agent_zones[z] >= ZONE_THRESHOLDS[z])], dtype=np.int8
    )
    obs["score_total"] = np.array([int(agent_score["total"])], dtype=np.int32)
    obs["fox_count"] = np.array([int(agent_score["fox_count"])], dtype=np.int8)

    obs["opp_score_total"] = np.array([int(opp_score["total"])], dtype=np.int32)
    obs["opp_fox_count"] = np.array([int(opp_score["fox_count"])], dtype=np.int8)
    obs["opp_min_zone"] = np.array([min(opp_zones.values())], dtype=np.int32)
    obs["opp_max_zone"] = np.array([max(opp_zones.values())], dtype=np.int32)
    obs["opp_zones_completed"] = np.array(
        [sum(1 for z in ZONES if opp_zones[z] >= ZONE_THRESHOLDS[z])], dtype=np.int8
    )

    for key in (
        "turn",
        "round",
        "phase",
        "decision",
        "actor_is_agent",
        "active_is_agent",
        "dice_values",
        "dice_locations",
        "dice_joker_values",
        "die_selected",
        "selection_present",
        "selection_color",
        "selection_acting",
        "selection_value",
        "selection_max_pick",
        "selection_elimination",
        "joker_pending",
        "joker_pending_value",
        "pink_present",
        "pink_position",
        "pink_effective",
        "pink_multiplier",
        "pink_bonus_kind",
        "pink_owner_is_agent",
        "bonus_present",
        "bonus_stage",
        "bonus_color",
        "bonus_value",
        "bonus_owner_is_agent",
        "pending_bonus_count",
    ):
        obs[key] = np.asarray(obs1[key])

    obs["bonus_blue_cell"] = np.array([int(pending_blue_cell or 0)], dtype=np.int8)
    obs["bonus_turquoise_row"] = np.array([int(pending_turquoise_row or 0)], dtype=np.int8)
    return obs
