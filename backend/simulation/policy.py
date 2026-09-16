"""Autoplay / fast-advance policy and the reusable ``HeuristicPolicy``.

``HeuristicPolicy`` lives outside the engine and only reads the engine's
observation and legal actions. It owns a dedicated RNG (seed-initialisable,
independent from the dice RNG) so a full game is reproducible. Its rules are
*preferences*: they filter the legal moves in priority order and always yield an
action the engine accepts.

The engine's ``legal_actions`` offers ``confirm_move`` as soon as a turquoise
selection has one picked cell, while its reducer still accepts further
``pick_cell`` actions. To honour the "take the maximum allowed checks" rule the
policy emits those continuation picks directly, staying inside the selection's
``legal`` destinations; every other action comes straight from ``legal_actions``.
"""

from __future__ import annotations

import random
from typing import Any, Sequence

from game_engine.legal import current_decision, is_global_turn_complete, legal_actions
from game_engine.rules import (
    active_context,
    all_unchecked_turquoise,
    bonus_brown_legal,
    bonus_has_any_placeable_value,
    blue_bonus_options,
    first_empty_pink,
    legal_destinations,
    passive_context,
    turquoise_companion_count,
)
from game_engine.types import (
    ACTING_COLORS,
    ALL_DIE_COLORS,
    Action,
    DieColor,
    GameState,
    effective_value,
)

AUTOPLAY_STEP_CAP = 8000

# Positions counted from the left, starting at 1 (not the printed values).
BROWN_AVOIDED_POSITIONS = (4, 5, 6)
BLUE_RIGHT_POSITIONS = tuple(range(8, 14))  # branch to the right of the centre (7)

MAROON_BLUE_FAMILY = ("brown", "darkblue")
RED_DIE_COLORS = ("pink", "white", "yellow")

_PICK_CELL = "pick_cell"


def brown_position_avoided(cell_id: str) -> bool:
    """True for brown cells at positions 4, 5 or 6 (positions, not printed values)."""
    return _position_of(cell_id, "brown-cell-") in BROWN_AVOIDED_POSITIONS


def blue_on_right(cell_id: str) -> bool:
    """True for blue cells on the right branch (positions 8..13)."""
    return _position_of(cell_id, "blue-cell-") in BLUE_RIGHT_POSITIONS


def _position_of(cell_id: str, prefix: str) -> int:
    if not cell_id or not cell_id.startswith(prefix):
        return -1
    try:
        return int(cell_id.rsplit("-", 1)[-1])
    except ValueError:
        return -1


def _available_dice(dice: dict[str, dict]) -> list[DieColor]:
    return [c for c in ALL_DIE_COLORS if dice[c]["location"] == "available"]


def nombre_retires(dice: dict[str, dict], chosen_color: DieColor) -> int:
    """``1 + number of available dice strictly below the chosen die`` (physical values)."""
    chosen = dice[chosen_color]["value"]
    return 1 + sum(
        1
        for c in ALL_DIE_COLORS
        if c != chosen_color and dice[c]["location"] == "available" and dice[c]["value"] < chosen
    )


def remaining_after(dice: dict[str, dict], chosen_color: DieColor) -> list[DieColor]:
    """Available dice surviving the removal (chosen + strictly inferior values removed)."""
    chosen = dice[chosen_color]["value"]
    return [
        c
        for c in ALL_DIE_COLORS
        if c != chosen_color and dice[c]["location"] == "available" and dice[c]["value"] >= chosen
    ]


