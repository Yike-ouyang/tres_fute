"""Legal player decisions for the current overlays / phase. Policy filters live elsewhere."""

from __future__ import annotations

from .rules import (
    active_context,
    any_available_die_has_move,
    any_discarded_die_has_move,
    blue_bonus_options,
    bonus_brown_legal,
    bonus_has_any_placeable_value,
    bonus_yellow_legal,
    color_availability,
    die_has_any_legal_move,
    passive_context,
)
from .types import ACTING_COLORS, ALL_DIE_COLORS, Action, GameState


def is_global_turn_complete(state: GameState) -> bool:
    phase = state["phase"]
    return (
        phase["kind"] == "passive"
        and phase["done"]
        and phase["player"] == 1
        and not state["bonus_resolution"]
        and not state["pink_choice"]
        and len(state["pending_bonuses"]) == 0
        and not state["pending_advance"]
    )


def remaining_autoplay_turns(state: GameState) -> int:
    if state["phase"]["kind"] == "game-over":
        return 0
    if is_global_turn_complete(state):
        return max(0, 6 - state["global_turn"])
    return max(0, 7 - state["global_turn"])


def legal_actions(state: GameState) -> list[Action]:
    phase = state["phase"]

    if state["pink_choice"]:
        acts: list[Action] = [{"type": "choose_pink_option", "option": "points"}]
        if state["pink_choice"]["bonus_effect"].get("kind") != "none":
            acts.append({"type": "choose_pink_option", "option": "bonus"})
        return acts

    if state["bonus_resolution"]:
        br = state["bonus_resolution"]
        board = state["boards"][br["owner"]]
        if br["stage"] == "chooseColor":
            return [{"type": "choose_bonus_color", "color": c} for c in ACTING_COLORS]
        if br["stage"] == "chooseValue":
            if br["color"] in ("yellow", "brown", "pink") and not bonus_has_any_placeable_value(
                board, br["color"]  # type: ignore[arg-type]
            ):
                return [{"type": "dismiss_impossible_bonus"}]
            values = [
                v
                for v in range(1, 7)
                if (
                    len(bonus_yellow_legal(board, v)) > 0
                    if br["color"] == "yellow"
                    else len(bonus_brown_legal(board, v)) > 0
                    if br["color"] == "brown"
                    else True
                )
            ]
            if not values:
                return [{"type": "dismiss_impossible_bonus"}]
            return [{"type": "choose_bonus_value", "value": v} for v in values]
        if br["stage"] == "placing" and br["color"] == "darkblue":
            return [
                {"type": "place_bonus_blue", "cell_id": opt["cell_id"], "value": opt["value"]}
                for opt in blue_bonus_options(board)
            ]
        if br["stage"] == "placing":
            sel = state["selection"]
            if sel and len(sel["picked"]) >= 1:
                return [{"type": "confirm_move"}]
            if sel:
                return [{"type": "pick_cell", "cell_id": cid} for cid in sel["legal"]]
            return [{"type": "dismiss_impossible_bonus"}]
        if br["stage"] == "noMove":
            return [{"type": "dismiss_impossible_bonus"}]
        return []

    if state["selection"]:
        sel = state["selection"]
        if sel["color"] == "white" and sel["acting_color"] is None:
            ctx = None
            if phase["kind"] == "active":
                ctx = active_context(state, phase["player"], phase["round"], "white")
            elif phase["kind"] == "passive":
                ctx = passive_context(state, phase["player"], "white")
            elif phase["kind"] == "plus1" and state["plus1_active"] is not None:
                ctx = passive_context(state, state["plus1_active"], "white")
            if not ctx:
                return [{"type": "cancel_selection"}]
            avail = color_availability(sel["value"], ctx)
            colors = [c for c in ACTING_COLORS if avail[c]]
            if not colors:
                return [{"type": "cancel_selection"}]
            return [{"type": "choose_white_color", "acting_color": c} for c in colors]
        if sel["acting_color"] is not None and len(sel["picked"]) >= 1:
            return [{"type": "confirm_move"}]
        if sel["acting_color"] is not None:
            if not sel["legal"]:
                return [{"type": "cancel_selection"}]
            return [{"type": "pick_cell", "cell_id": cid} for cid in sel["legal"]]
        return [{"type": "cancel_selection"}]

    if state["joker_pending"]:
        if state["joker_pending"].get("value") is None:
            return [{"type": "set_joker_value", "value": v} for v in range(1, 7)]
        return [
            {"type": "select_die", "color": c}
            for c in ALL_DIE_COLORS
            if state["dice"][c]["location"] == "available"
        ]

    if phase["kind"] == "fill-slots":
        return [
            {"type": "fill_slot_dummy", "color": c}
            for c in ALL_DIE_COLORS
            if state["dice"][c]["location"] == "discarded"
        ]

    if phase["kind"] == "plus1" and state["plus1_active"] is None:
        actor = phase["order"][phase["current"]]
        pb = state["boards"][actor]["bonuses"]["plus1"]
        acts = [{"type": "skip_plus1"}]
        if pb["unlocked"] > pb["used"]:
            acts.insert(0, {"type": "begin_plus1"})
        return acts

    if phase["kind"] == "plus1" and state["plus1_active"] is not None:
        actor = state["plus1_active"]
        already = set(state["plus1_used_dice"][actor])
        selectable = [
            c
            for c in ALL_DIE_COLORS
            if c not in already and die_has_any_legal_move(c, passive_context(state, actor, c))
        ]
        if not selectable:
            return [{"type": "skip_plus1"}]
        return [{"type": "select_die", "color": c} for c in selectable]

    if phase["kind"] == "passive" and phase["done"]:
        return [{"type": "continue"}]

    if phase["kind"] == "passive" and not phase["done"]:
        discarded_ok = any_discarded_die_has_move(state, phase["player"])
        pool = "discarded" if discarded_ok else "chosen"
        selectable = [
            c
            for c in ALL_DIE_COLORS
            if state["dice"][c]["location"] == pool
            and die_has_any_legal_move(c, passive_context(state, phase["player"], c))
        ]
        if not selectable:
            return [{"type": "pass_passive"}]
        return [{"type": "select_die", "color": c} for c in selectable]

    if phase["kind"] == "active":
        acts = []
        board = state["boards"][phase["player"]]
        available_count = sum(1 for c in ALL_DIE_COLORS if state["dice"][c]["location"] == "available")
        if available_count > 0 and board["bonuses"]["relance"]["unlocked"] > board["bonuses"]["relance"]["used"]:
            acts.append({"type": "use_relance"})
        if available_count > 0 and board["bonuses"]["joker"]["unlocked"] > board["bonuses"]["joker"]["used"]:
            acts.append({"type": "start_joker", "token_index": board["bonuses"]["joker"]["used"]})
        for color in ALL_DIE_COLORS:
            if state["dice"][color]["location"] != "available":
                continue
            if die_has_any_legal_move(color, active_context(state, phase["player"], phase["round"], color)):
                acts.append({"type": "select_die", "color": color})
        if not any_available_die_has_move(state, phase["player"], phase["round"]):
            acts.append({"type": "end_active_early"})
        return acts

    return []


