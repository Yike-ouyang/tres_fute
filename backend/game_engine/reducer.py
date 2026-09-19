"""State transitions. RNG is used only for rolls / rerolls of available dice."""

from __future__ import annotations

import copy
import random
from typing import Any

from .bonuses import (
    PINK_BONUSES,
    PINK_MULTIPLIERS,
    apply_unlocks,
    consume_joker_token,
    empty_bonus_state,
    pick_joker_token,
)
from .rules import (
    active_context,
    all_unchecked_turquoise,
    any_available_die_has_move,
    any_chosen_die_has_move,
    any_die_has_passive_move,
    any_discarded_die_has_move,
    blue_bonus_options,
    blue_sum,
    bonus_brown_legal,
    bonus_has_any_placeable_value,
    bonus_yellow_legal,
    first_empty_pink,
    legal_destinations,
    passive_context,
    pink_points,
    pink_value,
)
from .types import (
    ALL_DIE_COLORS,
    ActingColor,
    Action,
    BonusDieColor,
    BonusResolution,
    ChosenDie,
    DieColor,
    DieRuntime,
    GameState,
    PendingBonus,
    PlayerBoard,
    PlayerId,
    Selection,
    effective_value,
    empty_plus1_used_dice,
    other_player,
    PLAYER_IDS,
)

STUCK_ACTIVE = "Aucun coup possible. Terminez le tour."
STUCK_PASSIVE = "Aucun coup possible. Vous pouvez passer."
NO_DIE_MOVE = "Aucun coup possible avec ce dé."
NO_COLOR_MOVE = "Cette couleur ne permet aucun coup."
JOKER_NEED_VALUE = "Joker : choisissez d'abord une valeur."
JOKER_PICK_DIE = "Joker : choisissez un dé à transformer."
PINK_CHOICE_MSG = "Case rose : choisissez les points ou le bonus."
BONUS_NO_VALUE = "Aucune case disponible pour cette valeur."
FILL_SLOTS_MSG = "Compléter les dés actifs — sans effet. Ces choix ne produisent aucun coup."
PASSIVE_FALLBACK = "Aucun dé passif n’est jouable : vous pouvez choisir un dé actif."

DIE_COLOR_LABEL: dict[str, str] = {
    "yellow": "jaune",
    "turquoise": "turquoise",
    "darkblue": "bleu foncé",
    "brown": "marron",
    "pink": "rose",
    "black": "noir",
}

NEEDS_VALUE = {"yellow", "brown", "pink"}


def _roll_value(rng: random.Random) -> int:
    return rng.randint(1, 6)


def empty_board() -> PlayerBoard:
    return {
        "checks": {},
        "values": {},
        "brown_last_checked": None,
        "brown_disabled": {},
        "chosen_this_turn": [],
        "slots": [None, None, None],
        "bonuses": empty_bonus_state(),
    }


def _roll_all_dice(rng: random.Random) -> dict[DieColor, DieRuntime]:
    return {c: {"value": _roll_value(rng), "location": "available"} for c in ALL_DIE_COLORS}


def _reroll_available(dice: dict[DieColor, DieRuntime], rng: random.Random) -> dict[DieColor, DieRuntime]:
    next_dice: dict[DieColor, DieRuntime] = {}
    for color in ALL_DIE_COLORS:
        d = dice[color]
        if d["location"] == "available":
            next_dice[color] = {"value": _roll_value(rng), "location": "available"}
        else:
            next_dice[color] = copy.deepcopy(d)
    return next_dice


def _with_unique_pick(sel: Selection) -> Selection:
    if len(sel["legal"]) == 1 and len(sel["picked"]) == 0:
        return {**sel, "picked": [sel["legal"][0]]}
    return sel


def _has_empty_slot(board: PlayerBoard) -> bool:
    return any(s is None for s in board["slots"])


def _dump_available(dice: dict[DieColor, DieRuntime]) -> dict[DieColor, DieRuntime]:
    next_dice: dict[DieColor, DieRuntime] = {}
    for color in ALL_DIE_COLORS:
        d = dice[color]
        next_dice[color] = {**d, "location": "discarded"} if d["location"] == "available" else copy.deepcopy(d)
    return next_dice


def _count_available(dice: dict[DieColor, DieRuntime]) -> int:
    return sum(1 for c in ALL_DIE_COLORS if dice[c]["location"] == "available")


def _cell_number(cell_id: str) -> int:
    return int(cell_id.split("-")[-1])


def _enqueue_dice(state: GameState, owner: PlayerId, colors: list[BonusDieColor]) -> GameState:
    if not colors:
        return state
    extra: list[PendingBonus] = [{"owner": owner, "color": c} for c in colors]
    return {**state, "pending_bonuses": [*state["pending_bonuses"], *extra]}


def _with_stuck_message(state: GameState) -> GameState:
    phase = state["phase"]
    if phase["kind"] == "active":
        if _count_available(state["dice"]) > 0 and not any_available_die_has_move(
            state, phase["player"], phase["round"]
        ):
            return {**state, "message": STUCK_ACTIVE}
    elif phase["kind"] == "passive" and not phase["done"]:
        if any_discarded_die_has_move(state, phase["player"]):
            return state
        if any_chosen_die_has_move(state, phase["player"]):
            return {**state, "message": PASSIVE_FALLBACK}
        return {**state, "message": STUCK_PASSIVE}
    return state


