"""Fixed action catalogue, encoding/decoding and masking for :mod:`rl_env`.

The catalogue maps *semantic decisions* (stable across states, episodes and
instances) to integer ids. It never uses "the index of the current legal-action
list". A single id may decode to a short sequence of engine actions when the
engine needs several commands to apply one decision (e.g. picking a cell then
confirming, or checking several turquoise rows); the adapter orchestrates them
without re-implementing any rule.

Layout of the ``Discrete(N_ACTIONS)`` space (see the README for the full table)::

    SELECT_DIE           0 ..   5    one per physical die colour (yellow..white)
    WHITE_COLOR          6 ..  10    acting colour of the white die
    DEST_YELLOW         11 ..  28    yellow-r{1..3}-c{1..6}
    DEST_TURQUOISE      29 ..  59    31 non-empty row subsets (column set by the die)
    DEST_BLUE           60 ..  72    blue-cell-1..13
    DEST_BROWN          73 ..  84    brown-cell-1..12
    DEST_PINK           85 ..  96    pink-cell-1..12
    PINK_OPTION         97 ..  98    points / bonus
    JOKER_VALUE         99 .. 104    joker value 1..6
    BONUS_COLOR        105 .. 109    black-bonus acting colour
    BONUS_VALUE        110 .. 115    bonus value 1..6
    BLUE_BONUS_PLACE   116 .. 271    (blue cell 1..13) x (value 1..12)
    TURQUOISE_BONUS    272 .. 301    immediate turquoise bonus cell (r,c)
    UTILITY            302 .. 309    relance/joker/plus1/pass/continue/fill helpers
    FILL_SLOT          310 .. 315    filler die colour
"""

from __future__ import annotations

from typing import Any, NamedTuple

import numpy as np

from game_engine.legal import legal_actions
from game_engine.types import ACTING_COLORS, ALL_DIE_COLORS, Action, GameState

ACTION_VERSION = "1.1"

# --- id sections -----------------------------------------------------------

SELECT_DIE_OFFSET = 0
SELECT_DIE_COUNT = len(ALL_DIE_COLORS)  # 6

WHITE_COLOR_OFFSET = SELECT_DIE_OFFSET + SELECT_DIE_COUNT  # 6
WHITE_COLOR_COUNT = len(ACTING_COLORS)  # 5

YELLOW_OFFSET = WHITE_COLOR_OFFSET + WHITE_COLOR_COUNT  # 11
YELLOW_CELLS = [f"yellow-r{r}-c{c}" for r in range(1, 4) for c in range(1, 7)]
YELLOW_COUNT = len(YELLOW_CELLS)  # 18

TURQUOISE_OFFSET = YELLOW_OFFSET + YELLOW_COUNT  # 29
TURQUOISE_ROWS: tuple[int, ...] = (1, 2, 3, 4, 5)
# 31 non-empty subsets of rows, ordered by bit mask (row r -> bit r-1).
TURQUOISE_SUBSETS: list[tuple[int, ...]] = [
    tuple(r for r in TURQUOISE_ROWS if mask & (1 << (r - 1))) for mask in range(1, 1 << len(TURQUOISE_ROWS))
]
TURQUOISE_COUNT = len(TURQUOISE_SUBSETS)  # 31

BLUE_OFFSET = TURQUOISE_OFFSET + TURQUOISE_COUNT  # 60
BLUE_CELLS = [f"blue-cell-{p}" for p in range(1, 14)]
BLUE_COUNT = len(BLUE_CELLS)  # 13

BROWN_OFFSET = BLUE_OFFSET + BLUE_COUNT  # 73
BROWN_CELLS = [f"brown-cell-{n}" for n in range(1, 13)]
BROWN_COUNT = len(BROWN_CELLS)  # 12

PINK_OFFSET = BROWN_OFFSET + BROWN_COUNT  # 85
PINK_CELLS = [f"pink-cell-{n}" for n in range(1, 13)]
PINK_COUNT = len(PINK_CELLS)  # 12

PINK_OPTION_OFFSET = PINK_OFFSET + PINK_COUNT  # 97
PINK_OPTIONS = ("points", "bonus")
PINK_OPTION_COUNT = 2

JOKER_VALUE_OFFSET = PINK_OPTION_OFFSET + PINK_OPTION_COUNT  # 99
JOKER_VALUE_COUNT = 6

BONUS_COLOR_OFFSET = JOKER_VALUE_OFFSET + JOKER_VALUE_COUNT  # 105
BONUS_COLOR_COUNT = len(ACTING_COLORS)  # 5

