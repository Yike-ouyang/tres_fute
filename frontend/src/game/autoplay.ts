import {
  activeContext,
  anyAvailableDieHasMove,
  anyDiscardedDieHasMove,
  blueBonusOptions,
  bonusBrownLegal,
  bonusHasAnyPlaceableValue,
  bonusYellowLegal,
  colorAvailability,
  dieHasAnyLegalMove,
  passiveContext,
} from "./rules";
import {
  ACTING_COLORS,
  ALL_DIE_COLORS,
  type DieColor,
  type GameAction,
  type GameState,
} from "./types";

/** True when player 1’s last passive of the global turn is done and bonuses have drained. */
export function isGlobalTurnComplete(state: GameState): boolean {
  return (
    state.phase.kind === "passive" &&
    state.phase.done &&
    state.phase.player === 1 &&
    !state.bonusResolution &&
    !state.pinkChoice &&
    state.pendingBonuses.length === 0 &&
    !state.pendingAdvance
  );
}

/** How many autoplay turns may still be requested from this state. */
export function remainingAutoplayTurns(state: GameState): number {
  if (state.phase.kind === "game-over") return 0;
  if (isGlobalTurnComplete(state)) return Math.max(0, 6 - state.globalTurn);
  return Math.max(0, 7 - state.globalTurn);
}

function randomOf<T>(items: T[]): T {
  return items[Math.floor(Math.random() * items.length)];
}

/**
 * Every GameAction that is currently legal. Optional spends (relance, joker, +1)
 * appear alongside the choice to proceed without them. Mandatory moves are
 * always included when they exist.
 */