def _start_active_sequence(state: GameState, player: PlayerId, rng: random.Random) -> GameState:
    board = state["boards"][player]
    base: GameState = {
        **state,
        "phase": {"kind": "active", "player": player, "round": 1},
        "dice": _roll_all_dice(rng),
        "boards": {
            **state["boards"],
            player: {**board, "slots": [None, None, None], "chosen_this_turn": []},
        },
        "selection": None,
        "message": None,
        "plus1_active": None,
        "joker_pending": None,
        "bonus_resolution": None,
        "pink_choice": None,
        "pending_advance": None,
    }
    return _with_stuck_message(base)


def _settle_plus1(state: GameState) -> GameState:
    if state["phase"]["kind"] != "plus1":
        return state
    order = state["phase"]["order"]
    current = state["phase"]["current"]
    while current < len(order):
        actor = order[current]
        pb = state["boards"][actor]["bonuses"]["plus1"]
        if pb["unlocked"] > pb["used"]:
            break
        current += 1
    if current >= len(order):
        return _with_stuck_message(
            {
                **state,
                "phase": {"kind": "passive", "player": order[1], "done": False},
                "selection": None,
                "message": None,
                "plus1_active": None,
                "joker_pending": None,
            }
        )
    return {
        **state,
        "phase": {"kind": "plus1", "order": order, "current": current},
        "selection": None,
        "plus1_active": None,
        "message": f"Joueur {order[current]} peut utiliser un ou plusieurs +1.",
    }


def _end_active_sequence(state: GameState, active_player: PlayerId) -> GameState:
    dice: dict[DieColor, DieRuntime] = {}
    for color in ALL_DIE_COLORS:
        d = state["dice"][color]
        dice[color] = {**d, "location": "discarded"} if d["location"] == "available" else copy.deepcopy(d)
    passive = other_player(active_player)
    base: GameState = {
        **state,
        "dice": dice,
        "phase": {"kind": "plus1", "order": [active_player, passive], "current": 0},
        "selection": None,
        "message": None,
        "plus1_active": None,
        "joker_pending": None,
        "plus1_used_dice": empty_plus1_used_dice(),
    }
    return _settle_plus1(base)


def _enter_fill_slots_or_end(state: GameState, player: PlayerId) -> GameState:
    if not _has_empty_slot(state["boards"][player]):
        return _end_active_sequence(state, player)
    return {
        **state,
        "phase": {"kind": "fill-slots", "player": player},
        "selection": None,
        "message": FILL_SLOTS_MSG,
        "joker_pending": None,
    }


def _resolution_message(br: BonusResolution) -> str:
    label = DIE_COLOR_LABEL[br["color"]]
    stage = br["stage"]
    if stage == "chooseColor":
        return "Bonus dé noir : choisissez la couleur du dé bonus."
    if stage == "chooseValue":
        return f"Bonus {label} : choisissez une valeur."
    if stage == "placing":
        if br["color"] == "turquoise":
            return "Bonus turquoise : cochez la case turquoise de votre choix."
        if br["color"] == "darkblue":
            return "Bonus bleu foncé : choisissez la case et la valeur."
        return f"Bonus {label} : choisissez la case."
    return f"Bonus {label} : aucun coup possible, terminez la résolution."


def _enter_placement(state: GameState, br: BonusResolution) -> GameState:
    board = state["boards"][br["owner"]]
    if br["color"] == "turquoise":
        legal = all_unchecked_turquoise(board)
        if not legal:
            nxt: BonusResolution = {**br, "stage": "noMove"}
            return {**state, "bonus_resolution": nxt, "selection": None, "message": _resolution_message(nxt)}
        nxt = {**br, "stage": "placing"}
        return {
            **state,
            "bonus_resolution": nxt,
            "selection": _with_unique_pick(
                {
                    "color": "turquoise",
                    "value": 0,
                    "acting_color": "turquoise",
                    "legal": legal,
                    "picked": [],
                    "max_pick": 1,
                    "elimination_value": 0,
                }
            ),
            "message": _resolution_message(nxt),
        }
    if br["color"] == "darkblue":
        options = blue_bonus_options(board)
        nxt = {**br, "stage": "noMove" if not options else "placing"}
        return {**state, "bonus_resolution": nxt, "selection": None, "message": _resolution_message(nxt)}
    if br["value"] is None:
        nxt = {**br, "stage": "chooseValue"}
        return {**state, "bonus_resolution": nxt, "selection": None, "message": _resolution_message(nxt)}
    legal = bonus_yellow_legal(board, br["value"]) if br["color"] == "yellow" else bonus_brown_legal(board, br["value"])
    if not legal:
        if br["color"] in ("yellow", "brown") and not bonus_has_any_placeable_value(board, br["color"]):  # type: ignore[arg-type]
            dead: BonusResolution = {**br, "stage": "noMove"}
            return {**state, "bonus_resolution": dead, "selection": None, "message": _resolution_message(dead)}
        nxt = {**br, "stage": "chooseValue", "value": None}
        return {**state, "bonus_resolution": nxt, "selection": None, "message": BONUS_NO_VALUE}
    nxt = {**br, "stage": "placing"}
    color: DieColor = br["color"]  # type: ignore[assignment]
    acting: ActingColor = br["color"]  # type: ignore[assignment]
    return {
        **state,
        "bonus_resolution": nxt,
        "selection": _with_unique_pick(
            {
                "color": color,
                "value": br["value"],
                "acting_color": acting,
                "legal": legal,
                "picked": [],
                "max_pick": 1,
                "elimination_value": 0,
            }
        ),
        "message": _resolution_message(nxt),
    }