BONUS_VALUE_OFFSET = BONUS_COLOR_OFFSET + BONUS_COLOR_COUNT  # 110
BONUS_VALUE_COUNT = 6
BONUS_VALUE_MAX = 6

BLUE_BONUS_OFFSET = BONUS_VALUE_OFFSET + BONUS_VALUE_COUNT  # 116
# A blue sum is at most 12; the engine never proposes a higher (cell, value) pair.
BLUE_BONUS_VALUE_MAX = 12
BLUE_BONUS_COUNT = BLUE_COUNT * BLUE_BONUS_VALUE_MAX  # 156

TURQUOISE_BONUS_OFFSET = BLUE_BONUS_OFFSET + BLUE_BONUS_COUNT  # 272
TURQUOISE_BONUS_CELLS = [f"turquoise-r{r}-c{c}" for r in TURQUOISE_ROWS for c in range(1, 7)]
TURQUOISE_BONUS_COUNT = len(TURQUOISE_BONUS_CELLS)  # 30

UTILITY_OFFSET = TURQUOISE_BONUS_OFFSET + TURQUOISE_BONUS_COUNT  # 302
UTILITY_KINDS = (
    "use_relance",
    "start_joker",
    "begin_plus1",
    "skip_plus1",
    "end_active_early",
    "pass_passive",
    "dismiss_impossible_bonus",
    "continue",
)
UTILITY_COUNT = len(UTILITY_KINDS)  # 8

FILL_SLOT_OFFSET = UTILITY_OFFSET + UTILITY_COUNT  # 310
FILL_SLOT_COUNT = len(ALL_DIE_COLORS)  # 6

N_ACTIONS = FILL_SLOT_OFFSET + FILL_SLOT_COUNT  # 316

_UTILITY_INDEX = {name: i for i, name in enumerate(UTILITY_KINDS)}
_DEST_LAYOUT = {
    "yellow": (YELLOW_OFFSET, YELLOW_CELLS),
    "darkblue": (BLUE_OFFSET, BLUE_CELLS),
    "brown": (BROWN_OFFSET, BROWN_CELLS),
    "pink": (PINK_OFFSET, PINK_CELLS),
}


class Decision(NamedTuple):
    """A catalogue entry: stable id, engine action sequence and readable label."""

    action_id: int
    actions: list[Action]
    label: str


def _turquoise_row(cell_id: str) -> int:
    return int(cell_id.split("-")[1][1:])


def _turquoise_col(cell_id: str) -> int:
    return int(cell_id.rsplit("-c", 1)[1])


def build_legal_decisions(state: GameState) -> list[Decision]:
    """Enumerate the catalogue entries legal in ``state`` (context-aware)."""
    legal = legal_actions(state)
    if not legal:
        return []
    if state["pink_choice"]:
        return _pink_options(legal)
    if state["bonus_resolution"]:
        return _bonus_decisions(state, legal)
    if state["selection"]:
        return _selection_decisions(state, legal)
    if state["joker_pending"]:
        return _joker_decisions(state, legal)
    kind = state["phase"]["kind"]
    if kind == "fill-slots":
        return _fill_slot_decisions(legal)
    if kind == "plus1" and state["plus1_active"] is None:
        return _utility_decisions(legal, ("begin_plus1", "skip_plus1"))
    if kind in ("active", "passive", "plus1"):
        return _select_decisions(legal)
    return []


def _pink_options(legal: list[Action]) -> list[Decision]:
    out: list[Decision] = []
    for action in legal:
        if action["type"] != "choose_pink_option":
            continue
        idx = PINK_OPTIONS.index(action["option"])
        out.append(Decision(PINK_OPTION_OFFSET + idx, [action], f"pink:{action['option']}"))
    return out


def _utility_decisions(legal: list[Action], kinds: tuple[str, ...]) -> list[Decision]:
    out: list[Decision] = []
    for action in legal:
        if action["type"] in kinds:
            out.append(Decision(UTILITY_OFFSET + _UTILITY_INDEX[action["type"]], [action], action["type"]))
    return out


def _select_decisions(legal: list[Action]) -> list[Decision]:
    out: list[Decision] = []
    for action in legal:
        if action["type"] == "select_die":
            idx = ALL_DIE_COLORS.index(action["color"])
            out.append(Decision(SELECT_DIE_OFFSET + idx, [action], f"die:{action['color']}"))
        elif action["type"] in ("use_relance", "start_joker", "end_active_early", "pass_passive"):
            out.append(Decision(UTILITY_OFFSET + _UTILITY_INDEX[action["type"]], [action], action["type"]))
    return out


