"""Core types and constants for the Très Futé engine (REGLES v1.1)."""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict

DieColor = Literal["yellow", "turquoise", "darkblue", "brown", "pink", "white"]
ActingColor = Literal["yellow", "turquoise", "darkblue", "brown", "pink"]
DiceLocation = Literal["available", "chosen", "discarded"]
CumulativeBonus = Literal["relance", "joker", "plus1"]
BonusDieColor = Literal["yellow", "turquoise", "darkblue", "brown", "pink", "black"]
PlayerId = Literal[1, 2]
PinkOption = Literal["points", "bonus"]

ACTING_COLORS: tuple[ActingColor, ...] = (
    "yellow",
    "turquoise",
    "darkblue",
    "brown",
    "pink",
)
ALL_DIE_COLORS: tuple[DieColor, ...] = (
    "yellow",
    "turquoise",
    "darkblue",
    "brown",
    "pink",
    "white",
)
BONUS_DIE_COLORS: tuple[BonusDieColor, ...] = (
    "yellow",
    "turquoise",
    "darkblue",
    "brown",
    "pink",
    "black",
)
PLAYER_IDS: tuple[PlayerId, ...] = (1, 2)

BROWN_NUMBERS: tuple[int, ...] = (1, 5, 3, 4, 2, 6, 4, 5, 2, 1, 6, 3)

RULES_VERSION = "1.1"


def other_player(player: PlayerId) -> PlayerId:
    return 2 if player == 1 else 1


def empty_plus1_used_dice() -> dict[PlayerId, list[DieColor]]:
    return {1: [], 2: []}


class DieRuntime(TypedDict):
    value: int
    location: DiceLocation
    joker_value: NotRequired[int | None]


def effective_value(die: DieRuntime | dict[str, Any]) -> int:
    jv = die.get("joker_value")
    return int(jv) if jv is not None else int(die["value"])


class BonusTally(TypedDict):
    unlocked: int
    used: int


class BonusState(TypedDict):
    relance: BonusTally
    plus1: BonusTally
    joker: BonusTally
    slots_unlocked: dict[str, bool]


class ChosenDie(TypedDict):
    color: DieColor
    value: int


class PlayerBoard(TypedDict):
    checks: dict[str, bool]
    values: dict[str, int]
    brown_last_checked: int | None
    brown_disabled: dict[str, bool]
    chosen_this_turn: list[ChosenDie]
    slots: list[ChosenDie | None]
    bonuses: BonusState


class Selection(TypedDict):
    color: DieColor
    value: int
    acting_color: ActingColor | None
    legal: list[str]
    picked: list[str]
    max_pick: int
    elimination_value: int


class PendingBonus(TypedDict):
    owner: PlayerId
    color: BonusDieColor


class BonusResolution(TypedDict):
    owner: PlayerId
    origin_color: BonusDieColor
    color: BonusDieColor
    stage: Literal["chooseColor", "chooseValue", "placing", "noMove"]
    value: int | None


class PinkChoice(TypedDict):
    owner: PlayerId
    cell_id: str
    position: int
    effective_value: int
    multiplier: int
    bonus_slot_id: str | None
    bonus_effect: dict[str, Any]
    resume: dict[str, Any]


class GameState(TypedDict):
    global_turn: int
    phase: dict[str, Any]
    boards: dict[PlayerId, PlayerBoard]
    dice: dict[DieColor, DieRuntime]
    selection: Selection | None
    message: str | None
    plus1_active: PlayerId | None
    plus1_used_dice: dict[PlayerId, list[DieColor]]
    joker_pending: dict[str, Any] | None
    pending_bonuses: list[PendingBonus]
    bonus_resolution: BonusResolution | None
    pink_choice: PinkChoice | None
    pending_advance: dict[str, Any] | None


Action = dict[str, Any]
Event = dict[str, Any]