def _open_next_bonus(state: GameState) -> GameState:
    head, *rest = state["pending_bonuses"]
    base: GameState = {**state, "pending_bonuses": rest, "selection": None, "pink_choice": None}
    br: BonusResolution = {
        "owner": head["owner"],
        "origin_color": head["color"],
        "color": head["color"],
        "stage": "chooseValue",
        "value": None,
    }
    if head["color"] == "black":
        nxt: BonusResolution = {**br, "stage": "chooseColor"}
        return {**base, "bonus_resolution": nxt, "message": _resolution_message(nxt)}
    if head["color"] in NEEDS_VALUE:
        board = state["boards"][head["owner"]]
        if head["color"] in ("yellow", "brown", "pink") and not bonus_has_any_placeable_value(
            board, head["color"]  # type: ignore[arg-type]
        ):
            nxt = {**br, "stage": "noMove"}
            return {**base, "bonus_resolution": nxt, "message": _resolution_message(nxt)}
        return {**base, "bonus_resolution": br, "message": _resolution_message(br)}
    return _enter_placement(base, br)


def _advance(state: GameState, pending: dict[str, Any], rng: random.Random) -> GameState:
    kind = pending["kind"]
    if kind == "activeNext":
        return _with_stuck_message(
            {
                **state,
                "phase": {"kind": "active", "player": pending["player"], "round": pending["round"]},
                "dice": _reroll_available(state["dice"], rng),
                "selection": None,
                "message": None,
                "joker_pending": None,
            }
        )
    if kind == "endActive":
        return _end_active_sequence(state, pending["player"])
    if kind == "fillSlots":
        return _enter_fill_slots_or_end(state, pending["player"])
    if kind == "passiveDone":
        return {
            **state,
            "phase": {"kind": "passive", "player": pending["player"], "done": True},
            "selection": None,
            "message": None,
        }
    if kind == "plus1Next":
        return _settle_plus1(
            {
                **state,
                "phase": {"kind": "plus1", "order": pending["order"], "current": pending["current"]},
                "selection": None,
                "plus1_active": None,
                "message": None,
            }
        )
    if kind == "startTurn":
        return _start_active_sequence(state, pending["player"], rng)
    return state


def _drain_or_advance(state: GameState, rng: random.Random) -> GameState:
    if state["bonus_resolution"] or state["pink_choice"]:
        return state
    if state["pending_bonuses"]:
        return _open_next_bonus(state)
    if state["pending_advance"]:
        pending = state["pending_advance"]
        return _advance({**state, "pending_advance": None}, pending, rng)
    return state


def _finish_bonus_resolution(state: GameState, rng: random.Random) -> GameState:
    return _drain_or_advance(
        {**state, "bonus_resolution": None, "selection": None, "message": None},
        rng,
    )


def _grant_turn_bonuses(state: GameState, turn: int) -> GameState:
    turn_id = f"turn-{turn}"
    s = state
    for p in PLAYER_IDS:
        with_check: PlayerBoard = {
            **s["boards"][p],
            "checks": {**s["boards"][p]["checks"], turn_id: True},
        }
        board, die_bonuses = apply_unlocks(with_check)
        s = _enqueue_dice({**s, "boards": {**s["boards"], p: board}}, p, die_bonuses)
    return s


def begin_global_turn(state: GameState, turn: int, rng: random.Random) -> GameState:
    granted = _grant_turn_bonuses(
        {**state, "global_turn": turn, "phase": {"kind": "active", "player": 1, "round": 1}},
        turn,
    )
    return _drain_or_advance({**granted, "pending_advance": {"kind": "startTurn", "player": 1}}, rng)


def create_initial_state(rng: random.Random) -> GameState:
    base: GameState = {
        "global_turn": 1,
        "phase": {"kind": "active", "player": 1, "round": 1},
        "boards": {1: empty_board(), 2: empty_board()},
        "dice": _roll_all_dice(rng),
        "selection": None,
        "message": None,
        "plus1_active": None,
        "joker_pending": None,
        "plus1_used_dice": empty_plus1_used_dice(),
        "pending_bonuses": [],
        "bonus_resolution": None,
        "pink_choice": None,
        "pending_advance": None,
    }
    return begin_global_turn(base, 1, rng)


def _apply_move_to_board(board: PlayerBoard, sel: Selection, dice: dict[DieColor, DieRuntime]) -> PlayerBoard:
    checks = board["checks"]
    values = board["values"]
    brown_last = board["brown_last_checked"]
    brown_disabled = board["brown_disabled"]
    acting = sel["acting_color"]
    if acting == "yellow":
        checks = {**checks, sel["picked"][0]: True}
    elif acting == "turquoise":
        checks = {**checks, **{cid: True for cid in sel["picked"]}}
    elif acting == "darkblue":
        values = {**values, sel["picked"][0]: blue_sum(dice)}
    elif acting == "brown":
        cell = sel["picked"][0]
        idx = _cell_number(cell)
        checks = {**checks, cell: True}
        brown_disabled = {**brown_disabled}
        for n in range(1, idx):
            cid = f"brown-cell-{n}"
            if not checks.get(cid):
                brown_disabled[cid] = True
        brown_last = idx
    return {
        **board,
        "checks": checks,
        "values": values,
        "brown_last_checked": brown_last,
        "brown_disabled": brown_disabled,
    }


