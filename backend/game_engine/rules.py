"""Pure legal-destination helpers. Never mutate state. Never roll dice."""

from __future__ import annotations

import math
from typing import Any, Literal, TypedDict

from .types import (
    ACTING_COLORS,
    ALL_DIE_COLORS,
    BROWN_NUMBERS,
    ActingColor,
    DieColor,
    DieRuntime,
    GameState,
    PlayerBoard,
    PlayerId,
    effective_value,
)

TURQUOISE_ROWS = [1, 2, 3, 4, 5]
BLUE_RIGHT = [8, 9, 10, 11, 12, 13]
BLUE_LEFT = [6, 5, 4, 3, 2, 1]

PASSIVE_YELLOW_CELL: dict[int, str] = {
    1: "yellow-r3-c1",
    2: "yellow-r3-c2",
    3: "yellow-r2-c3",
    4: "yellow-r2-c4",
    5: "yellow-r1-c5",
    6: "yellow-r1-c6",
}
PASSIVE_YELLOW_CELLS: list[str] = list(PASSIVE_YELLOW_CELL.values())


class LegalResult(TypedDict):
    legal: list[str]
    max_pick: int


class MoveContext(TypedDict):
    mode: Literal["active", "passive"]
    board: PlayerBoard
    dice: dict[DieColor, DieRuntime]
    round: int
    selected_color: DieColor


class BlueBonusOption(TypedDict):
    cell_id: str
    value: int


def blue_sum(dice: dict[DieColor, DieRuntime]) -> int:
    return effective_value(dice["darkblue"]) + effective_value(dice["white"])


def _branch_info(values: dict[str, int], positions: list[int]) -> tuple[str | None, int]:
    ref = 7
    next_free: str | None = None
    for p in positions:
        cell_id = f"blue-cell-{p}"
        if cell_id in values:
            ref = values[cell_id]
        else:
            next_free = cell_id
            break
    return next_free, ref


def legal_blue(ctx: MoveContext) -> list[str]:
    total = blue_sum(ctx["dice"])
    values = ctx["board"]["values"]
    legal: list[str] = []
    next_free, ref = _branch_info(values, BLUE_RIGHT)
    if next_free and (total == ref + 1 or total == 7):
        legal.append(next_free)
    next_free, ref = _branch_info(values, BLUE_LEFT)
    if next_free and (total == ref - 1 or total == 7):
        legal.append(next_free)
    return legal


def first_empty_pink(values: dict[str, int]) -> str | None:
    for n in range(1, 13):
        cell_id = f"pink-cell-{n}"
        if cell_id not in values:
            return cell_id
    return None


def turquoise_companion_count(ctx: MoveContext, value: int) -> int:
    """Number of dice sharing ``value`` with the selected die in the turquoise group.

    Active games count ``chosen_this_turn``; passive / +1 games count dice sharing the
    selected die's location (grey square or slot). The selected die is never its own
    companion. This is the engine's own turquoise grouping, exposed for the policy.
    """
    if ctx["mode"] == "passive":
        group = ctx["dice"][ctx["selected_color"]]["location"]
        return sum(
            1
            for c in ALL_DIE_COLORS
            if c != ctx["selected_color"]
            and ctx["dice"][c]["location"] == group
            and effective_value(ctx["dice"][c]) == value
        )
    return sum(1 for d in ctx["board"]["chosen_this_turn"] if d["value"] == value)


def legal_destinations(acting_color: ActingColor, value: int, ctx: MoveContext) -> LegalResult:
    board = ctx["board"]
    if acting_color == "yellow":
        cell_id = (
            PASSIVE_YELLOW_CELL.get(value)
            if ctx["mode"] == "passive"
            else f"yellow-r{ctx['round']}-c{value}"
        )
        legal = [cell_id] if cell_id and not board["checks"].get(cell_id) else []
        return {"legal": legal, "max_pick": 1}
    if acting_color == "turquoise":
        free = [
            f"turquoise-r{r}-c{value}"
            for r in TURQUOISE_ROWS
            if not board["checks"].get(f"turquoise-r{r}-c{value}")
        ]
        same_value = turquoise_companion_count(ctx, value)
        cap = 1 + same_value
        return {"legal": free, "max_pick": min(cap, len(free))}
    if acting_color == "pink":
        target = first_empty_pink(board["values"])
        return {"legal": [target] if target else [], "max_pick": 1}
    if acting_color == "darkblue":
        return {"legal": legal_blue(ctx), "max_pick": 1}
    if acting_color == "brown":
        start = board["brown_last_checked"] or 0
        legal: list[str] = []
        for i, printed in enumerate(BROWN_NUMBERS):
            n = i + 1
            if n <= start:
                continue
            cell_id = f"brown-cell-{n}"
            if printed == value and not board["checks"].get(cell_id):
                legal.append(cell_id)
        return {"legal": legal, "max_pick": 1}
    return {"legal": [], "max_pick": 1}


