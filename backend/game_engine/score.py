"""Pure scores from checks / values / slotsUnlocked. Never a running total."""

from __future__ import annotations

from typing import TypedDict

from .bonuses import FOX_SLOT_IDS
from .types import PlayerBoard

YELLOW_ROW = [0, 2, 6, 12, 20, 30, 42]
TURQUOISE_ROW = [0, 1, 3, 6, 10, 15, 21]
BLUE_BRANCH = [0, 3, 6, 9, 13, 17, 22]
BROWN_TOTAL = [0, 3, 5, 9, 14, 20, 27, 35, 44, 54, 65, 77, 90]
BLUE_LEFT = [6, 5, 4, 3, 2, 1]
BLUE_RIGHT = [8, 9, 10, 11, 12, 13]
BLUE_SPECIAL = {2, 3, 4, 10, 11, 12}


class PlayerScore(TypedDict):
    yellow: int
    turquoise: int
    blue: int
    brown: int
    pink: int
    color_subtotal: int
    fox_count: int
    fox_value: int
    fox_points: int
    total: int


def _yellow_score(board: PlayerBoard) -> int:
    total = 0
    for r in range(1, 4):
        n = sum(1 for c in range(1, 7) if board["checks"].get(f"yellow-r{r}-c{c}"))
        total += YELLOW_ROW[n]
    return total


def _turquoise_score(board: PlayerBoard) -> int:
    total = 0
    for r in range(1, 6):
        n = sum(1 for c in range(1, 7) if board["checks"].get(f"turquoise-r{r}-c{c}"))
        total += TURQUOISE_ROW[n]
    return total


def _count_filled(board: PlayerBoard, positions: list[int]) -> int:
    return sum(1 for p in positions if f"blue-cell-{p}" in board["values"])


def _blue_score(board: PlayerBoard) -> int:
    left = BLUE_BRANCH[_count_filled(board, BLUE_LEFT)]
    right = BLUE_BRANCH[_count_filled(board, BLUE_RIGHT)]
    specials = 0
    for p in [*BLUE_LEFT, *BLUE_RIGHT]:
        v = board["values"].get(f"blue-cell-{p}")
        if v is not None and v in BLUE_SPECIAL:
            specials += 1
    return left + right + 4 * specials


def _brown_score(board: PlayerBoard) -> int:
    n = sum(1 for i in range(1, 13) if board["checks"].get(f"brown-cell-{i}"))
    return BROWN_TOTAL[n]


def _pink_score(board: PlayerBoard) -> int:
    return sum(board["values"][f"pink-cell-{i}"] for i in range(1, 13) if f"pink-cell-{i}" in board["values"])


def _fox_count(board: PlayerBoard) -> int:
    return sum(1 for sid in FOX_SLOT_IDS if board["bonuses"]["slots_unlocked"].get(sid))


def compute_score(board: PlayerBoard) -> PlayerScore:
    yellow = _yellow_score(board)
    turquoise = _turquoise_score(board)
    blue = _blue_score(board)
    brown = _brown_score(board)
    pink = _pink_score(board)
    color_subtotal = yellow + turquoise + blue + brown + pink
    foxes = _fox_count(board)
    fox_value = min(yellow, turquoise, blue, brown, pink)
    fox_points = foxes * fox_value
    return {
        "yellow": yellow,
        "turquoise": turquoise,
        "blue": blue,
        "brown": brown,
        "pink": pink,
        "color_subtotal": color_subtotal,
        "fox_count": foxes,
        "fox_value": fox_value,
        "fox_points": fox_points,
        "total": color_subtotal + fox_points,
    }
