"""Action catalogue 2.0 for :mod:`rl_env_2`.

Changes vs ``rl_env`` (316 ids):

* ``BLUE_BONUS_PLACE`` (cell x value) is split into two sequential decisions:
  ``BLUE_BONUS_CELL`` (12 cells, centre excluded) then ``BLUE_BONUS_VALUE`` (12).
* ``TURQUOISE_BONUS`` (30 cells) is split into ``TURQUOISE_BONUS_ROW`` (5) then
  ``TURQUOISE_BONUS_COL`` (6).
* ids that never appear in an agent decision are removed: ``DEST_PINK`` (the pink
  destination is always unique, hence auto-confirmed), ``blue-cell-7`` (never a
  destination nor a bonus cell), and the always-single utilities ``continue``,
  ``dismiss_impossible_bonus`` and ``pass_passive`` (auto-applied by the env).

The environment orchestrates the two-step decisions and only calls the engine
``place_bonus_blue`` / ``pick_cell``+``confirm_move`` at the end.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NamedTuple

import numpy as np

from game_engine.bonuses import PINK_MULTIPLIERS  # noqa: F401  (kept for API parity)
from game_engine.legal import legal_actions
from game_engine.types import ACTING_COLORS, ALL_DIE_COLORS, Action, GameState

ACTION_VERSION_2 = "2.0"

# --- id sections -----------------------------------------------------------

SELECT_DIE_OFFSET = 0
SELECT_DIE_COUNT = 6

WHITE_COLOR_OFFSET = 6
WHITE_COLOR_COUNT = 5

DEST_YELLOW_OFFSET = 11
YELLOW_CELLS = [f"yellow-r{r}-c{c}" for r in range(1, 4) for c in range(1, 7)]
YELLOW_COUNT = 18

DEST_TURQUOISE_OFFSET = 29
TURQUOISE_ROWS: tuple[int, ...] = (1, 2, 3, 4, 5)
TURQUOISE_SUBSETS: list[tuple[int, ...]] = [
    tuple(r for r in TURQUOISE_ROWS if mask & (1 << (r - 1))) for mask in range(1, 1 << len(TURQUOISE_ROWS))
]
TURQUOISE_COUNT = 31

BLUE_CELLS = [f"blue-cell-{p}" for p in range(1, 14)]
BLUE_CELLS_NO7 = [c for c in BLUE_CELLS if c != "blue-cell-7"]
DEST_BLUE_OFFSET = 60
DEST_BLUE_COUNT = len(BLUE_CELLS_NO7)  # 12

BROWN_CELLS = [f"brown-cell-{n}" for n in range(1, 13)]
DEST_BROWN_OFFSET = DEST_BLUE_OFFSET + DEST_BLUE_COUNT  # 72
DEST_BROWN_COUNT = 12

PINK_OPTION_OFFSET = DEST_BROWN_OFFSET + DEST_BROWN_COUNT  # 84
PINK_OPTIONS = ("points", "bonus")
PINK_OPTION_COUNT = 2

JOKER_VALUE_OFFSET = PINK_OPTION_OFFSET + PINK_OPTION_COUNT  # 86
JOKER_VALUE_COUNT = 6

BONUS_COLOR_OFFSET = JOKER_VALUE_OFFSET + JOKER_VALUE_COUNT  # 92
BONUS_COLOR_COUNT = 5

BONUS_VALUE_OFFSET = BONUS_COLOR_OFFSET + BONUS_COLOR_COUNT  # 97
BONUS_VALUE_COUNT = 6
BONUS_VALUE_MAX = 6

BLUE_BONUS_CELL_OFFSET = BONUS_VALUE_OFFSET + BONUS_VALUE_COUNT  # 103
BLUE_BONUS_CELL_COUNT = len(BLUE_CELLS_NO7)  # 12

BLUE_BONUS_VALUE_OFFSET = BLUE_BONUS_CELL_OFFSET + BLUE_BONUS_CELL_COUNT  # 115
BLUE_BONUS_VALUE_MAX = 12
BLUE_BONUS_VALUE_COUNT = 12

TURQUOISE_BONUS_ROW_OFFSET = BLUE_BONUS_VALUE_OFFSET + BLUE_BONUS_VALUE_COUNT  # 127
TURQUOISE_BONUS_ROW_COUNT = 5

TURQUOISE_BONUS_COL_OFFSET = TURQUOISE_BONUS_ROW_OFFSET + TURQUOISE_BONUS_ROW_COUNT  # 132
TURQUOISE_BONUS_COL_COUNT = 6

UTILITY_OFFSET = TURQUOISE_BONUS_COL_OFFSET + TURQUOISE_BONUS_COL_COUNT  # 138
UTILITY_KINDS = ("use_relance", "start_joker", "begin_plus1", "skip_plus1", "end_active_early")
UTILITY_COUNT = len(UTILITY_KINDS)  # 5

FILL_SLOT_OFFSET = UTILITY_OFFSET + UTILITY_COUNT  # 143
FILL_SLOT_COUNT = 6

N_ACTIONS_2 = FILL_SLOT_OFFSET + FILL_SLOT_COUNT  # 149

_UTILITY_INDEX = {name: i for i, name in enumerate(UTILITY_KINDS)}
_DEST_LAYOUT = {
    "yellow": (DEST_YELLOW_OFFSET, YELLOW_CELLS),
    "darkblue": (DEST_BLUE_OFFSET, BLUE_CELLS_NO7),
    "brown": (DEST_BROWN_OFFSET, BROWN_CELLS),
}


@dataclass(frozen=True)
class Pending:
    """Intermediate state of a factorised decision (held by the environment)."""

    blue_cell: int | None = None
    turquoise_row: int | None = None


class Decision(NamedTuple):
    action_id: int
    actions: list[Action]
    label: str


def _turquoise_row(cell_id: str) -> int:
    return int(cell_id.split("-")[1][1:])


def _turquoise_col(cell_id: str) -> int:
    return int(cell_id.rsplit("-c", 1)[1])


def _blue_cell(cell_id: str) -> int:
    return int(cell_id.rsplit("-", 1)[1])


def build_legal_decisions(state: GameState, pending: Pending = Pending()) -> list[Decision]:
    """Enumerate catalogue 2.0 decisions legal in ``state`` for the current agent decision."""
    legal = legal_actions(state)
    if not legal:
        return []
    if pending.blue_cell is not None:
        return _blue_bonus_value_decisions(pending.blue_cell, legal)
    if pending.turquoise_row is not None:
        return _turquoise_bonus_col_decisions(pending.turquoise_row, legal)
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
        if action["type"] == "choose_pink_option":
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
        elif action["type"] in ("use_relance", "start_joker", "end_active_early"):
            out.append(Decision(UTILITY_OFFSET + _UTILITY_INDEX[action["type"]], [action], action["type"]))
    return out


def _fill_slot_decisions(legal: list[Action]) -> list[Decision]:
    out: list[Decision] = []
    for action in legal:
        if action["type"] == "fill_slot_dummy":
            idx = ALL_DIE_COLORS.index(action["color"])
            out.append(Decision(FILL_SLOT_OFFSET + idx, [action], f"fill:{action['color']}"))
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
        return []
    if acting == "turquoise":
        return _turquoise_decisions(sel, picks)
    offset, cells = _DEST_LAYOUT[acting]
    out: list[Decision] = []
    for action in picks:
        out.append(
            Decision(
                offset + cells.index(action["cell_id"]),
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
        out.append(Decision(DEST_TURQUOISE_OFFSET + idx, actions, f"turquoise:rows{''.join(map(str, subset))}@c{column}"))
    return out


def _joker_decisions(state: GameState, legal: list[Action]) -> list[Decision]:
    jp = state["joker_pending"]
    assert jp is not None
    if jp.get("value") is None:
        out: list[Decision] = []
        for action in legal:
            if action["type"] == "set_joker_value":
                out.append(Decision(JOKER_VALUE_OFFSET + action["value"] - 1, [action], f"joker-value:{action['value']}"))
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
                out.append(Decision(BONUS_COLOR_OFFSET + ACTING_COLORS.index(action["color"]), [action], f"bonus-color:{action['color']}"))
        return out
    if stage == "chooseValue":
        out = []
        for action in legal:
            if action["type"] == "choose_bonus_value":
                out.append(Decision(BONUS_VALUE_OFFSET + action["value"] - 1, [action], f"bonus-value:{action['value']}"))
        return out
    if stage == "placing" and color == "darkblue":
        # Step 1 of the factorised blue bonus: choose a legal cell.
        cells: list[int] = []
        for action in legal:
            if action["type"] == "place_bonus_blue":
                cell = _blue_cell(action["cell_id"])
                if cell not in cells:
                    cells.append(cell)
        out = []
        for cell in sorted(cells):
            out.append(Decision(BLUE_BONUS_CELL_OFFSET + BLUE_CELLS_NO7.index(f"blue-cell-{cell}"), [], f"blue-bonus-cell:{cell}"))
        return out
    if stage == "placing":
        picks = [a for a in legal if a["type"] == "pick_cell"]
        if color == "turquoise":
            # Step 1 of the factorised turquoise bonus: choose a row.
            rows = sorted({_turquoise_row(a["cell_id"]) for a in picks})
            return [
                Decision(TURQUOISE_BONUS_ROW_OFFSET + (row - 1), [], f"turquoise-bonus-row:{row}") for row in rows
            ]
        if color in ("yellow", "brown"):
            offset, cells = (DEST_YELLOW_OFFSET, YELLOW_CELLS) if color == "yellow" else (DEST_BROWN_OFFSET, BROWN_CELLS)
            out = []
            for action in picks:
                out.append(Decision(offset + cells.index(action["cell_id"]), [action, {"type": "confirm_move"}], f"bonus-{color}:{action['cell_id']}"))
            return out
    return []


def _blue_bonus_value_decisions(cell: int, legal: list[Action]) -> list[Decision]:
    out: list[Decision] = []
    for action in legal:
        if action["type"] != "place_bonus_blue" or _blue_cell(action["cell_id"]) != cell:
            continue
        value = int(action["value"])
        if not (1 <= value <= BLUE_BONUS_VALUE_MAX):
            raise ValueError(f"blue bonus value out of range: {action}")
        out.append(Decision(BLUE_BONUS_VALUE_OFFSET + value - 1, [action], f"blue-bonus-value:{cell}={value}"))
    return out


def _turquoise_bonus_col_decisions(row: int, legal: list[Action]) -> list[Decision]:
    out: list[Decision] = []
    for action in legal:
        if action["type"] != "pick_cell" or _turquoise_row(action["cell_id"]) != row:
            continue
        col = _turquoise_col(action["cell_id"])
        out.append(
            Decision(
                TURQUOISE_BONUS_COL_OFFSET + (col - 1),
                [action, {"type": "confirm_move"}],
                f"turquoise-bonus-col:r{row}c{col}",
            )
        )
    return out


def legal_action_mask(state: GameState, pending: Pending = Pending()) -> np.ndarray:
    mask = np.zeros(N_ACTIONS_2, dtype=np.int8)
    for decision in build_legal_decisions(state, pending):
        mask[decision.action_id] = 1
    return mask


def decode(state: GameState, action_id: int, pending: Pending = Pending()) -> list[Action]:
    """RL id -> engine action sequence (empty for a step-1 factorised id)."""
    if not (0 <= int(action_id) < N_ACTIONS_2):
        raise ValueError(f"action id {action_id} outside [0, {N_ACTIONS_2})")
    for decision in build_legal_decisions(state, pending):
        if decision.action_id == int(action_id):
            return [dict(a) for a in decision.actions]
    raise ValueError(f"action id {action_id} ({label(action_id)}) is not legal in the current decision")


def encode(state: GameState, engine_action: Action | list[Action], pending: Pending = Pending()) -> int | None:
    """Engine action (or full sequence) -> RL id. Exact-sequence match first."""
    wanted = engine_action if isinstance(engine_action, list) else [engine_action]
    decisions = build_legal_decisions(state, pending)
    for decision in decisions:
        if decision.actions and decision.actions == wanted:
            return decision.action_id
    for decision in decisions:
        if decision.actions and decision.actions[0] == wanted[0]:
            return decision.action_id
    return None


def label(action_id: int) -> str:
    aid = int(action_id)
    sections = (
        (SELECT_DIE_OFFSET, SELECT_DIE_COUNT, "select_die", ALL_DIE_COLORS),
        (WHITE_COLOR_OFFSET, WHITE_COLOR_COUNT, "white_color", ACTING_COLORS),
        (DEST_YELLOW_OFFSET, YELLOW_COUNT, "dest_yellow", YELLOW_CELLS),
        (DEST_TURQUOISE_OFFSET, TURQUOISE_COUNT, "dest_turquoise", None),
        (DEST_BLUE_OFFSET, DEST_BLUE_COUNT, "dest_blue", BLUE_CELLS_NO7),
        (DEST_BROWN_OFFSET, DEST_BROWN_COUNT, "dest_brown", BROWN_CELLS),
        (PINK_OPTION_OFFSET, PINK_OPTION_COUNT, "pink_option", PINK_OPTIONS),
        (JOKER_VALUE_OFFSET, JOKER_VALUE_COUNT, "joker_value", tuple(range(1, 7))),
        (BONUS_COLOR_OFFSET, BONUS_COLOR_COUNT, "bonus_color", ACTING_COLORS),
        (BONUS_VALUE_OFFSET, BONUS_VALUE_COUNT, "bonus_value", tuple(range(1, 7))),
        (BLUE_BONUS_CELL_OFFSET, BLUE_BONUS_CELL_COUNT, "blue_bonus_cell", BLUE_CELLS_NO7),
        (BLUE_BONUS_VALUE_OFFSET, BLUE_BONUS_VALUE_COUNT, "blue_bonus_value", tuple(range(1, 13))),
        (TURQUOISE_BONUS_ROW_OFFSET, TURQUOISE_BONUS_ROW_COUNT, "turquoise_bonus_row", TURQUOISE_ROWS),
        (TURQUOISE_BONUS_COL_OFFSET, TURQUOISE_BONUS_COL_COUNT, "turquoise_bonus_col", tuple(range(1, 7))),
        (UTILITY_OFFSET, UTILITY_COUNT, "utility", UTILITY_KINDS),
        (FILL_SLOT_OFFSET, FILL_SLOT_COUNT, "fill_slot", ALL_DIE_COLORS),
    )
    for offset, count, name, values in sections:
        if offset <= aid < offset + count:
            if name == "dest_turquoise":
                return f"{name}:rows{''.join(map(str, TURQUOISE_SUBSETS[aid - offset]))}"
            return f"{name}:{values[aid - offset]}"
    return f"unknown:{aid}"
