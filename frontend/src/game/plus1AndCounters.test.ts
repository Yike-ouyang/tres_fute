import { describe, expect, it } from "vitest";
import {
  applyUnlocks,
  emptyBonusState,
  TOTAL_JOKERS,
  TOTAL_PLUS1,
  TOTAL_RELANCE,
} from "./bonuses";
import { legalActions } from "./autoplay";
import { gameReducer } from "./reducer";
import { legalDestinations } from "./rules";
import { computeScore } from "./score";
import {
  ALL_DIE_COLORS,
  emptyPlus1UsedDice,
  type DieColor,
  type DieRuntime,
  type GameState,
  type PlayerBoard,
} from "./types";

function emptyBoard(): PlayerBoard {
  return {
    checks: {},
    values: {},
    brownLastChecked: null,
    brownDisabled: {},
    chosenThisTurn: [],
    slots: [null, null, null],
    bonuses: emptyBonusState(),
  };
}

function allDice(
  overrides: Partial<Record<DieColor, DieRuntime>> = {}
): Record<DieColor, DieRuntime> {
  const dice = {} as Record<DieColor, DieRuntime>;
  for (const color of ALL_DIE_COLORS) {
    dice[color] = overrides[color] ?? { value: 1, location: "discarded" };
  }
  return dice;
}

function plus1State(overrides: Partial<GameState> = {}): GameState {
  const board = emptyBoard();
  board.bonuses = { ...emptyBonusState(), plus1: { unlocked: 2, used: 0 } };
  const board2 = emptyBoard();
  board2.bonuses = { ...emptyBonusState(), plus1: { unlocked: 1, used: 0 } };
  return {
    globalTurn: 1,
    phase: { kind: "plus1", order: [1, 2], current: 0 },
    boards: { 1: board, 2: board2 },
    dice: allDice({
      yellow: { value: 6, location: "discarded" },
      brown: { value: 5, location: "discarded" },
    }),
    selection: {
      color: "yellow",
      value: 6,
      actingColor: "yellow",
      legal: ["yellow-r1-c6"],
      picked: ["yellow-r1-c6"],
      maxPick: 1,
      eliminationValue: 6,
    },
    message: null,
    plus1Active: 1,
    plus1UsedDice: emptyPlus1UsedDice(),
    jokerPending: null,
    pendingBonuses: [],
    bonusResolution: null,
    pinkChoice: null,
    pendingAdvance: null,
    ...overrides,
  };
}

describe("counter track lengths", () => {
  it("has 7 slots for relance, joker and +1", () => {
    expect(TOTAL_RELANCE).toBe(7);
    expect(TOTAL_JOKERS).toBe(7);
    expect(TOTAL_PLUS1).toBe(7);
  });

  it("grants a fox when the 7th relance is unlocked", () => {
    const board = emptyBoard();
    board.bonuses = { ...emptyBonusState(), relance: { unlocked: 7, used: 0 } };
    const { board: next, dieBonuses } = applyUnlocks(board);
    expect(next.bonuses.slotsUnlocked["counter-relance-all"]).toBe(true);
    expect(dieBonuses).toEqual([]);
    expect(computeScore(next).foxCount).toBe(1);
  });

  it("does not grant the brown die at 4 jokers", () => {
    const board = emptyBoard();
    board.bonuses = { ...emptyBonusState(), joker: { unlocked: 4, used: 0 } };
    const { board: next, dieBonuses } = applyUnlocks(board);
    expect(next.bonuses.slotsUnlocked["counter-joker-all"]).toBeUndefined();
    expect(dieBonuses).toEqual([]);
  });

  it("grants the brown die when the 7th joker is unlocked", () => {
    const board = emptyBoard();
    board.bonuses = { ...emptyBonusState(), joker: { unlocked: 7, used: 0 } };
    const { dieBonuses, board: next } = applyUnlocks(board);
    expect(next.bonuses.slotsUnlocked["counter-joker-all"]).toBe(true);
    expect(dieBonuses).toEqual(["brown"]);
  });

  it("grants the pink die when the 7th +1 is unlocked", () => {
    const board = emptyBoard();
    board.bonuses = { ...emptyBonusState(), plus1: { unlocked: 7, used: 0 } };
    const { dieBonuses, board: next } = applyUnlocks(board);
    expect(next.bonuses.slotsUnlocked["counter-plus1-all"]).toBe(true);
    expect(dieBonuses).toEqual(["pink"]);
  });
});

describe("turquoise same-group counting", () => {
  const board = emptyBoard();

  it("counts other chosen dice when the selected die is chosen", () => {
    const ctx = {
      mode: "passive" as const,
      board,
      dice: allDice({
        turquoise: { value: 4, location: "chosen" },
        yellow: { value: 4, location: "chosen" },
        pink: { value: 4, location: "discarded" },
        brown: { value: 4, location: "discarded" },
      }),
      round: 0,
      selectedColor: "turquoise" as const,
    };
    expect(legalDestinations("turquoise", 4, ctx).maxPick).toBe(2);
  });

  it("counts other discarded dice when the selected die is discarded", () => {
    const ctx = {
      mode: "passive" as const,
      board,
      dice: allDice({
        turquoise: { value: 4, location: "discarded" },
        yellow: { value: 4, location: "chosen" },
        pink: { value: 4, location: "discarded" },
        brown: { value: 4, location: "discarded" },
      }),
      round: 0,
      selectedColor: "turquoise" as const,
    };
    expect(legalDestinations("turquoise", 4, ctx).maxPick).toBe(3);
  });
});

describe("+1 chaining and unique dice", () => {
  it("keeps the same actor after a successful +1 if they have another", () => {
    const after = gameReducer(plus1State(), { type: "VALIDATE_MOVE" });
    expect(after.boards[1].checks["yellow-r1-c6"]).toBe(true);
    expect(after.boards[1].bonuses.plus1.used).toBe(1);
    expect(after.plus1UsedDice[1]).toEqual(["yellow"]);
    expect(after.plus1Active).toBeNull();
    expect(after.phase).toEqual({ kind: "plus1", order: [1, 2], current: 0 });
    const acts = legalActions(after);
    expect(acts.some((a) => a.type === "PLUS1_USE")).toBe(true);
    expect(acts.some((a) => a.type === "PLUS1_SKIP")).toBe(true);
  });

  it("rejects a second +1 on the same die for that player", () => {
    let state = gameReducer(plus1State(), { type: "VALIDATE_MOVE" });
    state = gameReducer(state, { type: "PLUS1_USE" });
    const rejected = gameReducer(state, { type: "SELECT_DIE", color: "yellow" });
    expect(rejected.selection).toBeNull();
    const allowed = gameReducer(state, { type: "SELECT_DIE", color: "brown" });
    expect(allowed.selection?.color).toBe("brown");
  });

  it("lets the other player still target a die J1 already replayed", () => {
    let state = gameReducer(plus1State(), { type: "VALIDATE_MOVE" });
    state = gameReducer(state, { type: "PLUS1_SKIP" });
    state = gameReducer(state, { type: "PLUS1_USE" });
    expect(state.plus1Active).toBe(2);
    const picked = gameReducer(state, { type: "SELECT_DIE", color: "yellow" });
    expect(picked.selection?.color).toBe("yellow");
  });
});