def _acting_player(state: GameState) -> PlayerId | None:
    if state["pink_choice"]:
        return state["pink_choice"]["owner"]
    if state["bonus_resolution"]:
        return state["bonus_resolution"]["owner"]
    phase = state["phase"]
    if phase["kind"] == "active":
        return phase["player"]
    if phase["kind"] == "fill-slots":
        return phase["player"]
    if phase["kind"] == "passive" and not phase["done"]:
        return phase["player"]
    if phase["kind"] == "plus1" and state["plus1_active"] is not None:
        return state["plus1_active"]
    return None


def _ctx_for_phase(state: GameState, selected_color: DieColor):
    phase = state["phase"]
    if phase["kind"] == "active":
        return active_context(state, phase["player"], phase["round"], selected_color)
    if phase["kind"] == "passive" and not phase["done"]:
        return passive_context(state, phase["player"], selected_color)
    if phase["kind"] == "plus1" and state["plus1_active"] is not None:
        return passive_context(state, state["plus1_active"], selected_color)
    return None


def _eliminate_for_move(dice: dict[DieColor, DieRuntime], sel: Selection) -> dict[DieColor, DieRuntime]:
    next_dice: dict[DieColor, DieRuntime] = {}
    for color in ALL_DIE_COLORS:
        d = dice[color]
        if color == sel["color"]:
            next_dice[color] = {**d, "location": "chosen"}
        elif d["location"] == "available" and d["value"] < sel["elimination_value"]:
            next_dice[color] = {**d, "location": "discarded"}
        else:
            next_dice[color] = copy.deepcopy(d)
    return next_dice


def _finish_active_after_write(
    state: GameState,
    player: PlayerId,
    round_n: int,
    sel: Selection,
    extra_dice: list[BonusDieColor],
    board_written: PlayerBoard,
    rng: random.Random,
) -> GameState:
    slots = list(board_written["slots"])
    slots[round_n - 1] = {"color": sel["color"], "value": sel["value"]}
    chosen: list[ChosenDie] = [*board_written["chosen_this_turn"], {"color": sel["color"], "value": sel["value"]}]
    board, die_bonuses = apply_unlocks({**board_written, "slots": slots, "chosen_this_turn": chosen})
    dice = _eliminate_for_move(state["dice"], sel)
    next_state: GameState = {
        **state,
        "boards": {**state["boards"], player: board},
        "dice": dice,
        "selection": None,
        "message": None,
        "joker_pending": None,
    }
    next_state = _enqueue_dice(next_state, player, [*extra_dice, *die_bonuses])
    if round_n < 3 and _count_available(dice) > 0:
        pending = {"kind": "activeNext", "player": player, "round": round_n + 1}
    elif _has_empty_slot(board):
        pending = {"kind": "fillSlots", "player": player}
    else:
        pending = {"kind": "endActive", "player": player}
    return _drain_or_advance({**next_state, "pending_advance": pending}, rng)


def _finish_passive_after_write(
    state: GameState,
    player: PlayerId,
    extra_dice: list[BonusDieColor],
    board_written: PlayerBoard,
    rng: random.Random,
) -> GameState:
    board, die_bonuses = apply_unlocks(board_written)
    next_state: GameState = {
        **state,
        "boards": {**state["boards"], player: board},
        "selection": None,
        "message": None,
    }
    next_state = _enqueue_dice(next_state, player, [*extra_dice, *die_bonuses])
    return _drain_or_advance({**next_state, "pending_advance": {"kind": "passiveDone", "player": player}}, rng)


def _finish_plus1_after_write(
    state: GameState,
    actor: PlayerId,
    extra_dice: list[BonusDieColor],
    board_written: PlayerBoard,
    die_color: DieColor,
    rng: random.Random,
) -> GameState:
    if state["phase"]["kind"] != "plus1":
        return state
    pb = board_written["bonuses"]["plus1"]
    with_use: PlayerBoard = {
        **board_written,
        "bonuses": {**board_written["bonuses"], "plus1": {**pb, "used": pb["used"] + 1}},
    }
    board, die_bonuses = apply_unlocks(with_use)
    plus1_used = {**state["plus1_used_dice"], actor: [*state["plus1_used_dice"][actor], die_color]}
    still = board["bonuses"]["plus1"]["unlocked"] > board["bonuses"]["plus1"]["used"]
    next_state: GameState = {
        **state,
        "boards": {**state["boards"], actor: board},
        "plus1_used_dice": plus1_used,
        "selection": None,
        "plus1_active": None,
        "message": None,
    }
    next_state = _enqueue_dice(next_state, actor, [*extra_dice, *die_bonuses])
    return _drain_or_advance(
        {
            **next_state,
            "pending_advance": {
                "kind": "plus1Next",
                "order": state["phase"]["order"],
                "current": state["phase"]["current"] if still else state["phase"]["current"] + 1,
            },
        },
        rng,
    )


def _complete_after_pink_write(
    state: GameState,
    resume: dict[str, Any],
    extra_dice: list[BonusDieColor],
    board_written: PlayerBoard,
    rng: random.Random,
) -> GameState:
    kind = resume["kind"]
    if kind == "active":
        return _finish_active_after_write(
            state, resume["player"], resume["round"], resume["sel"], extra_dice, board_written, rng
        )
    if kind == "passive":
        return _finish_passive_after_write(state, resume["player"], extra_dice, board_written, rng)
    if kind == "plus1":
        return _finish_plus1_after_write(state, resume["actor"], extra_dice, board_written, resume["sel"]["color"], rng)
    if kind == "bonusDie":
        with_board: GameState = {**state, "boards": {**state["boards"], resume["owner"]: board_written}}
        enqueued = _enqueue_dice(with_board, resume["owner"], extra_dice)
        return _finish_bonus_resolution(enqueued, rng)
    return state