def pink_value(die_value: int) -> int:
    return math.ceil(die_value / 2)


def pink_points(eff: int, multiplier: int) -> int:
    return eff * multiplier


def bonus_yellow_legal(board: PlayerBoard, value: int) -> list[str]:
    return [f"yellow-r{r}-c{value}" for r in range(1, 4) if not board["checks"].get(f"yellow-r{r}-c{value}")]


def all_unchecked_turquoise(board: PlayerBoard) -> list[str]:
    legal: list[str] = []
    for r in TURQUOISE_ROWS:
        for c in range(1, 7):
            cell_id = f"turquoise-r{r}-c{c}"
            if not board["checks"].get(cell_id):
                legal.append(cell_id)
    return legal


def bonus_brown_legal(board: PlayerBoard, value: int) -> list[str]:
    start = board["brown_last_checked"] or 0
    legal: list[str] = []
    for i, printed in enumerate(BROWN_NUMBERS):
        n = i + 1
        if n <= start:
            continue
        cell_id = f"brown-cell-{n}"
        if printed == value and not board["checks"].get(cell_id):
            legal.append(cell_id)
    return legal


def blue_bonus_options(board: PlayerBoard) -> list[BlueBonusOption]:
    values = board["values"]
    options: list[BlueBonusOption] = []

    def push(cell_id: str | None, value: int) -> None:
        if not cell_id or value < 1:
            return
        if any(o["cell_id"] == cell_id and o["value"] == value for o in options):
            return
        options.append({"cell_id": cell_id, "value": value})

    next_free, ref = _branch_info(values, BLUE_LEFT)
    push(next_free, ref - 1)
    push(next_free, 7)
    next_free, ref = _branch_info(values, BLUE_RIGHT)
    push(next_free, ref + 1)
    push(next_free, 7)
    return options


def bonus_has_any_placeable_value(board: PlayerBoard, color: Literal["yellow", "brown", "pink"]) -> bool:
    if color == "pink":
        return first_empty_pink(board["values"]) is not None
    return any(
        len(bonus_yellow_legal(board, v) if color == "yellow" else bonus_brown_legal(board, v)) > 0
        for v in range(1, 7)
    )


def color_availability(value: int, ctx: MoveContext) -> dict[ActingColor, bool]:
    return {c: len(legal_destinations(c, value, ctx)["legal"]) > 0 for c in ACTING_COLORS}


def die_has_any_legal_move(color: DieColor, ctx: MoveContext) -> bool:
    value = effective_value(ctx["dice"][color])
    local: MoveContext = {**ctx, "selected_color": color}
    if color == "white":
        return any(len(legal_destinations(c, value, local)["legal"]) > 0 for c in ACTING_COLORS)
    return len(legal_destinations(color, value, local)["legal"]) > 0  # type: ignore[arg-type]


def active_context(state: GameState, player: int, round_n: int, selected_color: DieColor) -> MoveContext:
    return {
        "mode": "active",
        "board": state["boards"][player],  # type: ignore[index]
        "dice": state["dice"],
        "round": round_n,
        "selected_color": selected_color,
    }


def passive_context(state: GameState, player: int, selected_color: DieColor) -> MoveContext:
    return {
        "mode": "passive",
        "board": state["boards"][player],  # type: ignore[index]
        "dice": state["dice"],
        "round": 0,
        "selected_color": selected_color,
    }


def any_available_die_has_move(state: GameState, player: int, round_n: int) -> bool:
    return any(
        state["dice"][c]["location"] == "available"
        and die_has_any_legal_move(c, active_context(state, player, round_n, c))
        for c in ALL_DIE_COLORS
    )


def any_discarded_die_has_move(state: GameState, player: int) -> bool:
    return any(
        state["dice"][c]["location"] == "discarded"
        and die_has_any_legal_move(c, passive_context(state, player, c))
        for c in ALL_DIE_COLORS
    )


def any_chosen_die_has_move(state: GameState, player: int) -> bool:
    return any(
        state["dice"][c]["location"] == "chosen"
        and die_has_any_legal_move(c, passive_context(state, player, c))
        for c in ALL_DIE_COLORS
    )


def any_die_has_passive_move(state: GameState, player: int) -> bool:
    return any_discarded_die_has_move(state, player) or any_chosen_die_has_move(state, player)
