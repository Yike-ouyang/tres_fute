import { BROWN_NUMBERS } from "../boardData";
import {
  ACTING_COLORS,
  ALL_DIE_COLORS,
  effectiveValue,
  type ActingColor,
  type DieColor,
  type DieRuntime,
  type GameState,
  type PlayerBoard,
} from "./types";

/** A random integer die value between 1 and 6. */
export function rollValue(): number {
  return Math.floor(Math.random() * 6) + 1;
}

export interface LegalResult {
  /** Highlighted destination cell ids (unprefixed). */
  legal: string[];
  /** Maximum number of cells the player may pick (turquoise cap; 1 otherwise). */
  maxPick: number;
}

/** Context describing how a move is being evaluated. */
export interface MoveContext {
  mode: "active" | "passive";
  board: PlayerBoard;
  dice: Record<DieColor, DieRuntime>;
  /** Active yellow uses this as the row. Ignored in passive mode. */
  round: number;
  /** The die being played; used to exclude it from the passive turquoise count. */
  selectedColor: DieColor;
}

const TURQUOISE_ROWS = [1, 2, 3, 4, 5];
const BLUE_RIGHT = [8, 9, 10, 11, 12, 13];
const BLUE_LEFT = [6, 5, 4, 3, 2, 1];

/** Passive-yellow destination per die value: manche is irrelevant. */
const PASSIVE_YELLOW_CELL: Record<number, string> = {
  1: "yellow-r3-c1",
  2: "yellow-r3-c2",
  3: "yellow-r2-c3",
  4: "yellow-r2-c4",
  5: "yellow-r1-c5",
  6: "yellow-r1-c6",
};

/** The six cells reachable by a passive yellow die (for styling on both boards). */
export const PASSIVE_YELLOW_CELLS: string[] = Object.values(PASSIVE_YELLOW_CELL);

/** The blue sum is always darkblue + white (effective values, so jokers count). */
export function blueSum(dice: Record<DieColor, DieRuntime>): number {
  return effectiveValue(dice.darkblue) + effectiveValue(dice.white);
}

interface BranchInfo {
  nextFree: string | null;
  ref: number;
}

function branchInfo(
  values: Record<string, number>,
  positions: number[]
): BranchInfo {
  let ref = 7;
  let nextFree: string | null = null;
  for (const p of positions) {
    const id = `blue-cell-${p}`;
    if (values[id] !== undefined) {
      ref = values[id];
    } else {
      nextFree = id;
      break;
    }
  }
  return { nextFree, ref };
}

function legalBlue(ctx: MoveContext): string[] {
  const sum = blueSum(ctx.dice);
  const values = ctx.board.values;
  const legal: string[] = [];
  const right = branchInfo(values, BLUE_RIGHT);
  if (right.nextFree && (sum === right.ref + 1 || sum === 7)) {
    legal.push(right.nextFree);
  }
  const left = branchInfo(values, BLUE_LEFT);
  if (left.nextFree && (sum === left.ref - 1 || sum === 7)) {
    legal.push(left.nextFree);
  }
  return legal;
}

/** First empty pink cell, left to right, or null when the track is full. */
export function firstEmptyPink(values: Record<string, number>): string | null {
  for (let n = 1; n <= 12; n++) {
    const id = `pink-cell-${n}`;
    if (values[id] === undefined) return id;
  }
  return null;
}

/**
 * Legal destinations for a die acting as a given color with a given value, in a
 * given context (active or passive). Pure: never mutates state.
 */
export function legalDestinations(
  actingColor: ActingColor,
  value: number,
  ctx: MoveContext
): LegalResult {
  const { board } = ctx;
  switch (actingColor) {
    case "yellow": {
      const id =
        ctx.mode === "passive"
          ? PASSIVE_YELLOW_CELL[value]
          : `yellow-r${ctx.round}-c${value}`;
      return { legal: id && !board.checks[id] ? [id] : [], maxPick: 1 };
    }
    case "turquoise": {
      const free = TURQUOISE_ROWS.map((r) => `turquoise-r${r}-c${value}`).filter(
        (id) => !board.checks[id]
      );
      let sameValue: number;
      if (ctx.mode === "passive") {
        sameValue = ALL_DIE_COLORS.filter(
          (c) =>
            c !== ctx.selectedColor &&
            ctx.dice[c].location === "discarded" &&
            effectiveValue(ctx.dice[c]) === value
        ).length;
      } else {
        sameValue = board.chosenThisTurn.filter((d) => d.value === value).length;
      }
      const cap = 1 + sameValue;
      const maxPick = Math.min(cap, free.length);
      return { legal: free, maxPick };
    }
    case "pink": {
      const target = firstEmptyPink(board.values);
      return { legal: target ? [target] : [], maxPick: 1 };
    }
    case "darkblue": {
      return { legal: legalBlue(ctx), maxPick: 1 };
    }
    case "brown": {
      const start = board.brownLastChecked ?? 0;
      const legal: string[] = [];
      for (let i = 0; i < BROWN_NUMBERS.length; i++) {
        const n = i + 1;
        if (n <= start) continue;
        const id = `brown-cell-${n}`;
        if (BROWN_NUMBERS[i] === value && !board.checks[id]) {
          legal.push(id);
        }
      }
      return { legal, maxPick: 1 };
    }
    default:
      return { legal: [], maxPick: 1 };
  }
}

/** The value written for a pink move when taking the bonus (half, rounded up). */
export function pinkValue(dieValue: number): number {
  return Math.ceil(dieValue / 2);
}

/** The value written for a pink move when taking the points (value x multiplier). */
export function pinkPoints(effectiveValue: number, multiplier: number): number {
  return effectiveValue * multiplier;
}

