import { FOX_SLOT_IDS } from "./bonuses";
import type { PlayerBoard } from "./types";

/** Points for a yellow row given how many of its 6 cells are checked. */
const YELLOW_ROW = [0, 2, 6, 12, 20, 30, 42];
/** Points for a turquoise row given how many of its 6 cells are checked. */
const TURQUOISE_ROW = [0, 1, 3, 6, 10, 15, 21];
/** Progression points for a blue branch given how many cells are filled from the centre. */
const BLUE_BRANCH = [0, 3, 6, 9, 13, 17, 22];
/** Brown track score from total checked cells (skipped cells do not count). */
const BROWN_TOTAL = [0, 3, 5, 9, 14, 20, 27, 35, 44, 54, 65, 77, 90];

const BLUE_LEFT = [6, 5, 4, 3, 2, 1];
const BLUE_RIGHT = [8, 9, 10, 11, 12, 13];
const BLUE_SPECIAL = new Set([2, 3, 4, 10, 11, 12]);

export interface PlayerScore {
  yellow: number;
  turquoise: number;
  blue: number;
  brown: number;
  pink: number;
  colorSubtotal: number;
  foxCount: number;
  foxValue: number;
  foxPoints: number;
  total: number;
}

function yellowScore(board: PlayerBoard): number {
  let sum = 0;
  for (let r = 1; r <= 3; r++) {
    let n = 0;
    for (let c = 1; c <= 6; c++) {
      if (board.checks[`yellow-r${r}-c${c}`]) n++;
    }
    sum += YELLOW_ROW[n];
  }
  return sum;
}

function turquoiseScore(board: PlayerBoard): number {
  let sum = 0;
  for (let r = 1; r <= 5; r++) {
    let n = 0;
    for (let c = 1; c <= 6; c++) {
      if (board.checks[`turquoise-r${r}-c${c}`]) n++;
    }
    sum += TURQUOISE_ROW[n];
  }
  return sum;
}

function countFilled(board: PlayerBoard, positions: number[]): number {
  return positions.filter((p) => board.values[`blue-cell-${p}`] !== undefined).length;
}

function blueScore(board: PlayerBoard): number {
  const left = BLUE_BRANCH[countFilled(board, BLUE_LEFT)];
  const right = BLUE_BRANCH[countFilled(board, BLUE_RIGHT)];
  let specials = 0;
  for (const p of [...BLUE_LEFT, ...BLUE_RIGHT]) {
    const v = board.values[`blue-cell-${p}`];
    if (v !== undefined && BLUE_SPECIAL.has(v)) specials++;
  }
  return left + right + 4 * specials;
}

function brownScore(board: PlayerBoard): number {
  let n = 0;
  for (let i = 1; i <= 12; i++) {
    if (board.checks[`brown-cell-${i}`]) n++;
  }
  return BROWN_TOTAL[n];
}

function pinkScore(board: PlayerBoard): number {
  let sum = 0;
  for (let i = 1; i <= 12; i++) {
    const v = board.values[`pink-cell-${i}`];
    if (v !== undefined) sum += v;
  }
  return sum;
}

function foxCount(board: PlayerBoard): number {
  return FOX_SLOT_IDS.filter((id) => board.bonuses.slotsUnlocked[id]).length;
}

/**
 * Pure score of one player's board. Computed from checks/values/slotsUnlocked
 * only — never from a running total.
 */
export function computeScore(board: PlayerBoard): PlayerScore {
  const yellow = yellowScore(board);
  const turquoise = turquoiseScore(board);
  const blue = blueScore(board);
  const brown = brownScore(board);
  const pink = pinkScore(board);
  const colorSubtotal = yellow + turquoise + blue + brown + pink;
  const foxes = foxCount(board);
  const foxValue = Math.min(yellow, turquoise, blue, brown, pink);
  const foxPoints = foxes * foxValue;
  return {
    yellow,
    turquoise,
    blue,
    brown,
    pink,
    colorSubtotal,
    foxCount: foxes,
    foxValue,
    foxPoints,
    total: colorSubtotal + foxPoints,
  };
}