def current_decision(state: GameState) -> dict:
    """Human-readable description of the waiting decision (not RNG internals)."""
    if state["pink_choice"]:
        return {"kind": "choose_pink_option", "actor": state["pink_choice"]["owner"]}
    if state["bonus_resolution"]:
        br = state["bonus_resolution"]
        return {"kind": f"bonus_{br['stage']}", "actor": br["owner"], "color": br["color"]}
    if state["selection"]:
        sel = state["selection"]
        actor = None
        phase = state["phase"]
        if phase["kind"] in ("active", "passive", "fill-slots"):
            actor = phase.get("player")
        elif phase["kind"] == "plus1":
            actor = state["plus1_active"]
        if sel["color"] == "white" and sel["acting_color"] is None:
            return {"kind": "choose_white_color", "actor": actor}
        if sel["acting_color"] is not None and sel["picked"]:
            return {"kind": "confirm_move", "actor": actor}
        return {"kind": "pick_cell", "actor": actor}
    if state["joker_pending"]:
        phase = state["phase"]
        actor = phase["player"] if phase["kind"] == "active" else None
        if state["joker_pending"].get("value") is None:
            return {"kind": "set_joker_value", "actor": actor}
        return {"kind": "select_die", "actor": actor, "joker": True}
    phase = state["phase"]
    if phase["kind"] == "game-over":
        return {"kind": "game_over", "actor": None}
    if phase["kind"] == "fill-slots":
        return {"kind": "fill_slot_dummy", "actor": phase["player"]}
    if phase["kind"] == "plus1" and state["plus1_active"] is None:
        return {"kind": "plus1_window", "actor": phase["order"][phase["current"]]}
    if phase["kind"] == "plus1":
        return {"kind": "select_die", "actor": state["plus1_active"], "plus1": True}
    if phase["kind"] == "passive" and phase["done"]:
        return {"kind": "continue", "actor": phase["player"]}
    if phase["kind"] == "passive":
        return {"kind": "select_die", "actor": phase["player"], "passive": True}
    if phase["kind"] == "active":
        return {"kind": "select_die", "actor": phase["player"], "round": phase["round"]}
    return {"kind": "unknown", "actor": None}
