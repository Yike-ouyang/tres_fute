"""Numeric, flat observation encoding and observation space for :mod:`rl_env`.

The observation is a flat ``gymnasium.spaces.Dict`` of fixed-shape numeric
arrays. Its point of view is constant: axis 0 of every two-player array is the
**agent**, axis 1 is the **adversary**, regardless of who is currently active or
passive. Board geometry follows the full game: yellow 3x6, turquoise 5x6, blue
13 cells (centre included, see mapping below), brown 12, pink 12.

Blue mapping: index ``p - 1`` holds ``blue-cell-p`` for ``p`` in 1..13. The centre
cell ``blue-cell-7`` is never written by the rules (it is the branch origin) and
always stays at value 0; it is kept so indices are simple.

Die identity is preserved: dice are read in the engine's fixed colour order and
never sorted. No RNG internal state and no future rolls are exposed.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from gymnasium import spaces

from game_engine.bonuses import ALL_SLOTS
from game_engine.legal import current_decision
from game_engine.score import compute_score
from game_engine.types import ACTING_COLORS, ALL_DIE_COLORS, GameState, PlayerId

from .actions import BLUE_CELLS, BROWN_CELLS, PINK_CELLS, YELLOW_CELLS

OBSERVATION_VERSION = "1.0"

# --- fixed sizes -----------------------------------------------------------

N_PLAYERS = 2
YELLOW_SIZE = len(YELLOW_CELLS)  # 18
TURQUOISE_SIZE = 30
BLUE_SIZE = 13
BROWN_SIZE = len(BROWN_CELLS)  # 12
PINK_SIZE = len(PINK_CELLS)  # 12
SLOTS_SIZE = len(ALL_SLOTS)  # 58
CHOSEN_CAP = 3
BONUS_SLOTS_CAP = 3
PENDING_BONUS_CAP = 8  # measured max is 2; generous, asserted (never truncated)

# Selection destination catalogue (bit layout for legal/picked masks).
DEST_YELLOW_START = 0
DEST_BLUE_START = DEST_YELLOW_START + YELLOW_SIZE  # 18
DEST_BROWN_START = DEST_BLUE_START + BLUE_SIZE  # 31
DEST_PINK_START = DEST_BROWN_START + BROWN_SIZE  # 43
DEST_TURQUOISE_START = DEST_PINK_START + PINK_SIZE  # 55
DEST_CELL_COUNT = DEST_TURQUOISE_START + TURQUOISE_SIZE  # 85

PHASE_KINDS = ("none", "active", "passive", "plus1", "fill-slots", "game-over")
DECISION_KINDS = (
    "none",
    "select_die",
    "white_color",
    "dest_yellow",
    "dest_turquoise",
    "dest_blue",
    "dest_brown",
    "dest_pink",
    "pink_option",
    "joker_value",
    "bonus_color",
    "bonus_value",
    "blue_bonus_place",
    "bonus_place_yellow",
    "bonus_place_brown",
    "bonus_place_turquoise",
    "fill_slot",
    "plus1_window",
    "auto",
)
BONUS_DIE_COLORS = ("yellow", "turquoise", "darkblue", "brown", "pink", "black")
PINK_BONUS_KINDS = ("none", "cumulative", "die", "fox")

_LOCATION_INDEX = {"available": 0, "chosen": 1, "discarded": 2}


def decision_kind(state: GameState) -> str:
    """Classify the current engine decision (observation/trace helper)."""
    if state["pink_choice"]:
        return "pink_option"
    if state["bonus_resolution"]:
        br = state["bonus_resolution"]
        if br["stage"] == "chooseColor":
            return "bonus_color"
        if br["stage"] == "chooseValue":
            return "bonus_value"
        if br["stage"] == "placing" and br["color"] == "darkblue":
            return "blue_bonus_place"
        if br["stage"] == "placing":
            return f"bonus_place_{br['color']}" if br["color"] in ("turquoise",) else f"bonus_place_{br['color']}"
        return "auto"
    if state["selection"]:
        sel = state["selection"]
        if sel["color"] == "white" and sel["acting_color"] is None:
            return "white_color"
        return f"dest_{'blue' if sel['acting_color'] == 'darkblue' else sel['acting_color']}"
    if state["joker_pending"]:
        return "joker_value" if state["joker_pending"].get("value") is None else "select_die"
    kind = state["phase"]["kind"]
    if kind == "fill-slots":
        return "fill_slot"
    if kind == "plus1" and state["plus1_active"] is None:
        return "plus1_window"
    if kind in ("active", "passive", "plus1"):
        return "select_die"
    return "auto"


def _kind_index(kind: str) -> int:
    return DECISION_KINDS.index(kind) if kind in DECISION_KINDS else DECISION_KINDS.index("auto")


def dest_cell_index(cell_id: str) -> int | None:
    if cell_id in YELLOW_CELLS:
        return DEST_YELLOW_START + YELLOW_CELLS.index(cell_id)
    if cell_id in BLUE_CELLS:
        return DEST_BLUE_START + BLUE_CELLS.index(cell_id)
    if cell_id in BROWN_CELLS:
        return DEST_BROWN_START + BROWN_CELLS.index(cell_id)
    if cell_id in PINK_CELLS:
        return DEST_PINK_START + PINK_CELLS.index(cell_id)
    if cell_id.startswith("turquoise-r"):
        row = int(cell_id.split("-")[1][1:])
        col = int(cell_id.rsplit("-c", 1)[1])
        return DEST_TURQUOISE_START + (row - 1) * 6 + (col - 1)
    return None


def observation_space() -> spaces.Dict:
    """The fixed observation space (flat Dict of numeric arrays)."""
    int8 = np.int8
    int16 = np.int16
    int32 = np.int32
    return spaces.Dict(
        {
            # per-player boards (axis 0: 0 = agent, 1 = adversary)
            "yellow_checks": spaces.MultiBinary([N_PLAYERS, YELLOW_SIZE]),
            "turquoise_checks": spaces.MultiBinary([N_PLAYERS, TURQUOISE_SIZE]),
            "blue_values": spaces.Box(0, 12, (N_PLAYERS, BLUE_SIZE), dtype=int16),
            "brown_checks": spaces.MultiBinary([N_PLAYERS, BROWN_SIZE]),
            "brown_last_checked": spaces.Box(0, 12, (N_PLAYERS,), dtype=int16),
            "brown_disabled": spaces.MultiBinary([N_PLAYERS, BROWN_SIZE]),
            "pink_values": spaces.Box(0, 18, (N_PLAYERS, PINK_SIZE), dtype=int16),
            "bonuses": spaces.Box(0, 7, (N_PLAYERS, 6), dtype=int16),
            "slots_unlocked": spaces.MultiBinary([N_PLAYERS, SLOTS_SIZE]),
            "chosen_count": spaces.Box(0, CHOSEN_CAP, (N_PLAYERS,), dtype=int8),
            "chosen_colors": spaces.Box(0, 6, (N_PLAYERS, CHOSEN_CAP), dtype=int8),
            "chosen_values": spaces.Box(0, 6, (N_PLAYERS, CHOSEN_CAP), dtype=int8),
            "slot_filled": spaces.MultiBinary([N_PLAYERS, BONUS_SLOTS_CAP]),
            "slot_colors": spaces.Box(0, 6, (N_PLAYERS, BONUS_SLOTS_CAP), dtype=int8),
            "slot_values": spaces.Box(0, 6, (N_PLAYERS, BONUS_SLOTS_CAP), dtype=int8),
            "score_total": spaces.Box(0, 10000, (N_PLAYERS,), dtype=int32),
            "fox_count": spaces.Box(0, 6, (N_PLAYERS,), dtype=int8),
            # context
            "turn": spaces.Box(0, 6, (1,), dtype=int8),
            "round": spaces.Box(0, 3, (1,), dtype=int8),
            "phase": spaces.Box(0, len(PHASE_KINDS) - 1, (1,), dtype=int8),
            "decision": spaces.Box(0, len(DECISION_KINDS) - 1, (1,), dtype=int8),
            "actor_is_agent": spaces.MultiBinary([1]),
            "active_is_agent": spaces.MultiBinary([1]),
            # dice (fixed colour order)
            "dice_values": spaces.Box(1, 6, (len(ALL_DIE_COLORS),), dtype=int8),
            "dice_locations": spaces.Box(0, 2, (len(ALL_DIE_COLORS),), dtype=int8),
            "dice_joker_values": spaces.Box(0, 6, (len(ALL_DIE_COLORS),), dtype=int8),
            "die_selected": spaces.MultiBinary([len(ALL_DIE_COLORS)]),
            # action in progress
            "selection_present": spaces.MultiBinary([1]),
            "selection_color": spaces.Box(0, 6, (1,), dtype=int8),
            "selection_acting": spaces.Box(0, 5, (1,), dtype=int8),
            "selection_value": spaces.Box(0, 12, (1,), dtype=int8),
            "selection_max_pick": spaces.Box(0, 5, (1,), dtype=int8),
            "selection_elimination": spaces.Box(0, 6, (1,), dtype=int8),
            "selection_picked": spaces.MultiBinary([DEST_CELL_COUNT]),
            "selection_legal": spaces.MultiBinary([DEST_CELL_COUNT]),
            "joker_pending": spaces.MultiBinary([1]),
            "joker_pending_value": spaces.Box(0, 6, (1,), dtype=int8),
            # pending resolutions
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
            "pending_bonus_colors": spaces.Box(0, 6, (PENDING_BONUS_CAP,), dtype=int8),
            "pending_bonus_owner_is_agent": spaces.MultiBinary([PENDING_BONUS_CAP]),
        }
    )


_BONUS_STAGES = ("chooseColor", "chooseValue", "placing", "noMove")


def _player_order(agent: PlayerId) -> tuple[PlayerId, PlayerId]:
    return (agent, 2 if agent == 1 else 1)  # index 0 = agent, index 1 = adversary


def _board_arrays(board: dict[str, Any]) -> dict[str, Any]:
    yellow = np.array([1 if board["checks"].get(c) else 0 for c in YELLOW_CELLS], dtype=np.int8)
    turquoise = np.array(
        [1 if board["checks"].get(f"turquoise-r{r}-c{c}") else 0 for r in range(1, 6) for c in range(1, 7)],
        dtype=np.int8,
    )
    blue = np.array([int(board["values"].get(c, 0)) for c in BLUE_CELLS], dtype=np.int16)
    brown = np.array([1 if board["checks"].get(c) else 0 for c in BROWN_CELLS], dtype=np.int8)
    brown_disabled = np.array([1 if board["brown_disabled"].get(c) else 0 for c in BROWN_CELLS], dtype=np.int8)
    pink = np.array([int(board["values"].get(c, 0)) for c in PINK_CELLS], dtype=np.int16)
    bonuses = board["bonuses"]
    bonus_vec = np.array(
        [
            bonuses["relance"]["unlocked"],
            bonuses["relance"]["used"],
            bonuses["joker"]["unlocked"],
            bonuses["joker"]["used"],
            bonuses["plus1"]["unlocked"],
            bonuses["plus1"]["used"],
        ],
        dtype=np.int16,
    )
    slots = np.array([1 if bonuses["slots_unlocked"].get(s.slot_id) else 0 for s in ALL_SLOTS], dtype=np.int8)
    chosen = board["chosen_this_turn"][:CHOSEN_CAP]
    chosen_colors = np.zeros(CHOSEN_CAP, dtype=np.int8)
    chosen_values = np.zeros(CHOSEN_CAP, dtype=np.int8)
    for i, die in enumerate(chosen):
        chosen_colors[i] = ALL_DIE_COLORS.index(die["color"]) + 1
        chosen_values[i] = die["value"]
    slot_filled = np.zeros(BONUS_SLOTS_CAP, dtype=np.int8)
    slot_colors = np.zeros(BONUS_SLOTS_CAP, dtype=np.int8)
    slot_values = np.zeros(BONUS_SLOTS_CAP, dtype=np.int8)
    for i, die in enumerate(board["slots"][:BONUS_SLOTS_CAP]):
        if die is None:
            continue
        slot_filled[i] = 1
        slot_colors[i] = ALL_DIE_COLORS.index(die["color"]) + 1
        slot_values[i] = die["value"]
    score = compute_score(board)
    return {
        "yellow_checks": yellow,
        "turquoise_checks": turquoise,
        "blue_values": blue,
        "brown_checks": brown,
        "brown_last_checked": int(board["brown_last_checked"] or 0),
        "brown_disabled": brown_disabled,
        "pink_values": pink,
        "bonuses": bonus_vec,
        "slots_unlocked": slots,
        "chosen_count": len(chosen),
        "chosen_colors": chosen_colors,
        "chosen_values": chosen_values,
        "slot_filled": slot_filled,
        "slot_colors": slot_colors,
        "slot_values": slot_values,
        "score_total": score["total"],
        "fox_count": score["fox_count"],
    }


def encode_observation(state: GameState, agent: PlayerId) -> dict[str, np.ndarray]:
    """Encode ``state`` from ``agent``'s point of view (index 0 = agent)."""
    order = _player_order(agent)
    boards = [_board_arrays(state["boards"][p]) for p in order]

    obs: dict[str, np.ndarray] = {
        "yellow_checks": np.stack([b["yellow_checks"] for b in boards]).astype(np.int8),
        "turquoise_checks": np.stack([b["turquoise_checks"] for b in boards]).astype(np.int8),
        "blue_values": np.stack([b["blue_values"] for b in boards]).astype(np.int16),
        "brown_checks": np.stack([b["brown_checks"] for b in boards]).astype(np.int8),
        "brown_last_checked": np.array([b["brown_last_checked"] for b in boards], dtype=np.int16),
        "brown_disabled": np.stack([b["brown_disabled"] for b in boards]).astype(np.int8),
        "pink_values": np.stack([b["pink_values"] for b in boards]).astype(np.int16),
        "bonuses": np.stack([b["bonuses"] for b in boards]).astype(np.int16),
        "slots_unlocked": np.stack([b["slots_unlocked"] for b in boards]).astype(np.int8),
        "chosen_count": np.array([b["chosen_count"] for b in boards], dtype=np.int8),
        "chosen_colors": np.stack([b["chosen_colors"] for b in boards]).astype(np.int8),
        "chosen_values": np.stack([b["chosen_values"] for b in boards]).astype(np.int8),
        "slot_filled": np.stack([b["slot_filled"] for b in boards]).astype(np.int8),
        "slot_colors": np.stack([b["slot_colors"] for b in boards]).astype(np.int8),
        "slot_values": np.stack([b["slot_values"] for b in boards]).astype(np.int8),
        "score_total": np.array([b["score_total"] for b in boards], dtype=np.int32),
        "fox_count": np.array([b["fox_count"] for b in boards], dtype=np.int8),
        "turn": np.array([state["global_turn"]], dtype=np.int8),
        "round": np.array([state["phase"].get("round", 0) or 0], dtype=np.int8),
        "phase": np.array([PHASE_KINDS.index(state["phase"]["kind"])], dtype=np.int8),
        "decision": np.array([_kind_index(decision_kind(state))], dtype=np.int8),
    }

    decision = current_decision(state)
    actor = decision.get("actor")
    obs["actor_is_agent"] = np.array([1 if actor == agent else 0], dtype=np.int8)
    active_actor = state["phase"].get("player") if state["phase"]["kind"] == "active" else None
    obs["active_is_agent"] = np.array([1 if active_actor == agent else 0], dtype=np.int8)

    # dice
    obs["dice_values"] = np.array([state["dice"][c]["value"] for c in ALL_DIE_COLORS], dtype=np.int8)
    obs["dice_locations"] = np.array([_LOCATION_INDEX[state["dice"][c]["location"]] for c in ALL_DIE_COLORS], dtype=np.int8)
    obs["dice_joker_values"] = np.array(
        [int(state["dice"][c].get("joker_value") or 0) for c in ALL_DIE_COLORS], dtype=np.int8
    )
    sel = state["selection"]
    sel_color = ALL_DIE_COLORS.index(sel["color"]) + 1 if sel else 0
    obs["die_selected"] = np.array(
        [1 if (sel and c == sel["color"]) else 0 for c in ALL_DIE_COLORS], dtype=np.int8
    )

    # selection in progress
    picked = np.zeros(DEST_CELL_COUNT, dtype=np.int8)
    legal_mask = np.zeros(DEST_CELL_COUNT, dtype=np.int8)
    if sel:
        for cid in sel["picked"]:
            idx = dest_cell_index(cid)
            if idx is not None:
                picked[idx] = 1
        for cid in sel["legal"]:
            idx = dest_cell_index(cid)
            if idx is not None:
                legal_mask[idx] = 1
    obs["selection_present"] = np.array([1 if sel else 0], dtype=np.int8)
    obs["selection_color"] = np.array([sel_color], dtype=np.int8)
    obs["selection_acting"] = np.array(
        [ACTING_COLORS.index(sel["acting_color"]) + 1 if sel and sel["acting_color"] else 0], dtype=np.int8
    )
    obs["selection_value"] = np.array([int(sel["value"]) if sel else 0], dtype=np.int8)
    obs["selection_max_pick"] = np.array([int(sel["max_pick"]) if sel else 0], dtype=np.int8)
    obs["selection_elimination"] = np.array([int(sel["elimination_value"]) if sel else 0], dtype=np.int8)
    obs["selection_picked"] = picked
    obs["selection_legal"] = legal_mask

    jp = state["joker_pending"]
    obs["joker_pending"] = np.array([1 if jp else 0], dtype=np.int8)
    obs["joker_pending_value"] = np.array([int(jp["value"]) if jp and jp.get("value") else 0], dtype=np.int8)

    # pink choice
    pc = state["pink_choice"]
    obs["pink_present"] = np.array([1 if pc else 0], dtype=np.int8)
    obs["pink_position"] = np.array([int(pc["position"]) if pc else 0], dtype=np.int8)
    obs["pink_effective"] = np.array([int(pc["effective_value"]) if pc else 0], dtype=np.int8)
    obs["pink_multiplier"] = np.array([int(pc["multiplier"]) if pc else 0], dtype=np.int8)
    obs["pink_bonus_kind"] = np.array(
        [PINK_BONUS_KINDS.index(pc["bonus_effect"].get("kind", "none")) if pc else 0], dtype=np.int8
    )
    obs["pink_owner_is_agent"] = np.array([1 if pc and pc["owner"] == agent else 0], dtype=np.int8)

    # bonus resolution
    br = state["bonus_resolution"]
    obs["bonus_present"] = np.array([1 if br else 0], dtype=np.int8)
    obs["bonus_stage"] = np.array([_BONUS_STAGES.index(br["stage"]) if br else 0], dtype=np.int8)
    obs["bonus_color"] = np.array(
        [BONUS_DIE_COLORS.index(br["color"]) + 1 if br else 0], dtype=np.int8
    )
    obs["bonus_value"] = np.array([int(br["value"]) if br and br["value"] is not None else 0], dtype=np.int8)
    obs["bonus_owner_is_agent"] = np.array([1 if br and br["owner"] == agent else 0], dtype=np.int8)

    # pending bonus queue (never truncated: the cap is asserted)
    queue = state["pending_bonuses"]
    if len(queue) > PENDING_BONUS_CAP:
        raise RuntimeError(
            f"pending_bonuses length {len(queue)} exceeds PENDING_BONUS_CAP={PENDING_BONUS_CAP}; "
            "increase the cap in observations.py instead of truncating"
        )
    obs["pending_bonus_count"] = np.array([len(queue)], dtype=np.int8)
    pending_colors = np.zeros(PENDING_BONUS_CAP, dtype=np.int8)
    pending_agent = np.zeros(PENDING_BONUS_CAP, dtype=np.int8)
    for i, item in enumerate(queue):
        pending_colors[i] = BONUS_DIE_COLORS.index(item["color"]) + 1
        pending_agent[i] = 1 if item["owner"] == agent else 0
    obs["pending_bonus_colors"] = pending_colors
    obs["pending_bonus_owner_is_agent"] = pending_agent
    return obs
