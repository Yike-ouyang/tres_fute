"""JSON view of engine state (camelCase for the React client). RNG internals are never exposed."""

from __future__ import annotations

from typing import Any

from .legal import current_decision, legal_actions
from .rules import (
    any_available_die_has_move,
    any_chosen_die_has_move,
    any_die_has_passive_move,
    any_discarded_die_has_move,
    color_availability,
    active_context,
    passive_context,
)
from .score import compute_score
from .types import ACTING_COLORS, ALL_DIE_COLORS, GameState, PlayerId

_KEY_MAP = {
    "global_turn": "globalTurn",
    "plus1_active": "plus1Active",
    "plus1_used_dice": "plus1UsedDice",
    "joker_pending": "jokerPending",
    "pending_bonuses": "pendingBonuses",
    "bonus_resolution": "bonusResolution",
    "pink_choice": "pinkChoice",
    "pending_advance": "pendingAdvance",
    "joker_value": "jokerValue",
    "acting_color": "actingColor",
    "max_pick": "maxPick",
    "elimination_value": "eliminationValue",
    "brown_last_checked": "brownLastChecked",
    "brown_disabled": "brownDisabled",
    "chosen_this_turn": "chosenThisTurn",
    "slots_unlocked": "slotsUnlocked",
    "origin_color": "originColor",
    "cell_id": "cellId",
    "effective_value": "effectiveValue",
    "bonus_slot_id": "bonusSlotId",
    "bonus_effect": "bonusEffect",
    "token_index": "tokenIndex",
    "color_subtotal": "colorSubtotal",
    "fox_count": "foxCount",
    "fox_value": "foxValue",
    "fox_points": "foxPoints",
}


def to_camel(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            key = _KEY_MAP.get(k, k)
            if isinstance(k, int) or (isinstance(k, str) and k.isdigit()):
                key = str(k)
            out[key] = to_camel(v)
        return out
    if isinstance(obj, list):
        return [to_camel(x) for x in obj]
    if isinstance(obj, tuple):
        return [to_camel(x) for x in obj]
    return obj


def _stuck(state: GameState) -> bool:
    phase = state["phase"]
    if phase["kind"] == "active":
        available = sum(1 for c in ALL_DIE_COLORS if state["dice"][c]["location"] == "available")
        return available > 0 and not any_available_die_has_move(state, phase["player"], phase["round"])
    if phase["kind"] == "passive" and not phase["done"]:
        return not any_die_has_passive_move(state, phase["player"])
    return False


def _white_availability(state: GameState) -> dict[str, bool] | None:
    sel = state["selection"]
    if not sel or sel["color"] != "white" or sel["acting_color"] is not None:
        return None
    phase = state["phase"]
    ctx = None
    if phase["kind"] == "active":
        ctx = active_context(state, phase["player"], phase["round"], "white")
    elif phase["kind"] == "passive":
        ctx = passive_context(state, phase["player"], "white")
    elif phase["kind"] == "plus1" and state["plus1_active"] is not None:
        ctx = passive_context(state, state["plus1_active"], "white")
    if not ctx:
        return None
    return dict(color_availability(sel["value"], ctx))


def _passive_flags(state: GameState) -> dict[str, bool]:
    phase = state["phase"]
    if phase["kind"] != "passive" or phase["done"]:
        return {"discardedHasMove": False, "chosenFallback": False}
    discarded = any_discarded_die_has_move(state, phase["player"])
    chosen = (not discarded) and any_chosen_die_has_move(state, phase["player"])
    return {"discardedHasMove": discarded, "chosenFallback": chosen}


def observe(state: GameState, player: PlayerId | None = None) -> dict[str, Any]:
    """Visible game state. `player` is reserved; both boards are public."""
    del player
    scores = {
        "1": compute_score(state["boards"][1]),
        "2": compute_score(state["boards"][2]),
    }
    return {
        "state": to_camel(state),
        "legalActions": to_camel(legal_actions(state)),
        "scores": to_camel(scores),
        "decision": current_decision(state),
        "stuck": _stuck(state),
        "whiteAvailability": _white_availability(state),
        "passiveFlags": _passive_flags(state),
        "actingColors": list(ACTING_COLORS),
    }
