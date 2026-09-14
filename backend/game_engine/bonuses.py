"""Bonus catalog, unlock detection, and counter tracks (capacity 7)."""

from __future__ import annotations

from typing import Any, Callable

from .types import BonusDieColor, BonusState, CumulativeBonus, PlayerBoard

BonusEffect = dict[str, Any]

relance: BonusEffect = {"kind": "cumulative", "bonus": "relance"}
joker: BonusEffect = {"kind": "cumulative", "bonus": "joker"}
plus1: BonusEffect = {"kind": "cumulative", "bonus": "plus1"}
none: BonusEffect = {"kind": "none"}
fox: BonusEffect = {"kind": "fox"}


def die(color: BonusDieColor) -> BonusEffect:
    return {"kind": "die", "color": color}


FOX_SLOT_IDS: tuple[str, ...] = (
    "gold-r1-c6",
    "turqRow-1",
    "blue-13",
    "brownGap-11-12",
    "pink-9",
    "counter-relance-all",
)

NUMBERED_JOKERS = 4
WILD_JOKERS = 3

TURQUOISE_DARK_COUNT = [6, 5, 3, 2, 1]


def is_turquoise_dark(row: int, col: int) -> bool:
    return col <= TURQUOISE_DARK_COUNT[row - 1]


def joker_token_value(index: int) -> int | None:
    numbered = [3, 4, 5, 6]
    return numbered[index] if index < NUMBERED_JOKERS else None


def joker_token_label(index: int) -> str:
    v = joker_token_value(index)
    return "?" if v is None else str(v)


GOLD_ROW1: list[BonusEffect] = [relance, joker, die("pink"), plus1, die("turquoise"), fox]
GOLD_ROW2: list[BonusEffect] = [
    joker,
    die("turquoise"),
    die("darkblue"),
    die("brown"),
    die("yellow"),
    plus1,
]
TURQ_ROW: list[BonusEffect] = [fox, plus1, die("brown"), die("turquoise"), none]
TURQ_COL: list[BonusEffect] = [
    die("brown"),
    die("pink"),
    die("yellow"),
    joker,
    die("darkblue"),
    relance,
]
BLUE_BONUS: dict[int, BonusEffect] = {
    1: plus1,
    2: die("pink"),
    4: die("yellow"),
    5: joker,
    9: relance,
    10: die("brown"),
    12: die("turquoise"),
    13: fox,
}
BROWN_GAPS: list[dict[str, Any]] = [
    {"left": 1, "right": 2, "effect": joker},
    {"left": 2, "right": 3, "effect": die("pink")},
    {"left": 4, "right": 5, "effect": relance},
    {"left": 5, "right": 6, "effect": die("turquoise")},
    {"left": 7, "right": 8, "effect": plus1},
    {"left": 8, "right": 9, "effect": die("darkblue")},
    {"left": 10, "right": 11, "effect": die("yellow")},
    {"left": 11, "right": 12, "effect": fox},
]
TURN_BONUS: dict[int, BonusEffect] = {
    1: relance,
    2: plus1,
    3: joker,
    4: die("black"),
}
PINK_MULTIPLIERS = [0, 1, 2, 2, 1, 2, 2, 1, 3, 2, 2, 3]
PINK_BONUSES: list[BonusEffect] = [
    none,
    relance,
    die("darkblue"),
    plus1,
    joker,
    die("yellow"),
    die("brown"),
    relance,
    fox,
    die("darkblue"),
    die("turquoise"),
    die("black"),
]


class SlotDef:
    __slots__ = ("slot_id", "source", "effect", "predicate", "meta")

    def __init__(
        self,
        slot_id: str,
        source: str,
        effect: BonusEffect,
        predicate: Callable[[PlayerBoard], bool],
        meta: dict[str, int],
    ) -> None:
        self.slot_id = slot_id
        self.source = source
        self.effect = effect
        self.predicate = predicate
        self.meta = meta


def _gold_slots() -> list[SlotDef]:
    slots: list[SlotDef] = []
    for between_row, effects in ((1, GOLD_ROW1), (2, GOLD_ROW2)):
        for i, effect in enumerate(effects):
            col = i + 1
            above = f"yellow-r{between_row}-c{col}"
            below = f"yellow-r{between_row + 1}-c{col}"
            slots.append(
                SlotDef(
                    f"gold-r{between_row}-c{col}",
                    "gold",
                    effect,
                    lambda b, a=above, d=below: bool(b["checks"].get(a) and b["checks"].get(d)),
                    {"betweenRow": between_row, "col": col},
                )
            )
    return slots


def _turquoise_row_slots() -> list[SlotDef]:
    out: list[SlotDef] = []
    for i, effect in enumerate(TURQ_ROW):
        row = i + 1
        count = TURQUOISE_DARK_COUNT[row - 1]
        cells = [f"turquoise-r{row}-c{c + 1}" for c in range(count)]
        out.append(
            SlotDef(
                f"turqRow-{row}",
                "turqRow",
                effect,
                lambda b, ids=tuple(cells): all(b["checks"].get(cid) for cid in ids),
                {"row": row},
            )
        )
    return out


