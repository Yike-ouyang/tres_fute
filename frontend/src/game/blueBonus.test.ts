import { describe, expect, it } from "vitest";
import { emptyBonusState } from "./bonuses";
import { blueBonusOptions } from "./rules";
import type { PlayerBoard } from "./types";

function boardWithValues(values: Record<string, number>): PlayerBoard {
  return {
    checks: {},
    values,
    brownLastChecked: null,
    brownDisabled: {},
    chosenThisTurn: [],
    slots: [null, null, null],
    bonuses: emptyBonusState(),
  };
}

describe("blueBonusOptions cap", () => {
  it("allows the stepped value 12 while ref = 11 on the right branch", () => {
    const options = blueBonusOptions(boardWithValues({ "blue-cell-8": 8, "blue-cell-9": 9, "blue-cell-10": 10, "blue-cell-11": 11 }));
    expect(options).toContainEqual({ cellId: "blue-cell-12", value: 12 });
    expect(options).toContainEqual({ cellId: "blue-cell-12", value: 7 });
  });

  it("drops the stepped value above 12 (ref = 12 -> only the wildcard 7)", () => {
    const options = blueBonusOptions(
      boardWithValues({ "blue-cell-8": 8, "blue-cell-9": 9, "blue-cell-10": 10, "blue-cell-11": 11, "blue-cell-12": 12 })
    );
    expect(options).toContainEqual({ cellId: "blue-cell-13", value: 7 });
    expect(options.some((o) => o.value > 12)).toBe(false);
    expect(options.some((o) => o.cellId === "blue-cell-13" && o.value === 13)).toBe(false);
  });

  it("never proposes a value outside 1..12 on an open branch", () => {
    const options = blueBonusOptions(boardWithValues({}));
    for (const option of options) {
      expect(option.value).toBeGreaterThanOrEqual(1);
      expect(option.value).toBeLessThanOrEqual(12);
    }
  });
});