// ---- Immediate colored bonus-die placement helpers ----

/** Yellow bonus die: any unchecked yellow cell in the die's column (free row). */
export function bonusYellowLegal(board: PlayerBoard, value: number): string[] {
  const legal: string[] = [];
  for (let r = 1; r <= 3; r++) {
    const id = `yellow-r${r}-c${value}`;
    if (!board.checks[id]) legal.push(id);
  }
  return legal;
}

/** Turquoise bonus die: check any one unchecked turquoise cell. */
export function allUncheckedTurquoise(board: PlayerBoard): string[] {
  const legal: string[] = [];
  for (const r of TURQUOISE_ROWS) {
    for (let c = 1; c <= 6; c++) {
      const id = `turquoise-r${r}-c${c}`;
      if (!board.checks[id]) legal.push(id);
    }
  }
  return legal;
}

/** Brown bonus die: a legal brown cell of the chosen number, respecting progression. */
export function bonusBrownLegal(board: PlayerBoard, value: number): string[] {
  const start = board.brownLastChecked ?? 0;
  const legal: string[] = [];
  for (let i = 0; i < BROWN_NUMBERS.length; i++) {
    const n = i + 1;
    if (n <= start) continue;
    const id = `brown-cell-${n}`;
    if (BROWN_NUMBERS[i] === value && !board.checks[id]) legal.push(id);
  }
  return legal;
}

/** A single dark-blue bonus option: which cell to fill and the value to write. */
export interface BlueBonusOption {
  cellId: string;
  value: number;
}

/**
 * Dark-blue bonus die: write a regulation value into the next-free cell of either
 * branch. Each open branch accepts its stepped value (ref-1 left / ref+1 right)
 * and the wildcard 7.
 */
export function blueBonusOptions(board: PlayerBoard): BlueBonusOption[] {
  const values = board.values;
  const options: BlueBonusOption[] = [];
  const push = (cellId: string | null, value: number) => {
    if (!cellId || value < 1) return;
    if (options.some((o) => o.cellId === cellId && o.value === value)) return;
    options.push({ cellId, value });
  };
  const left = branchInfo(values, BLUE_LEFT);
  push(left.nextFree, left.ref - 1);
  push(left.nextFree, 7);
  const right = branchInfo(values, BLUE_RIGHT);
  push(right.nextFree, right.ref + 1);
  push(right.nextFree, 7);
  return options;
}

/** Whether a colored bonus die can still be placed for at least one value. */
export function bonusHasAnyPlaceableValue(
  board: PlayerBoard,
  color: "yellow" | "brown" | "pink"
): boolean {
  if (color === "pink") return firstEmptyPink(board.values) !== null;
  return [1, 2, 3, 4, 5, 6].some((v) =>
    color === "yellow"
      ? bonusYellowLegal(board, v).length > 0
      : bonusBrownLegal(board, v).length > 0
  );
}

/** Availability of each acting color for a die's value in the given context. */
export function colorAvailability(
  value: number,
  ctx: MoveContext
): Record<ActingColor, boolean> {
  const result = {} as Record<ActingColor, boolean>;
  for (const color of ACTING_COLORS) {
    result[color] = legalDestinations(color, value, ctx).legal.length > 0;
  }
  return result;
}

/** Whether a die (by permanent color) has any legal move in the given context. */
export function dieHasAnyLegalMove(color: DieColor, ctx: MoveContext): boolean {
  const value = effectiveValue(ctx.dice[color]);
  const localCtx: MoveContext = { ...ctx, selectedColor: color };
  if (color === "white") {
    return ACTING_COLORS.some(
      (c) => legalDestinations(c, value, localCtx).legal.length > 0
    );
  }
  return legalDestinations(color, value, localCtx).legal.length > 0;
}

/** Build a move context for the active player's board. */
export function activeContext(
  state: GameState,
  player: number,
  round: number,
  selectedColor: DieColor
): MoveContext {
  return {
    mode: "active",
    board: state.boards[player as 1 | 2],
    dice: state.dice,
    round,
    selectedColor,
  };
}

/** Build a move context for the passive player's board. */
export function passiveContext(
  state: GameState,
  player: number,
  selectedColor: DieColor
): MoveContext {
  return {
    mode: "passive",
    board: state.boards[player as 1 | 2],
    dice: state.dice,
    round: 0,
    selectedColor,
  };
}

/** Whether any available die has a legal move for the active player. */
export function anyAvailableDieHasMove(
  state: GameState,
  player: number,
  round: number
): boolean {
  return ALL_DIE_COLORS.some((color) => {
    if (state.dice[color].location !== "available") return false;
    return dieHasAnyLegalMove(color, activeContext(state, player, round, color));
  });
}

/** Whether any discarded (grey-square) die has a legal passive move. */
export function anyDiscardedDieHasMove(state: GameState, player: number): boolean {
  return ALL_DIE_COLORS.some((color) => {
    if (state.dice[color].location !== "discarded") return false;
    return dieHasAnyLegalMove(color, passiveContext(state, player, color));
  });
}

/** Whether any chosen (active-slot) die has a legal passive move. */
export function anyChosenDieHasMove(state: GameState, player: number): boolean {
  return ALL_DIE_COLORS.some((color) => {
    if (state.dice[color].location !== "chosen") return false;
    return dieHasAnyLegalMove(color, passiveContext(state, player, color));
  });
}

/** Whether any of the six dice has a legal passive move. */
export function anyDieHasPassiveMove(state: GameState, player: number): boolean {
  return anyDiscardedDieHasMove(state, player) || anyChosenDieHasMove(state, player);
}