def _fill_slot_decisions(legal: list[Action]) -> list[Decision]:
    out: list[Decision] = []
    for action in legal:
        if action["type"] == "fill_slot_dummy":
            idx = ALL_DIE_COLORS.index(action["color"])
            out.append(Decision(FILL_SLOT_OFFSET + idx, [action], f"fill:{action['color']}"))
        elif action["type"] == "start_joker":
            # Joker is usable whenever dice must be chosen, including fill-slots.
            out.append(Decision(UTILITY_OFFSET + _UTILITY_INDEX["start_joker"], [action], "start_joker"))
    return out


def _selection_decisions(state: GameState, legal: list[Action]) -> list[Decision]:
    sel = state["selection"]
    assert sel is not None
    if sel["color"] == "white" and sel["acting_color"] is None:
        out: list[Decision] = []
        for action in legal:
            if action["type"] == "choose_white_color":
                idx = ACTING_COLORS.index(action["acting_color"])
                out.append(Decision(WHITE_COLOR_OFFSET + idx, [action], f"white:{action['acting_color']}"))
        return out
    return _destination_decisions(sel, legal)


def _destination_decisions(sel: dict[str, Any], legal: list[Action]) -> list[Decision]:
    acting = sel["acting_color"]
    picks = [a for a in legal if a["type"] == "pick_cell"]
    if not picks:
        return []  # single technical confirmation is auto-applied by the environment
    if acting == "turquoise":
        return _turquoise_decisions(sel, picks)
    offset, cells = _DEST_LAYOUT[acting]
    out: list[Decision] = []
    for action in picks:
        idx = cells.index(action["cell_id"])
        out.append(
            Decision(
                offset + idx,
                [action, {"type": "confirm_move"}],
                f"{acting}:{action['cell_id']}",
            )
        )
    return out


def _turquoise_decisions(sel: dict[str, Any], picks: list[Action]) -> list[Decision]:
    free_rows = {_turquoise_row(a["cell_id"]) for a in picks}
    column = _turquoise_col(picks[0]["cell_id"])
    by_row = {_turquoise_row(a["cell_id"]): a for a in picks}
    out: list[Decision] = []
    for idx, subset in enumerate(TURQUOISE_SUBSETS):
        if len(subset) > sel["max_pick"] or not set(subset) <= free_rows:
            continue
        actions: list[Action] = [by_row[r] for r in subset]
        actions.append({"type": "confirm_move"})
        rows = "".join(str(r) for r in subset)
        out.append(Decision(TURQUOISE_OFFSET + idx, actions, f"turquoise:rows{rows}@c{column}"))
    return out


def _joker_decisions(state: GameState, legal: list[Action]) -> list[Decision]:
    jp = state["joker_pending"]
    assert jp is not None
    if jp.get("value") is None:
        out: list[Decision] = []
        for action in legal:
            if action["type"] == "set_joker_value":
                out.append(
                    Decision(JOKER_VALUE_OFFSET + action["value"] - 1, [action], f"joker-value:{action['value']}")
                )
        return out
    return _select_decisions(legal)


def _bonus_decisions(state: GameState, legal: list[Action]) -> list[Decision]:
    br = state["bonus_resolution"]
    assert br is not None
    stage, color = br["stage"], br["color"]
    if stage == "chooseColor":
        out: list[Decision] = []
        for action in legal:
            if action["type"] == "choose_bonus_color":
                idx = ACTING_COLORS.index(action["color"])
                out.append(Decision(BONUS_COLOR_OFFSET + idx, [action], f"bonus-color:{action['color']}"))
        return out
    if stage == "chooseValue":
        out = []
        for action in legal:
            if action["type"] == "choose_bonus_value":
                out.append(
                    Decision(BONUS_VALUE_OFFSET + action["value"] - 1, [action], f"bonus-value:{action['value']}")
                )
        return out
    if stage == "placing" and color == "darkblue":
        out = []
        for action in legal:
            if action["type"] == "place_bonus_blue":
                cell = int(action["cell_id"].rsplit("-", 1)[1])
                value = int(action["value"])
                if not (1 <= cell <= BLUE_COUNT and 1 <= value <= BLUE_BONUS_VALUE_MAX):
                    raise ValueError(f"blue bonus out of catalogue range: {action}")
                idx = (cell - 1) * BLUE_BONUS_VALUE_MAX + (value - 1)
                out.append(Decision(BLUE_BONUS_OFFSET + idx, [action], f"blue-bonus:{cell}={value}"))
        return out
    if stage == "placing":
        picks = [a for a in legal if a["type"] == "pick_cell"]
        if color == "turquoise":
            out = []
            for action in picks:
                idx = TURQUOISE_BONUS_CELLS.index(action["cell_id"])
                out.append(
                    Decision(
                        TURQUOISE_BONUS_OFFSET + idx,
                        [action, {"type": "confirm_move"}],
                        f"turquoise-bonus:{action['cell_id']}",
                    )
                )
            return out
        if color in ("yellow", "brown"):
            offset, cells = (YELLOW_OFFSET, YELLOW_CELLS) if color == "yellow" else (BROWN_OFFSET, BROWN_CELLS)
            out = []
            for action in picks:
                idx = cells.index(action["cell_id"])
                out.append(
                    Decision(offset + idx, [action, {"type": "confirm_move"}], f"bonus-{color}:{action['cell_id']}")
                )
            return out
    return []