def _open_pink_for_move(
    state: GameState, owner: PlayerId, sel: Selection, resume: dict[str, Any], rng: random.Random
) -> GameState:
    dest = sel["picked"][0]
    n = _cell_number(dest)
    eff = sel["value"]
    if n == 1:
        inscribed = pink_value(eff)
        board: PlayerBoard = {
            **state["boards"][owner],
            "values": {**state["boards"][owner]["values"], dest: inscribed},
        }
        return _complete_after_pink_write(state, resume, [], board, rng)
    bonus_effect = PINK_BONUSES[n - 1]
    return {
        **state,
        "pink_choice": {
            "owner": owner,
            "cell_id": dest,
            "position": n,
            "effective_value": eff,
            "multiplier": PINK_MULTIPLIERS[n - 1],
            "bonus_slot_id": None if bonus_effect["kind"] == "none" else f"pink-{n}",
            "bonus_effect": bonus_effect,
            "resume": resume,
        },
        "selection": None,
        "message": PINK_CHOICE_MSG,
    }


def _validate_active(state: GameState, sel: Selection, player: PlayerId, round_n: int, rng: random.Random) -> GameState:
    if sel["acting_color"] == "pink":
        return _open_pink_for_move(state, player, sel, {"kind": "active", "player": player, "round": round_n, "sel": sel}, rng)
    moved = _apply_move_to_board(state["boards"][player], sel, state["dice"])
    return _finish_active_after_write(state, player, round_n, sel, [], moved, rng)


def _validate_passive(state: GameState, sel: Selection, player: PlayerId, rng: random.Random) -> GameState:
    if sel["acting_color"] == "pink":
        return _open_pink_for_move(state, player, sel, {"kind": "passive", "player": player, "sel": sel}, rng)
    moved = _apply_move_to_board(state["boards"][player], sel, state["dice"])
    return _finish_passive_after_write(state, player, [], moved, rng)


def _validate_plus1(state: GameState, sel: Selection, actor: PlayerId, rng: random.Random) -> GameState:
    if sel["acting_color"] == "pink":
        return _open_pink_for_move(state, actor, sel, {"kind": "plus1", "actor": actor, "sel": sel}, rng)
    moved = _apply_move_to_board(state["boards"][actor], sel, state["dice"])
    return _finish_plus1_after_write(state, actor, [], moved, sel["color"], rng)


def _continue_after_passive(state: GameState, player: PlayerId, rng: random.Random) -> GameState:
    if player == 2:
        return _start_active_sequence(state, 2, rng)
    if state["global_turn"] >= 6:
        return {
            **state,
            "phase": {"kind": "game-over"},
            "selection": None,
            "message": "Partie terminée",
            "plus1_active": None,
            "joker_pending": None,
        }
    return begin_global_turn(state, state["global_turn"] + 1, rng)


def game_reducer(state: GameState, action: Action, rng: random.Random) -> GameState:
    """Apply one player decision. Illegal actions return the same object (no RNG)."""
    t = action.get("type")
    if t == "select_die":
        return _act_select_die(state, action, rng)
    if t == "choose_white_color":
        return _act_choose_white_color(state, action)
    if t == "pick_cell":
        return _act_pick_cell(state, action)
    if t == "cancel_selection":
        return _act_cancel_selection(state)
    if t == "confirm_move":
        return _act_confirm_move(state, rng)
    if t == "end_active_early":
        return _act_end_active(state)
    if t == "pass_passive":
        return _act_pass_passive(state)
    if t == "continue":
        return _act_continue(state, rng)
    if t == "use_relance":
        return _act_use_relance(state, rng)
    if t == "start_joker":
        return _act_start_joker(state, action)
    if t == "set_joker_value":
        return _act_set_joker_value(state, action)
    if t == "cancel_joker":
        return _act_cancel_joker(state)
    if t == "begin_plus1":
        return _act_begin_plus1(state)
    if t == "skip_plus1":
        return _act_skip_plus1(state)
    if t == "choose_bonus_color":
        return _act_choose_bonus_color(state, action)
    if t == "choose_bonus_value":
        return _act_choose_bonus_value(state, action, rng)
    if t == "place_bonus_blue":
        return _act_place_bonus_blue(state, action, rng)
    if t == "dismiss_impossible_bonus":
        return _act_dismiss_bonus(state, rng)
    if t == "choose_pink_option":
        return _act_pink_choose(state, action, rng)
    if t == "cancel_pink_option":
        return _act_pink_cancel(state)
    if t == "fill_slot_dummy":
        return _act_fill_slot(state, action)
    if t == "reset":
        return create_initial_state(rng)
    return state