export function legalActions(state: GameState): GameAction[] {
  const { phase } = state;

  if (state.pinkChoice) {
    const acts: GameAction[] = [{ type: "PINK_CHOOSE", option: "points" }];
    if (state.pinkChoice.bonusEffect.kind !== "none") {
      acts.push({ type: "PINK_CHOOSE", option: "bonus" });
    }
    return acts;
  }

  if (state.bonusResolution) {
    const br = state.bonusResolution;
    const board = state.boards[br.owner];
    if (br.stage === "chooseColor") {
      return ACTING_COLORS.map((color) => ({ type: "BONUS_CHOOSE_COLOR" as const, color }));
    }
    if (br.stage === "chooseValue") {
      if (
        (br.color === "yellow" || br.color === "brown" || br.color === "pink") &&
        !bonusHasAnyPlaceableValue(board, br.color)
      ) {
        return [{ type: "BONUS_NOMOVE_DONE" }];
      }
      const values = [1, 2, 3, 4, 5, 6].filter((v) => {
        if (br.color === "yellow") return bonusYellowLegal(board, v).length > 0;
        if (br.color === "brown") return bonusBrownLegal(board, v).length > 0;
        return true;
      });
      if (values.length === 0) return [{ type: "BONUS_NOMOVE_DONE" }];
      return values.map((value) => ({ type: "BONUS_CHOOSE_VALUE" as const, value }));
    }
    if (br.stage === "placing" && br.color === "darkblue") {
      return blueBonusOptions(board).map((opt) => ({
        type: "BONUS_PLACE_BLUE" as const,
        cellId: opt.cellId,
        value: opt.value,
      }));
    }
    if (br.stage === "placing") {
      const sel = state.selection;
      if (sel && sel.picked.length >= 1) return [{ type: "VALIDATE_MOVE" }];
      if (sel) return sel.legal.map((cellId) => ({ type: "PICK_CELL" as const, cellId }));
      return [{ type: "BONUS_NOMOVE_DONE" }];
    }
    if (br.stage === "noMove") return [{ type: "BONUS_NOMOVE_DONE" }];
    return [];
  }

  if (state.selection) {
    const sel = state.selection;
    if (sel.color === "white" && sel.actingColor === null) {
      const ctx =
        phase.kind === "active"
          ? activeContext(state, phase.player, phase.round, "white")
          : phase.kind === "passive"
          ? passiveContext(state, phase.player, "white")
          : phase.kind === "plus1" && state.plus1Active !== null
          ? passiveContext(state, state.plus1Active, "white")
          : null;
      if (!ctx) return [{ type: "CANCEL_SELECTION" }];
      const avail = colorAvailability(sel.value, ctx);
      const colors = ACTING_COLORS.filter((c) => avail[c]);
      if (colors.length === 0) return [{ type: "CANCEL_SELECTION" }];
      return colors.map((actingColor) => ({
        type: "CHOOSE_WHITE_COLOR" as const,
        actingColor,
      }));
    }
    if (sel.actingColor !== null && sel.picked.length >= 1) {
      // A destination is already picked: autoplay must validate, not wait.
      return [{ type: "VALIDATE_MOVE" }];
    }
    if (sel.actingColor !== null) {
      if (sel.legal.length === 0) return [{ type: "CANCEL_SELECTION" }];
      return sel.legal.map((cellId) => ({ type: "PICK_CELL" as const, cellId }));
    }
    return [{ type: "CANCEL_SELECTION" }];
  }

  if (state.jokerPending) {
    if (state.jokerPending.value === null) {
      return [1, 2, 3, 4, 5, 6].map((value) => ({ type: "SET_JOKER_VALUE" as const, value }));
    }
    return ALL_DIE_COLORS.filter((c) => state.dice[c].location === "available").map((color) => ({
      type: "SELECT_DIE" as const,
      color,
    }));
  }

  if (phase.kind === "fill-slots") {
    return ALL_DIE_COLORS.filter((c) => state.dice[c].location === "discarded").map((color) => ({
      type: "FILL_SLOT" as const,
      color,
    }));
  }

  if (phase.kind === "plus1" && state.plus1Active === null) {
    const actor = phase.order[phase.current];
    const pb = state.boards[actor].bonuses.plus1;
    const acts: GameAction[] = [{ type: "PLUS1_SKIP" }];
    if (pb.unlocked > pb.used) acts.unshift({ type: "PLUS1_USE" });
    return acts;
  }

  if (phase.kind === "plus1" && state.plus1Active !== null) {
    const actor = state.plus1Active;
    const already = new Set(state.plus1UsedDice[actor]);
    const selectable = ALL_DIE_COLORS.filter((color) => {
      if (already.has(color)) return false;
      return dieHasAnyLegalMove(color, passiveContext(state, actor, color));
    });
    if (selectable.length === 0) return [{ type: "PLUS1_SKIP" }];
    return selectable.map((color) => ({ type: "SELECT_DIE" as const, color }));
  }

  if (phase.kind === "passive" && phase.done) {
    return [{ type: "CONTINUE" }];
  }

  if (phase.kind === "passive" && !phase.done) {
    const discardedOk = anyDiscardedDieHasMove(state, phase.player);
    const pool = discardedOk ? "discarded" : "chosen";
    const selectable = ALL_DIE_COLORS.filter((c) => {
      if (state.dice[c].location !== pool) return false;
      return dieHasAnyLegalMove(c, passiveContext(state, phase.player, c));
    });
    if (selectable.length === 0) return [{ type: "PASS_PASSIVE" }];
    return selectable.map((color) => ({ type: "SELECT_DIE" as const, color }));
  }

  if (phase.kind === "active") {
    const acts: GameAction[] = [];
    const board = state.boards[phase.player];
    const availableCount = ALL_DIE_COLORS.filter(
      (c) => state.dice[c].location === "available"
    ).length;
    if (
      availableCount > 0 &&
      board.bonuses.relance.unlocked > board.bonuses.relance.used
    ) {
      acts.push({ type: "USE_RELANCE" });
    }
    if (
      availableCount > 0 &&
      board.bonuses.joker.unlocked > board.bonuses.joker.used
    ) {
      acts.push({ type: "START_JOKER", tokenIndex: board.bonuses.joker.used });
    }
    for (const color of ALL_DIE_COLORS) {
      if (state.dice[color].location !== "available") continue;
      if (dieHasAnyLegalMove(color, activeContext(state, phase.player, phase.round, color))) {
        acts.push({ type: "SELECT_DIE", color });
      }
    }
    if (!anyAvailableDieHasMove(state, phase.player, phase.round)) {
      acts.push({ type: "END_TURN" });
    }
    return acts;
  }

  return [];
}

export type MaxDieAllowReason = "aucun inférieur jouable" | "toutes les valeurs égales";

export interface AutoplayDecisionMeta {
  playable: DieColor[];
  excluded: DieColor[];
  chosenDie: DieColor | null;
  maxAllowedReason: MaxDieAllowReason | null;
}

function emptyMeta(): AutoplayDecisionMeta {
  return { playable: [], excluded: [], chosenDie: null, maxAllowedReason: null };
}

function selectDieColors(acts: GameAction[]): DieColor[] {
  return acts.filter((a): a is { type: "SELECT_DIE"; color: DieColor } => a.type === "SELECT_DIE").map(
    (a) => a.color
  );
}

/**
 * Autoplay-only: on active rounds 1–2, drop max-physical-value dice when a
 * strictly lower playable die exists. Does not apply during a pending joker.
 */