def legal_action_mask(state: GameState) -> np.ndarray:
    """Boolean mask of shape ``(N_ACTIONS,)`` derived from the engine's legal actions."""
    mask = np.zeros(N_ACTIONS, dtype=np.int8)
    for decision in build_legal_decisions(state):
        mask[decision.action_id] = 1
    return mask


def decode(state: GameState, action_id: int) -> list[Action]:
    """RL id -> engine action sequence. Raises ``ValueError`` if the id is not legal."""
    if not (0 <= int(action_id) < N_ACTIONS):
        raise ValueError(f"action id {action_id} outside [0, {N_ACTIONS})")
    for decision in build_legal_decisions(state):
        if decision.action_id == int(action_id):
            return [dict(a) for a in decision.actions]
    raise ValueError(f"action id {action_id} ({label(action_id)}) is not legal in the current decision")


def encode(state: GameState, engine_action: Action) -> int | None:
    """Engine action -> RL id when the action heads a catalogue decision."""
    for decision in build_legal_decisions(state):
        if decision.actions and decision.actions[0] == engine_action:
            return decision.action_id
    return None


def label(action_id: int) -> str:
    """Human-readable label for debugging."""
    aid = int(action_id)
    sections = (
        (SELECT_DIE_OFFSET, SELECT_DIE_COUNT, "select_die", ALL_DIE_COLORS),
        (WHITE_COLOR_OFFSET, WHITE_COLOR_COUNT, "white_color", ACTING_COLORS),
        (YELLOW_OFFSET, YELLOW_COUNT, "dest_yellow", YELLOW_CELLS),
        (TURQUOISE_OFFSET, TURQUOISE_COUNT, "dest_turquoise", None),
        (BLUE_OFFSET, BLUE_COUNT, "dest_blue", BLUE_CELLS),
        (BROWN_OFFSET, BROWN_COUNT, "dest_brown", BROWN_CELLS),
        (PINK_OFFSET, PINK_COUNT, "dest_pink", PINK_CELLS),
        (PINK_OPTION_OFFSET, PINK_OPTION_COUNT, "pink_option", PINK_OPTIONS),
        (JOKER_VALUE_OFFSET, JOKER_VALUE_COUNT, "joker_value", tuple(range(1, 7))),
        (BONUS_COLOR_OFFSET, BONUS_COLOR_COUNT, "bonus_color", ACTING_COLORS),
        (BONUS_VALUE_OFFSET, BONUS_VALUE_COUNT, "bonus_value", tuple(range(1, 7))),
        (TURQUOISE_BONUS_OFFSET, TURQUOISE_BONUS_COUNT, "turquoise_bonus", TURQUOISE_BONUS_CELLS),
        (UTILITY_OFFSET, UTILITY_COUNT, "utility", UTILITY_KINDS),
        (FILL_SLOT_OFFSET, FILL_SLOT_COUNT, "fill_slot", ALL_DIE_COLORS),
    )
    for offset, count, name, values in sections:
        if offset <= aid < offset + count:
            if name == "dest_turquoise":
                subset = TURQUOISE_SUBSETS[aid - offset]
                return f"{name}:rows{''.join(map(str, subset))}"
            return f"{name}:{values[aid - offset]}"
    if BLUE_BONUS_OFFSET <= aid < BLUE_BONUS_OFFSET + BLUE_BONUS_COUNT:
        local = aid - BLUE_BONUS_OFFSET
        cell = local // BLUE_BONUS_VALUE_MAX + 1
        value = local % BLUE_BONUS_VALUE_MAX + 1
        return f"blue_bonus:{cell}={value}"
    return f"unknown:{aid}"