def _act_select_die(state: GameState, action: Action, rng: random.Random) -> GameState:
    if state["bonus_resolution"] or state["pink_choice"]:
        return state
    phase = state["phase"]
    actor = _acting_player(state)
    if actor is None:
        return state
    color: DieColor = action["color"]
    dice = state["dice"]
    boards = state["boards"]
    joker_pending = state["joker_pending"]
    joker_applied = False

    d = dice.get(color)
    if not d:
        return state

    # Validate the die against the current context (active / passive / +1 / fill-slots).
    if phase["kind"] == "active":
        if d["location"] != "available":
            return state
    elif phase["kind"] == "fill-slots":
        if d["location"] != "discarded":
            return state
    elif phase["kind"] == "passive" and not phase["done"]:
        discarded_ok = any_discarded_die_has_move(state, phase["player"])
        pool = "discarded" if discarded_ok else "chosen"
        if d["location"] != pool:
            return state
    elif phase["kind"] == "plus1" and state["plus1_active"] is not None:
        if d["location"] not in ("chosen", "discarded"):
            return state
        if color in state["plus1_used_dice"][state["plus1_active"]]:
            return state
    else:
        return state

    # Apply the pending joker to the chosen die, consuming its token (JOKER-004).
    if joker_pending:
        if joker_pending.get("value") is None:
            return {**state, "message": JOKER_NEED_VALUE}
        joker_value = int(joker_pending["value"])
        jb = boards[actor]["bonuses"]["joker"]
        index = joker_pending.get("token_index")
        if index is None:
            index = pick_joker_token(jb, joker_value)
        dice = {**dice, color: {**d, "joker_value": joker_value}}
        new_jb = consume_joker_token(jb, index) if index is not None else {**jb, "used": jb["used"] + 1}
        boards = {
            **boards,
            actor: {**boards[actor], "bonuses": {**boards[actor]["bonuses"], "joker": new_jb}},
        }
        joker_pending = None
        joker_applied = True
        d = dice[color]

    # fill-slots: the joker only changes the die value; placement uses fill_slot_dummy.
    if phase["kind"] == "fill-slots":
        return {**state, "dice": dice, "boards": boards, "joker_pending": None} if joker_applied else state

    base: GameState = {**state, "dice": dice, "boards": boards, "joker_pending": None} if joker_applied else state
    value = effective_value(d)
    elimination_value = d["value"]

    if color == "white":
        return {
            **base,
            "selection": {
                "color": "white",
                "value": value,
                "acting_color": None,
                "legal": [],
                "picked": [],
                "max_pick": 1,
                "elimination_value": elimination_value,
            },
            "message": None,
        }

    ctx = _ctx_for_phase(base, color)
    if not ctx:
        return base
    result = legal_destinations(color, value, ctx)  # type: ignore[arg-type]
    if not result["legal"]:
        return {**base, "selection": None, "message": NO_DIE_MOVE}
    fallback = None
    if phase["kind"] == "passive" and not phase["done"] and not any_discarded_die_has_move(base, phase["player"]):
        fallback = PASSIVE_FALLBACK
    return {
        **base,
        "selection": _with_unique_pick(
            {
                "color": color,
                "value": value,
                "acting_color": color,  # type: ignore[typeddict-item]
                "legal": result["legal"],
                "picked": [],
                "max_pick": result["max_pick"],
                "elimination_value": elimination_value,
            }
        ),
        "message": fallback,
    }


def _act_choose_white_color(state: GameState, action: Action) -> GameState:
    if state["bonus_resolution"] or state["pink_choice"]:
        return state
    sel = state["selection"]
    if not sel or sel["color"] != "white":
        return state
    ctx = _ctx_for_phase(state, "white")
    if not ctx:
        return state
    acting: ActingColor = action["acting_color"]
    result = legal_destinations(acting, sel["value"], ctx)
    if not result["legal"]:
        return {**state, "message": NO_COLOR_MOVE}
    return {
        **state,
        "selection": _with_unique_pick(
            {**sel, "acting_color": acting, "legal": result["legal"], "picked": [], "max_pick": result["max_pick"]}
        ),
        "message": None,
    }


def _act_pick_cell(state: GameState, action: Action) -> GameState:
    sel = state["selection"]
    if not sel or sel["acting_color"] is None:
        return state
    cell_id = action["cell_id"]
    if cell_id not in sel["legal"]:
        return state
    if cell_id in sel["picked"]:
        picked = [c for c in sel["picked"] if c != cell_id]
    elif len(sel["picked"]) >= sel["max_pick"]:
        if sel["max_pick"] == 1:
            picked = [cell_id]
        else:
            return state
    else:
        picked = [*sel["picked"], cell_id]
    return {**state, "selection": {**sel, "picked": picked}}


def _act_cancel_selection(state: GameState) -> GameState:
    br = state["bonus_resolution"]
    if br and br["stage"] == "placing":
        if br["color"] in ("yellow", "brown"):
            nxt: BonusResolution = {**br, "stage": "chooseValue", "value": None}
            return {**state, "selection": None, "bonus_resolution": nxt, "message": _resolution_message(nxt)}
        sel = state["selection"]
        return {**state, "selection": {**sel, "picked": []} if sel else None}
    return {
        **state,
        "selection": None,
        "plus1_active": None if state["phase"]["kind"] == "plus1" else state["plus1_active"],
        "message": None,
    }


def _act_confirm_move(state: GameState, rng: random.Random) -> GameState:
    br = state["bonus_resolution"]
    if br and br["stage"] == "placing":
        sel = state["selection"]
        if not sel or not sel["picked"]:
            return state
        owner = br["owner"]
        board = state["boards"][owner]
        cell = sel["picked"][0]
        if br["color"] in ("turquoise", "yellow"):
            board = {**board, "checks": {**board["checks"], cell: True}}
        elif br["color"] == "brown":
            idx = _cell_number(cell)
            checks = {**board["checks"], cell: True}
            brown_disabled = {**board["brown_disabled"]}
            for n in range(1, idx):
                cid = f"brown-cell-{n}"
                if not checks.get(cid):
                    brown_disabled[cid] = True
            board = {**board, "checks": checks, "brown_disabled": brown_disabled, "brown_last_checked": idx}
        else:
            return state
        unlocked, die_bonuses = apply_unlocks(board)
        next_state = _enqueue_dice(
            {**state, "boards": {**state["boards"], owner: unlocked}, "selection": None},
            owner,
            die_bonuses,
        )
        return _finish_bonus_resolution(next_state, rng)

    sel = state["selection"]
    phase = state["phase"]
    if not sel or sel["acting_color"] is None or not sel["picked"] or len(sel["picked"]) > sel["max_pick"]:
        return state
    if phase["kind"] == "active":
        return _validate_active(state, sel, phase["player"], phase["round"], rng)
    if phase["kind"] == "passive" and not phase["done"]:
        return _validate_passive(state, sel, phase["player"], rng)
    if phase["kind"] == "plus1" and state["plus1_active"] is not None:
        return _validate_plus1(state, sel, state["plus1_active"], rng)
    return state