export function restrictActiveDieSelect(
  state: GameState,
  acts: GameAction[]
): { acts: GameAction[]; meta: AutoplayDecisionMeta } {
  const selectActs = acts.filter((a): a is { type: "SELECT_DIE"; color: DieColor } => a.type === "SELECT_DIE");
  const rest = acts.filter((a) => a.type !== "SELECT_DIE");
  const playable = selectDieColors(selectActs);
  const baseMeta: AutoplayDecisionMeta = {
    playable,
    excluded: [],
    chosenDie: null,
    maxAllowedReason: null,
  };

  const { phase } = state;
  if (
    phase.kind !== "active" ||
    phase.round > 2 ||
    state.jokerPending ||
    selectActs.length === 0
  ) {
    return { acts, meta: baseMeta };
  }

  const available = ALL_DIE_COLORS.filter((c) => state.dice[c].location === "available");
  if (available.length === 0) return { acts, meta: baseMeta };

  const maxPhys = Math.max(...available.map((c) => state.dice[c].value));
  const allEqual = available.every((c) => state.dice[c].value === maxPhys);
  const lower = selectActs.filter((a) => state.dice[a.color].value < maxPhys);

  if (lower.length > 0) {
    const excluded = playable.filter((c) => state.dice[c].value === maxPhys);
    return {
      acts: [...rest, ...lower],
      meta: { playable, excluded, chosenDie: null, maxAllowedReason: null },
    };
  }

  return {
    acts,
    meta: {
      playable,
      excluded: [],
      chosenDie: null,
      maxAllowedReason: allEqual ? "toutes les valeurs égales" : "aucun inférieur jouable",
    },
  };
}

export function pickRandomAction(state: GameState): GameAction | null {
  return pickAutoplayAction(state).action;
}

export function pickAutoplayAction(state: GameState): {
  action: GameAction | null;
  meta: AutoplayDecisionMeta;
} {
  const raw = legalActions(state);
  if (raw.length === 0) return { action: null, meta: emptyMeta() };
  if (raw.some((a) => a.type === "VALIDATE_MOVE")) {
    return { action: { type: "VALIDATE_MOVE" }, meta: emptyMeta() };
  }
  const { acts, meta } = restrictActiveDieSelect(state, raw);
  if (acts.length === 0) return { action: null, meta };
  const action = randomOf(acts);
  return {
    action,
    meta: {
      ...meta,
      chosenDie: action.type === "SELECT_DIE" ? action.color : null,
    },
  };
}

function fingerprint(state: GameState): string {
  return JSON.stringify({
    phase: state.phase,
    dice: state.dice,
    sel: state.selection,
    plus1: state.plus1Active,
    plus1UsedDice: state.plus1UsedDice,
    joker: state.jokerPending,
    pending: state.pendingBonuses,
    br: state.bonusResolution,
    pink: state.pinkChoice,
    adv: state.pendingAdvance,
    b1: state.boards[1].checks,
    b1v: state.boards[1].values,
    b1s: state.boards[1].bonuses,
    b1slots: state.boards[1].slots,
    b2: state.boards[2].checks,
    b2v: state.boards[2].values,
    b2s: state.boards[2].bonuses,
    b2slots: state.boards[2].slots,
    turn: state.globalTurn,
    msg: state.message,
  });
}

export const AUTOPLAY_STEP_CAP = 8000;

export interface AutoplayStepResult {
  action: GameAction | null;
  stop: boolean;
  reason: string | null;
  meta: AutoplayDecisionMeta | null;
}

/**
 * Decide the next autoplay action. `completed` is how many global turns have
 * finished since autoplay started. Stop before CONTINUE that would start a
 * turn beyond the quota (except turn 6 → game-over).
 */
export function nextAutoplayAction(
  state: GameState,
  completed: number,
  quota: number
): AutoplayStepResult {
  if (state.phase.kind === "game-over") {
    return { action: null, stop: true, reason: null, meta: null };
  }
  if (isGlobalTurnComplete(state) && completed >= quota) {
    if (state.globalTurn >= 6) {
      return { action: { type: "CONTINUE" }, stop: false, reason: null, meta: emptyMeta() };
    }
    return { action: null, stop: true, reason: null, meta: null };
  }
  const picked = pickAutoplayAction(state);
  if (!picked.action) {
    return {
      action: null,
      stop: true,
      reason: "Aucune action légale (blocage).",
      meta: picked.meta,
    };
  }
  return { action: picked.action, stop: false, reason: null, meta: picked.meta };
}

export function stateFingerprint(state: GameState): string {
  return fingerprint(state);
}
