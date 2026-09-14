import { describe, expect, it } from "vitest";
import { emptyBonusState } from "./bonuses";
import { gameReducer } from "./reducer";
import { pinkValue } from "./rules";
import { computeScore } from "./score";
import {
  ALL_DIE_COLORS,
  type DieColor,
  type DieRuntime,
  type GameState,
  type PlayerBoard,
  type Selection,
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
    dice[color] = overrides[color] ?? { value: 1, location: "available" };
  }
  return dice;
}

function pinkSelection(value: number, dest = "pink-cell-1", eliminationValue = value): Selection {
  return {
    color: "pink",
    value,
    actingColor: "pink",
    legal: [dest],
    picked: [dest],
    maxPick: 1,
    eliminationValue,
  };
}

function baseState(overrides: Partial<GameState> = {}): GameState {
  return {
    globalTurn: 1,
    phase: { kind: "active", player: 1, round: 1 },
    boards: { 1: emptyBoard(), 2: emptyBoard() },
    dice: allDice({ pink: { value: 4, location: "available" } }),
    selection: pinkSelection(4),
    message: null,
    plus1Active: null,
    plus1UsedDice: { 1: [], 2: [] },
    jokerPending: null,
    pendingBonuses: [],
    bonusResolution: null,
    pinkChoice: null,
    pendingAdvance: null,
    ...overrides,
  };
}

describe("pinkValue", () => {
  it("maps 1..6 to ceil(v/2)", () => {
    expect([1, 2, 3, 4, 5, 6].map(pinkValue)).toEqual([1, 1, 2, 2, 3, 3]);
  });
});

describe("first pink cell inscription", () => {
  it("writes ceil(v/2) for an even value and skips the points/bonus dialog", () => {
    const after = gameReducer(baseState(), { type: "VALIDATE_MOVE" });
    expect(after.boards[1].values["pink-cell-1"]).toBe(2);
    expect(after.pinkChoice).toBeNull();
    expect(after.boards[1].bonuses).toEqual(emptyBonusState());
    expect(computeScore(after.boards[1]).pink).toBe(2);
  });

  it("writes ceil(v/2) for an odd value", () => {
    const after = gameReducer(
      baseState({
        dice: allDice({ pink: { value: 5, location: "available" } }),
        selection: pinkSelection(5),
      }),
      { type: "VALIDATE_MOVE" }
    );
    expect(after.boards[1].values["pink-cell-1"]).toBe(3);
    expect(after.pinkChoice).toBeNull();
    expect(computeScore(after.boards[1]).pink).toBe(3);
  });

  it("uses the joker effective value, not the physical roll", () => {
    const withJoker = emptyBoard();
    withJoker.bonuses = {
      ...emptyBonusState(),
      joker: { unlocked: 1, used: 0 },
    };
    let state = baseState({
      boards: { 1: withJoker, 2: emptyBoard() },
      dice: allDice({ pink: { value: 6, location: "available" } }),
      selection: null,
    });
    state = gameReducer(state, { type: "START_JOKER", tokenIndex: 0 });
    expect(state.jokerPending).toEqual({ tokenIndex: 0, value: 3 });
    state = gameReducer(state, { type: "SELECT_DIE", color: "pink" });
    expect(state.selection?.value).toBe(3);
    expect(state.selection?.eliminationValue).toBe(6);
    expect(state.boards[1].bonuses.joker.used).toBe(1);
    state = gameReducer(state, { type: "VALIDATE_MOVE" });
    expect(state.boards[1].values["pink-cell-1"]).toBe(2);
    expect(state.pinkChoice).toBeNull();
    expect(computeScore(state.boards[1]).pink).toBe(2);
  });

  it("uses the chosen value of an immediate pink bonus die", () => {
    const after = gameReducer(
      baseState({
        selection: null,
        bonusResolution: {
          owner: 1,
          originColor: "pink",
          color: "pink",
          stage: "chooseValue",
          value: null,
        },
      }),
      { type: "BONUS_CHOOSE_VALUE", value: 5 }
    );
    expect(after.boards[1].values["pink-cell-1"]).toBe(3);
    expect(after.pinkChoice).toBeNull();
    expect(after.bonusResolution).toBeNull();
    expect(after.boards[1].bonuses.slotsUnlocked).toEqual({});
    expect(computeScore(after.boards[1]).pink).toBe(3);
  });

  it("does not divide the inscribed value again when scoring", () => {
    const board = emptyBoard();
    board.values = { "pink-cell-1": 3 };
    expect(computeScore(board).pink).toBe(3);
    expect(computeScore(board).pink).not.toBe(pinkValue(3));
  });

  it("still opens the points/bonus dialog on cell 2", () => {
    const board = emptyBoard();
    board.values = { "pink-cell-1": 2 };
    const after = gameReducer(
      baseState({
        boards: { 1: board, 2: emptyBoard() },
        selection: pinkSelection(4, "pink-cell-2"),
      }),
      { type: "VALIDATE_MOVE" }
    );
    expect(after.boards[1].values["pink-cell-2"]).toBeUndefined();
    expect(after.pinkChoice).toMatchObject({
      position: 2,
      effectiveValue: 4,
      multiplier: 1,
      cellId: "pink-cell-2",
    });
  });
});