def _act_end_active(state: GameState) -> GameState:
    if state["bonus_resolution"] or state["pink_choice"]:
        return state
    phase = state["phase"]
    if phase["kind"] != "active":
        return state
    dumped: GameState = {
        **state,
        "dice": _dump_available(state["dice"]),
        "selection": None,
        "joker_pending": None,
    }
    return _enter_fill_slots_or_end(dumped, phase["player"])


def _act_pass_passive(state: GameState) -> GameState:
    if state["bonus_resolution"] or state["pink_choice"]:
        return state
    phase = state["phase"]
    if phase["kind"] != "passive" or phase["done"]:
        return state
    if any_die_has_passive_move(state, phase["player"]):
        return state
    return {
        **state,
        "phase": {"kind": "passive", "player": phase["player"], "done": True},
        "selection": None,
        "message": None,
    }


def _act_continue(state: GameState, rng: random.Random) -> GameState:
    if state["bonus_resolution"] or state["pink_choice"]:
        return state
    phase = state["phase"]
    if phase["kind"] != "passive" or not phase["done"]:
        return state
    return _continue_after_passive(state, phase["player"], rng)


def _act_use_relance(state: GameState, rng: random.Random) -> GameState:
    if state["bonus_resolution"] or state["pink_choice"]:
        return state
    phase = state["phase"]
    if phase["kind"] != "active":
        return state
    board = state["boards"][phase["player"]]
    rb = board["bonuses"]["relance"]
    if rb["unlocked"] <= rb["used"]:
        return state
    boards = {
        **state["boards"],
        phase["player"]: {
            **board,
            "bonuses": {**board["bonuses"], "relance": {**rb, "used": rb["used"] + 1}},
        },
    }
    return _with_stuck_message(
        {
            **state,
            "boards": boards,
            "dice": _reroll_available(state["dice"], rng),
            "selection": None,
            "joker_pending": None,
            "message": None,
        }
    )


def _act_start_joker(state: GameState, action: Action) -> GameState:
    if state["bonus_resolution"] or state["pink_choice"] or state["selection"]:
        return state
    actor = _acting_player(state)
    if actor is None:
        return state
    jb = state["boards"][actor]["bonuses"]["joker"]
    if jb["unlocked"] <= jb["used"]:
        return state
    if state["joker_pending"]:
        return state
    # The value is always chosen by the player (tokens may be used in any order).
    return {
        **state,
        "joker_pending": {"token_index": None, "value": None},
        "selection": None,
        "message": JOKER_NEED_VALUE,
    }


def _act_set_joker_value(state: GameState, action: Action) -> GameState:
    jp = state["joker_pending"]
    if not jp or jp.get("value") is not None:
        return state
    actor = _acting_player(state)
    if actor is None:
        return state
    value = action["value"]
    jb = state["boards"][actor]["bonuses"]["joker"]
    index = pick_joker_token(jb, value)
    if index is None:
        return state
    return {
        **state,
        "joker_pending": {"token_index": index, "value": int(value)},
        "message": JOKER_PICK_DIE,
    }


def _act_cancel_joker(state: GameState) -> GameState:
    if not state["joker_pending"]:
        return state
    return {**state, "joker_pending": None, "message": None}


def _act_begin_plus1(state: GameState) -> GameState:
    if state["bonus_resolution"] or state["pink_choice"]:
        return state
    phase = state["phase"]
    if phase["kind"] != "plus1":
        return state
    if state["plus1_active"] is not None:
        return state
    actor = phase["order"][phase["current"]]
    pb = state["boards"][actor]["bonuses"]["plus1"]
    if pb["unlocked"] <= pb["used"]:
        return state
    return {
        **state,
        "plus1_active": actor,
        "selection": None,
        "message": f"Joueur {actor} : choisissez un dé pour le +1.",
    }


def _act_skip_plus1(state: GameState) -> GameState:
    if state["bonus_resolution"] or state["pink_choice"]:
        return state
    phase = state["phase"]
    if phase["kind"] != "plus1":
        return state
    return _settle_plus1(
        {
            **state,
            "phase": {"kind": "plus1", "order": phase["order"], "current": phase["current"] + 1},
            "selection": None,
            "plus1_active": None,
            "message": None,
        }
    )


def _act_choose_bonus_color(state: GameState, action: Action) -> GameState:
    br = state["bonus_resolution"]
    if not br or br["stage"] != "chooseColor":
        return state
    chosen: BonusDieColor = action["color"]
    with_color: BonusResolution = {**br, "color": chosen, "value": None}
    if chosen in NEEDS_VALUE:
        board = state["boards"][br["owner"]]
        if chosen in ("yellow", "brown", "pink") and not bonus_has_any_placeable_value(board, chosen):  # type: ignore[arg-type]
            nxt: BonusResolution = {**with_color, "stage": "noMove"}
            return {**state, "bonus_resolution": nxt, "selection": None, "message": _resolution_message(nxt)}
        nxt = {**with_color, "stage": "chooseValue"}
        return {**state, "bonus_resolution": nxt, "message": _resolution_message(nxt)}
    return _enter_placement(state, with_color)