class HeuristicPolicy:
    """Heuristic player: fast-forward, or a fixed opponent for a single RL agent."""

    def __init__(
        self,
        seed: int | None = None,
        *,
        rng: random.Random | None = None,
        debug: bool = False,
        relance_probability: float = 0.0,
        joker_probability: float = 0.0,
        plus1_probability: float = 0.0,
        marron_bleu_probability: float = 0.75,
    ) -> None:
        # Dedicated RNG: independent from the engine dice RNG, seed-initialisable.
        self.rng = rng if rng is not None else random.Random(seed)
        self.debug = debug
        # Optional-resource strategy: configurable, never spent automatically by default.
        self.relance_probability = relance_probability
        self.joker_probability = joker_probability
        self.plus1_probability = plus1_probability
        self.marron_bleu_probability = marron_bleu_probability
        self.log: list[str] = []
        self._plan: dict[str, Any] | None = None

    # ------------------------------------------------------------------ logging

    def _trace(self, message: str) -> None:
        if self.debug:
            self.log.append(message)

    def drain_log(self) -> list[str]:
        entries, self.log = self.log, []
        return entries

    # ------------------------------------------------------------------ entry point

    def choisir_action(self, source: GameState | Any) -> Action | None:
        """Pick a legal action from the observation / engine context. ``None`` if stuck."""
        state: GameState = source.state if hasattr(source, "state") else source  # type: ignore[assignment]
        legal = legal_actions(state)
        if not legal:
            return None
        # Continue an in-flight multi-pick (turquoise may check several cells) even
        # when the engine already proposes ``confirm_move`` after the first pick.
        follow = self._follow_plan_pick(state)
        if follow is not None:
            return follow

        if len(legal) == 1:
            return self._resolve_single(state, legal[0])

        if state["pink_choice"]:
            self._plan = None
            return self._handle_pink_choice(legal)

        if state["bonus_resolution"]:
            self._plan = None
            return self._handle_bonus(state, legal)

        if state["selection"] is not None:
            return self._handle_selection(state, legal)

        if state["joker_pending"]:
            self._plan = None
            return self._handle_joker(state, legal)

        kind = state["phase"]["kind"]
        if kind == "fill-slots":
            self._plan = None
            return self.rng.choice(legal)

        if kind == "plus1" and state["plus1_active"] is None:
            self._plan = None
            return self._handle_plus1_window(legal)

        if kind in ("active", "passive", "plus1"):
            return self._handle_select_die(state, legal)

        self._plan = None
        return self.rng.choice(legal)

    def action_for_player(self, source: GameState | Any, player: int) -> Action | None:
        """Like :meth:`choisir_action`, but only when ``player`` owns the decision.

        Enables reusing one policy instance as the fixed opponent of a single agent:
        the harness calls this each step and plays the action only when it is ``player``'s
        turn, letting the agent act otherwise.
        """
        state: GameState = source.state if hasattr(source, "state") else source  # type: ignore[assignment]
        if current_decision(state).get("actor") != player:
            return None
        return self.choisir_action(state)

    def _resolve_single(self, state: GameState, action: Action) -> Action:
        if action["type"] in ("confirm_move", "continue", "pass_passive", "skip_plus1", "end_active_early"):
            self._plan = None
        return action

    def _follow_plan_pick(self, state: GameState) -> Action | None:
        sel = state["selection"]
        if sel is None or not self._plan:
            return None
        if len(sel["picked"]) >= sel["max_pick"]:
            return None
        picked = set(sel["picked"])
        remaining = [cid for cid in self._plan.get("destinations", []) if cid not in picked and cid in sel["legal"]]
        if remaining:
            return {"type": _PICK_CELL, "cell_id": remaining[0]}
        return None

    # ------------------------------------------------------------------ dice choice

    def _ctx(self, state: GameState, die_color: DieColor) -> Any:
        phase = state["phase"]
        kind = phase["kind"]
        if kind == "active":
            return active_context(state, phase["player"], phase["round"], die_color)
        if kind == "passive":
            return passive_context(state, phase["player"], die_color)
        if kind == "plus1" and state["plus1_active"] is not None:
            return passive_context(state, state["plus1_active"], die_color)
        return None

    def _candidates(self, state: GameState, colors: Sequence[DieColor]) -> list[dict[str, Any]]:
        """Complete usages: (die, acting colour, legal destinations). White expands by colour."""
        dice = state["dice"]
        out: list[dict[str, Any]] = []
        for color in colors:
            if dice[color]["location"] not in ("available", "chosen", "discarded"):
                continue
            value = effective_value(dice[color])
            ctx = self._ctx(state, color)
            if ctx is None:
                continue
            if color == "white":
                for acting in ACTING_COLORS:
                    result = legal_destinations(acting, value, ctx)
                    if result["legal"]:
                        out.append(
                            {
                                "die": color,
                                "acting": acting,
                                "legal": list(result["legal"]),
                                "max_pick": int(result["max_pick"]),
                            }
                        )
            else:
                result = legal_destinations(color, value, ctx)  # type: ignore[arg-type]
                if result["legal"]:
                    out.append(
                        {
                            "die": color,
                            "acting": color,
                            "legal": list(result["legal"]),
                            "max_pick": int(result["max_pick"]),
                        }
                    )
        return out

    def _handle_select_die(self, state: GameState, legal: list[Action]) -> Action:
        select = [a for a in legal if a["type"] == "select_die"]
        if state["phase"]["kind"] == "active":
            resource = self._maybe_optional_resource(legal)
            if resource is not None:
                self._plan = None
                return resource
        if select:
            return self._commit_die(state, select)
        end_early = next((a for a in legal if a["type"] == "end_active_early"), None)
        if end_early is not None:
            self._plan = None
            return end_early
        self._plan = None
        return self.rng.choice(legal)

    def _maybe_optional_resource(self, legal: list[Action]) -> Action | None:
        for action in legal:
            if action["type"] == "use_relance" and self.relance_probability > 0:
                if self.rng.random() < self.relance_probability:
                    self._trace("optional: use_relance")
                    return action
            if action["type"] == "start_joker" and self.joker_probability > 0:
                if self.rng.random() < self.joker_probability:
                    self._trace("optional: start_joker")
                    return action
        return None

    def _commit_die(self, state: GameState, select: list[Action]) -> Action:
        colors = [a["color"] for a in select]
        cands = self._candidates(state, colors)
        if not cands:
            self._plan = None
            return self.rng.choice(select)

        dice = state["dice"]
        self._trace(f"candidates={[ (c['die'], c['acting']) for c in cands ]}")

        # Priority 1-3: round constraints.
        cands = self._pref_first_round(state, cands)
        cands = self._pref_second_round(state, cands)
        # Priority 4-5: brown positions / blue right branch.
        cands = self._pref_brown(cands)
        cands = self._pref_blue(cands)
        # Priority 6: 75 % brown/blue draw (once per die/colour usage).
        cands, _ = self._pref_maroon_blue(cands)
        self._trace(f"after colour prefs: {len(cands)} kept")
        # Priority 8: turquoise companion.
        cands = self._pref_turquoise(state, cands)

        chosen = self.rng.choice(cands)
        destinations = self._plan_destinations(state, chosen)
        self._plan = {
            "die": chosen["die"],
            "acting": chosen["acting"],
            "destinations": destinations,
            "max_pick": chosen["max_pick"],
        }
        kept_dice = remaining_after(dice, chosen["die"])
        self._trace(
            f"chosen die={chosen['die']} acting={chosen['acting']} "
            f"removed={nombre_retires(dice, chosen['die'])} kept={kept_dice} dests={destinations}"
        )
        return {"type": "select_die", "color": chosen["die"]}

    # ------------------------------------------------------------------ preferences

    def _pref_first_round(self, state: GameState, cands: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Priority 1: active round 1 keeps ≤3 removed dice."""
        phase = state["phase"]
        if phase["kind"] != "active" or phase["round"] != 1:
            return cands
        dice = state["dice"]
        kept = [c for c in cands if nombre_retires(dice, c["die"]) <= 3]
        if len(kept) < len(cands):
            self._trace(f"filter round1: {len(cands)} -> {len(kept)}")
        if not kept:
            self._trace("round1: no move ≤3 removed, preference relaxed")
        return kept or cands

    def _pref_second_round(self, state: GameState, cands: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Priorities 2-3: active round 2 keeps a die, then a rose/white/yellow one."""
        phase = state["phase"]
        if phase["kind"] != "active" or phase["round"] != 2:
            return cands
        dice = state["dice"]

        with_die = [c for c in cands if remaining_after(dice, c["die"])]
        kept = with_die or cands
        with_red = [c for c in kept if any(dc in RED_DIE_COLORS for dc in remaining_after(dice, c["die"]))]
        result = with_red or kept
        self._trace(f"filter round2: {len(cands)} -> {len(result)}")
        if not with_die:
            self._trace("round2: no move keeps a die, preference relaxed")
        elif not with_red:
            self._trace("round2: no move keeps a rose/white/yellow die, preference relaxed")
        return result

    def _pref_brown(self, cands: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Priority 4: avoid brown positions 4, 5, 6 when an alternative exists."""
        kept = [
            c
            for c in cands
            if not (c["acting"] == "brown" and all(brown_position_avoided(cid) for cid in c["legal"]))
        ]
        if not kept:
            self._trace("brown: only avoided positions remain, preference relaxed")
        return kept or cands

    def _pref_blue(self, cands: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Priority 5: use the right blue branch when an alternative exists."""
        kept = [
            c
            for c in cands
            if not (c["acting"] == "darkblue" and not any(blue_on_right(cid) for cid in c["legal"]))
        ]
        if not kept:
            self._trace("blue: only left branch remains, preference relaxed")
        return kept or cands

    def _pref_maroon_blue(self, cands: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
        """Priority 6: 75 % brown/blue family versus other colours (single draw)."""
        family = [c for c in cands if c["acting"] in MAROON_BLUE_FAMILY]
        others = [c for c in cands if c["acting"] not in MAROON_BLUE_FAMILY]
        if family and others:
            pick_family = self.rng.random() < self.marron_bleu_probability
            self._trace(
                f"tirage marron/bleu {self.marron_bleu_probability:.0%} -> "
                f"{'marron/bleu' if pick_family else 'autres'}"
            )
            return (family if pick_family else others), pick_family
        if family:
            return family, False
        return others or cands, False

    def _pref_turquoise(self, state: GameState, cands: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Priority 8: prefer turquoise sharing its value with a companion die."""
        dice = state["dice"]
        kept: list[dict[str, Any]] = []
        for cand in cands:
            if cand["acting"] != "turquoise":
                kept.append(cand)
                continue
            ctx = self._ctx(state, cand["die"])
            if ctx is None:
                kept.append(cand)
                continue
            value = effective_value(dice[cand["die"]])
            if turquoise_companion_count(ctx, value) >= 1:
                kept.append(cand)
        if not kept:
            self._trace("turquoise: no shared value, preference relaxed")
        return kept or cands

    def _plan_destinations(self, state: GameState, cand: dict[str, Any]) -> list[str]:
        legal = list(cand["legal"])
        acting = cand["acting"]
        if acting == "brown":
            preferred = [cid for cid in legal if not brown_position_avoided(cid)]
            pool = preferred or legal
        elif acting == "darkblue":
            preferred = [cid for cid in legal if blue_on_right(cid)]
            pool = preferred or legal
        else:
            pool = legal
        count = cand["max_pick"] if acting == "turquoise" else 1
        count = max(1, min(count, len(pool)))
        if count == 1:
            return [self.rng.choice(pool)]
        return self.rng.sample(pool, count)

    # ------------------------------------------------------------------ selection follow-up

    def _handle_selection(self, state: GameState, legal: list[Action]) -> Action:
        sel = state["selection"]
        assert sel is not None
        if sel["color"] == "white" and sel["acting_color"] is None:
            options = [a for a in legal if a["type"] == "choose_white_color"]
            if not options:
                self._plan = None
                return self.rng.choice(legal)
            if self._plan and self._plan.get("die") == "white":
                for action in options:
                    if action["acting_color"] == self._plan["acting"]:
                        return action
            return self._choose_white_color(state, options)

        confirm = next((a for a in legal if a["type"] == "confirm_move"), None)
        picks = [a for a in legal if a["type"] == _PICK_CELL]
        if picks:
            return self._choose_pick(state, picks, sel)
        self._plan = None
        if confirm is not None:
            return confirm
        return self.rng.choice(legal)

    def _choose_white_color(self, state: GameState, options: list[Action]) -> Action:
        cands = self._candidates(state, ["white"])
        cands = self._pref_brown(cands)
        cands = self._pref_blue(cands)
        cands, _ = self._pref_maroon_blue(cands)
        cands = self._pref_turquoise(state, cands)
        acting = self.rng.choice(cands)["acting"] if cands else None
        for action in options:
            if action["acting_color"] == acting:
                return action
        return self.rng.choice(options)

    def _choose_pick(self, state: GameState, picks: list[Action], sel: dict[str, Any]) -> Action:
        cells = [a["cell_id"] for a in picks]
        if sel["acting_color"] == "brown":
            preferred = [c for c in cells if not brown_position_avoided(c)]
            cells = preferred or cells
        elif sel["acting_color"] == "darkblue":
            preferred = [c for c in cells if blue_on_right(c)]
            cells = preferred or cells
        return {"type": _PICK_CELL, "cell_id": self.rng.choice(cells)}

    # ------------------------------------------------------------------ overlays

    def _handle_pink_choice(self, legal: list[Action]) -> Action:
        """Priority 7: always take the bonus option when the engine offers one."""
        bonus = next((a for a in legal if a.get("option") == "bonus"), None)
        if bonus is not None:
            return bonus
        points = next((a for a in legal if a.get("option") == "points"), None)
        return points or legal[0]

    def _handle_bonus(self, state: GameState, legal: list[Action]) -> Action:
        br = state["bonus_resolution"]
        assert br is not None
        stage = br["stage"]
        board = state["boards"][br["owner"]]

        if stage == "chooseColor":
            colors = [a["color"] for a in legal if a["type"] == "choose_bonus_color"]
            movable = [c for c in colors if self._bonus_color_has_move(board, c)]
            pool = movable or colors
            family = [c for c in pool if c in MAROON_BLUE_FAMILY]
            others = [c for c in pool if c not in MAROON_BLUE_FAMILY]
            if family and others and self.rng.random() < self.marron_bleu_probability:
                chosen = self.rng.choice(family)
            else:
                chosen = self.rng.choice(others or pool)
            return {"type": "choose_bonus_color", "color": chosen}

        if stage == "chooseValue":
            values = [a["value"] for a in legal if a["type"] == "choose_bonus_value"]
            if not values:
                return legal[0]
            if br["color"] == "brown":
                preferred = [
                    v
                    for v in values
                    if any(not brown_position_avoided(cid) for cid in bonus_brown_legal(board, v))
                ]
                values = preferred or values
            return {"type": "choose_bonus_value", "value": self.rng.choice(values)}

        if stage == "placing" and br["color"] == "darkblue":
            options = [a for a in legal if a["type"] == "place_bonus_blue"]
            right = [a for a in options if blue_on_right(a["cell_id"])]
            return self.rng.choice(right or options)

        picks = [a for a in legal if a["type"] == _PICK_CELL]
        if picks:
            cells = [a["cell_id"] for a in picks]
            if br["color"] == "brown":
                preferred = [c for c in cells if not brown_position_avoided(c)]
                cells = preferred or cells
            return {"type": _PICK_CELL, "cell_id": self.rng.choice(cells)}
        confirm = next((a for a in legal if a["type"] == "confirm_move"), None)
        return confirm or legal[0]

    def _bonus_color_has_move(self, board: dict[str, Any], color: str) -> bool:
        if color == "yellow":
            return bonus_has_any_placeable_value(board, "yellow")
        if color == "brown":
            return bonus_has_any_placeable_value(board, "brown")
        if color == "pink":
            return first_empty_pink(board["values"]) is not None
        if color == "turquoise":
            return len(all_unchecked_turquoise(board)) > 0
        if color == "darkblue":
            return len(blue_bonus_options(board)) > 0
        return False

    # ------------------------------------------------------------------ joker / +1

    def _handle_plus1_window(self, legal: list[Action]) -> Action:
        begin = next((a for a in legal if a["type"] == "begin_plus1"), None)
        skip = next((a for a in legal if a["type"] == "skip_plus1"), None)
        if begin is not None and self.plus1_probability > 0 and self.rng.random() < self.plus1_probability:
            return begin
        return skip or legal[0]

    def _handle_joker(self, state: GameState, legal: list[Action]) -> Action:
        jp = state["joker_pending"]
        assert jp is not None
        if jp.get("value") is None:
            values = [a["value"] for a in legal if a["type"] == "set_joker_value"]
            feasible = [v for v in values if self._value_enables_move(state, v)]
            return {"type": "set_joker_value", "value": self.rng.choice(feasible or values)}
        options = [a for a in legal if a["type"] == "select_die"]
        if not options:
            return self.rng.choice(legal)
        value = jp["value"]
        select = [a for a in options if self._die_can_move_with_value(state, a["color"], value)]
        return self.rng.choice(select or options)

    def _die_can_move_with_value(self, state: GameState, color: DieColor, value: int) -> bool:
        ctx = self._ctx(state, color)
        if ctx is None:
            return False
        if color == "white":
            return any(legal_destinations(c, value, ctx)["legal"] for c in ACTING_COLORS)
        return bool(legal_destinations(color, value, ctx)["legal"])  # type: ignore[arg-type]

    def _value_enables_move(self, state: GameState, value: int) -> bool:
        return any(
            state["dice"][c]["location"] == "available" and self._die_can_move_with_value(state, c, value)
            for c in ALL_DIE_COLORS
        )


# ---------------------------------------------------------------------- legacy helpers

def restrict_active_die_select(state: GameState, acts: list[Action]) -> list[Action]:
    """Legacy max-die filter (kept for compatibility; no longer used by fast advance)."""
    select_acts = [a for a in acts if a["type"] == "select_die"]
    rest = [a for a in acts if a["type"] != "select_die"]
    phase = state["phase"]
    if phase["kind"] != "active" or phase["round"] > 2 or state["joker_pending"] or not select_acts:
        return acts
    available = _available_dice(state["dice"])
    if not available:
        return acts
    max_phys = max(state["dice"][c]["value"] for c in available)
    lower = [a for a in select_acts if state["dice"][a["color"]]["value"] < max_phys]
    if lower:
        return [*rest, *lower]
    return acts


def pick_autoplay_action(state: GameState, rng: random.Random) -> Action | None:
    """Uniform random legal action (legacy). Prefer :func:`pick_heuristic_action`."""
    raw = legal_actions(state)
    if not raw:
        return None
    if any(a["type"] == "confirm_move" for a in raw):
        return {"type": "confirm_move"}
    acts = restrict_active_die_select(state, raw)
    if not acts:
        return None
    return rng.choice(acts)


def pick_heuristic_action(state: GameState, policy: HeuristicPolicy) -> Action | None:
    return policy.choisir_action(state)


def _as_policy(policy: Any) -> HeuristicPolicy:
    if isinstance(policy, HeuristicPolicy):
        return policy
    return HeuristicPolicy(rng=policy)


def next_autoplay_action(
    state: GameState, completed: int, quota: int, policy: Any
) -> tuple[Action | None, bool, str | None]:
    if state["phase"]["kind"] == "game-over":
        return None, True, None
    if is_global_turn_complete(state) and completed >= quota:
        if state["global_turn"] >= 6:
            return {"type": "continue"}, False, None
        return None, True, None
    action = pick_heuristic_action(state, _as_policy(policy))
    if action is None:
        return None, True, "Aucune action autoplay légale."
    return action, False, None


def fingerprint(state: GameState) -> str:
    return repr(
        (
            state["phase"],
            state["dice"],
            state["selection"],
            state["plus1_active"],
            state["plus1_used_dice"],
            state["joker_pending"],
            state["pending_bonuses"],
            state["bonus_resolution"],
            state["pink_choice"],
            state["pending_advance"],
            state["boards"],
            state["global_turn"],
            state["message"],
        )
    )


def run_autoplay(
    engine: Any,
    n_turns: int,
    policy: Any,
    step_cap: int = AUTOPLAY_STEP_CAP,
    on_progress: Any | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    """Advance up to n_turns global turns with ``HeuristicPolicy``.

    ``policy`` may be a :class:`HeuristicPolicy` or a ``random.Random`` (wrapped,
    preserving reproducibility). Stops on game-over or anti-loop.
    """
    heur = _as_policy(policy)
    if debug:
        heur.debug = True
    completed = 0
    last_fp = fingerprint(engine.state)
    stopped = "quota"
    for step in range(step_cap):
        before_complete = engine.turn_complete()
        action, stop, reason = next_autoplay_action(engine.state, completed, n_turns, heur)
        if stop:
            stopped = reason or "quota"
            break
        events = engine.step(action)
        if not events:
            stopped = "blocage"
            break
        if not before_complete and engine.turn_complete():
            completed += 1
            if on_progress:
                on_progress(completed, n_turns)
        fp = fingerprint(engine.state)
        if fp == last_fp:
            stopped = "blocage"
            break
        last_fp = fp
        if engine.is_over():
            stopped = "game-over"
            break
        if step == step_cap - 1:
            stopped = "step-cap"
    return {"completed": completed, "stopped": stopped, "over": engine.is_over(), "scores": engine.scores()}