def _turquoise_col_slots() -> list[SlotDef]:
    out: list[SlotDef] = []
    for i, effect in enumerate(TURQ_COL):
        col = i + 1
        rows = [
            f"turquoise-r{r}-c{col}"
            for r in range(1, len(TURQUOISE_DARK_COUNT) + 1)
            if is_turquoise_dark(r, col)
        ]
        out.append(
            SlotDef(
                f"turqCol-{col}",
                "turqCol",
                effect,
                lambda b, ids=tuple(rows): all(b["checks"].get(cid) for cid in ids),
                {"col": col},
            )
        )
    return out


def _blue_slots() -> list[SlotDef]:
    out: list[SlotDef] = []
    for pos, effect in BLUE_BONUS.items():
        out.append(
            SlotDef(
                f"blue-{pos}",
                "blue",
                effect,
                lambda b, p=pos: b["values"].get(f"blue-cell-{p}") is not None,
                {"pos": pos},
            )
        )
    return out


def _brown_gap_slots() -> list[SlotDef]:
    out: list[SlotDef] = []
    for g in BROWN_GAPS:
        left, right, effect = g["left"], g["right"], g["effect"]
        out.append(
            SlotDef(
                f"brownGap-{left}-{right}",
                "brownGap",
                effect,
                lambda b, l=left, r=right: bool(
                    b["checks"].get(f"brown-cell-{l}") and b["checks"].get(f"brown-cell-{r}")
                ),
                {"left": left, "right": right},
            )
        )
    return out


def _turn_slots() -> list[SlotDef]:
    out: list[SlotDef] = []
    for n, effect in TURN_BONUS.items():
        out.append(
            SlotDef(
                f"turn-{n}",
                "turn",
                effect,
                lambda b, tid=f"turn-{n}": bool(b["checks"].get(tid)),
                {"n": n},
            )
        )
    return out


def _all_catalog_effects() -> list[BonusEffect]:
    return [
        *GOLD_ROW1,
        *GOLD_ROW2,
        *TURQ_ROW,
        *TURQ_COL,
        *BLUE_BONUS.values(),
        *[g["effect"] for g in BROWN_GAPS],
        *TURN_BONUS.values(),
        *PINK_BONUSES,
    ]


def _count_cumulative(bonus: CumulativeBonus) -> int:
    return sum(
        1 for e in _all_catalog_effects() if e.get("kind") == "cumulative" and e.get("bonus") == bonus
    )


TOTAL_RELANCE = _count_cumulative("relance")
TOTAL_JOKERS = _count_cumulative("joker")
TOTAL_PLUS1 = _count_cumulative("plus1")


def _counter_slots() -> list[SlotDef]:
    return [
        SlotDef(
            "counter-relance-all",
            "counter",
            fox,
            lambda b: b["bonuses"]["relance"]["unlocked"] >= TOTAL_RELANCE,
            {},
        ),
        SlotDef(
            "counter-joker-all",
            "counter",
            die("brown"),
            lambda b: b["bonuses"]["joker"]["unlocked"] >= TOTAL_JOKERS,
            {},
        ),
        SlotDef(
            "counter-plus1-all",
            "counter",
            die("pink"),
            lambda b: b["bonuses"]["plus1"]["unlocked"] >= TOTAL_PLUS1,
            {},
        ),
    ]


def _pink_slots() -> list[SlotDef]:
    return [
        SlotDef(
            f"pink-{i + 1}",
            "pink",
            effect,
            lambda _b: False,
            {"n": i + 1, "multiplier": PINK_MULTIPLIERS[i]},
        )
        for i, effect in enumerate(PINK_BONUSES)
    ]


ALL_SLOTS: list[SlotDef] = [
    *_turn_slots(),
    *_gold_slots(),
    *_turquoise_row_slots(),
    *_turquoise_col_slots(),
    *_blue_slots(),
    *_brown_gap_slots(),
    *_counter_slots(),
    *_pink_slots(),
]


def slots_by_source(source: str) -> list[SlotDef]:
    return [s for s in ALL_SLOTS if s.source == source]


def empty_bonus_state() -> BonusState:
    return {
        "relance": {"unlocked": 0, "used": 0},
        "plus1": {"unlocked": 0, "used": 0},
        "joker": {"unlocked": 0, "used": 0},
        "slots_unlocked": {},
    }


def _apply_effect(bonuses: BonusState, effect: BonusEffect) -> BonusState:
    if effect.get("kind") == "cumulative":
        bonus = effect["bonus"]
        tally = bonuses[bonus]
        return {
            **bonuses,
            bonus: {**tally, "unlocked": tally["unlocked"] + 1},
        }
    return bonuses


def apply_unlocks(board: PlayerBoard) -> tuple[PlayerBoard, list[BonusDieColor]]:
    """Idempotent fixpoint: newly satisfied slots fire once, in catalog order."""
    bonuses = board["bonuses"]
    working: PlayerBoard = board
    die_bonuses: list[BonusDieColor] = []
    changed = True
    while changed:
        changed = False
        for slot in ALL_SLOTS:
            if bonuses["slots_unlocked"].get(slot.slot_id):
                continue
            if not slot.predicate(working):
                continue
            bonuses = {
                **_apply_effect(bonuses, slot.effect),
                "slots_unlocked": {**bonuses["slots_unlocked"], slot.slot_id: True},
            }
            working = {**working, "bonuses": bonuses}
            if slot.effect.get("kind") == "die":
                die_bonuses.append(slot.effect["color"])
            changed = True
    return working, die_bonuses