def _act_choose_bonus_value(state: GameState, action: Action, rng: random.Random) -> GameState:
    br = state["bonus_resolution"]
    if not br or br["stage"] != "chooseValue":
        return state
    value = action["value"]
    if value < 1 or value > 6:
        return state
    if br["color"] == "pink":
        board = state["boards"][br["owner"]]
        dest = first_empty_pink(board["values"])
        if not dest:
            nxt: BonusResolution = {**br, "stage": "noMove"}
            return {**state, "bonus_resolution": nxt, "selection": None, "message": _resolution_message(nxt)}
        return _open_pink_for_move(
            {**state, "bonus_resolution": {**br, "value": value, "stage": "placing"}},
            br["owner"],
            {
                "color": "pink",
                "value": value,
                "acting_color": "pink",
                "legal": [dest],
                "picked": [dest],
                "max_pick": 1,
                "elimination_value": 0,
            },
            {"kind": "bonusDie", "owner": br["owner"]},
            rng,
        )
    return _enter_placement(state, {**br, "value": value})


def _act_place_bonus_blue(state: GameState, action: Action, rng: random.Random) -> GameState:
    br = state["bonus_resolution"]
    if not br or br["color"] != "darkblue" or br["stage"] != "placing":
        return state
    owner = br["owner"]
    board: PlayerBoard = {
        **state["boards"][owner],
        "values": {**state["boards"][owner]["values"], action["cell_id"]: action["value"]},
    }
    unlocked, die_bonuses = apply_unlocks(board)
    next_state = _enqueue_dice({**state, "boards": {**state["boards"], owner: unlocked}}, owner, die_bonuses)
    return _finish_bonus_resolution(next_state, rng)


def _act_dismiss_bonus(state: GameState, rng: random.Random) -> GameState:
    br = state["bonus_resolution"]
    if not br:
        return state
    if br["stage"] == "noMove":
        return _finish_bonus_resolution(state, rng)
    if (
        br["stage"] == "chooseValue"
        and br["color"] in ("yellow", "brown", "pink")
        and not bonus_has_any_placeable_value(state["boards"][br["owner"]], br["color"])  # type: ignore[arg-type]
    ):
        return _finish_bonus_resolution(state, rng)
    return state


def _act_pink_choose(state: GameState, action: Action, rng: random.Random) -> GameState:
    choice = state["pink_choice"]
    if not choice:
        return state
    option = action["option"]
    if option == "bonus" and choice["bonus_effect"].get("kind") == "none":
        return state
    owner = choice["owner"]
    src = state["boards"][owner]
    values = {**src["values"]}
    bonuses = src["bonuses"]
    extra: list[BonusDieColor] = []
    if option == "points":
        values[choice["cell_id"]] = pink_points(choice["effective_value"], choice["multiplier"])
    else:
        values[choice["cell_id"]] = pink_value(choice["effective_value"])
        eff = choice["bonus_effect"]
        if eff.get("kind") == "cumulative":
            bonus = eff["bonus"]
            bonuses = {
                **bonuses,
                bonus: {**bonuses[bonus], "unlocked": bonuses[bonus]["unlocked"] + 1},
            }
        elif eff.get("kind") == "die":
            extra.append(eff["color"])
        if choice["bonus_slot_id"]:
            bonuses = {
                **bonuses,
                "slots_unlocked": {**bonuses["slots_unlocked"], choice["bonus_slot_id"]: True},
            }
    board_written: PlayerBoard = {**src, "values": values, "bonuses": bonuses}
    cleared: GameState = {**state, "pink_choice": None}
    return _complete_after_pink_write(cleared, choice["resume"], extra, board_written, rng)


def _act_pink_cancel(state: GameState) -> GameState:
    choice = state["pink_choice"]
    if not choice:
        return state
    if choice["resume"]["kind"] == "bonusDie":
        br = state["bonus_resolution"]
        if br:
            nxt: BonusResolution = {**br, "stage": "chooseValue", "value": None}
            return {**state, "pink_choice": None, "bonus_resolution": nxt, "message": _resolution_message(nxt)}
        return {**state, "pink_choice": None}
    return {**state, "pink_choice": None, "selection": choice["resume"]["sel"], "message": None}


def _act_fill_slot(state: GameState, action: Action) -> GameState:
    if state["bonus_resolution"] or state["pink_choice"]:
        return state
    phase = state["phase"]
    if phase["kind"] != "fill-slots":
        return state
    color: DieColor = action["color"]
    d = state["dice"].get(color)
    if not d or d["location"] != "discarded":
        return state
    board = state["boards"][phase["player"]]
    idx = next((i for i, s in enumerate(board["slots"]) if s is None), -1)
    if idx < 0:
        return _enter_fill_slots_or_end(state, phase["player"])
    slots = list(board["slots"])
    slots[idx] = {"color": color, "value": d["value"]}
    dice = {**state["dice"], color: {**d, "location": "chosen"}}
    next_state: GameState = {
        **state,
        "dice": dice,
        "boards": {**state["boards"], phase["player"]: {**board, "slots": slots}},
        "selection": None,
    }
    return _enter_fill_slots_or_end(next_state, phase["player"])
