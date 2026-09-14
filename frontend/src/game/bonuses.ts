import {
  type BonusDieColor,
  type BonusEffect,
  type BonusState,
  type CumulativeBonus,
  type PlayerBoard,
} from "./types";

// ---- Bonus effect shorthands ----
const relance: BonusEffect = { kind: "cumulative", bonus: "relance" };
const joker: BonusEffect = { kind: "cumulative", bonus: "joker" };
const plus1: BonusEffect = { kind: "cumulative", bonus: "plus1" };
const none: BonusEffect = { kind: "none" };
const fox: BonusEffect = { kind: "fox" };
const die = (color: BonusDieColor): BonusEffect => ({ kind: "die", color });

/** Stable slot ids for the six fox bonuses (unprefixed; DOM uses p1-/p2-). */
export const FOX_SLOT_IDS = [
  "gold-r1-c6",
  "turqRow-1",
  "blue-13",
  "brownGap-11-12",
  "pink-9",
  "counter-relance-all",
] as const;

/** Joker token value by unlock order: first four are 3,4,5,6, the rest are wild (null). */
export function jokerTokenValue(index: number): number | null {
  const numbered = [3, 4, 5, 6];
  return index < NUMBERED_JOKERS ? numbered[index] : null;
}

export function jokerTokenLabel(index: number): string {
  const v = jokerTokenValue(index);
  return v === null ? "?" : String(v);
}

/** Dark turquoise cells per row (top to bottom): a shrinking triangle. */
export const TURQUOISE_DARK_COUNT = [6, 5, 3, 2, 1];

export function isTurquoiseDark(row: number, col: number): boolean {
  return col <= TURQUOISE_DARK_COUNT[row - 1];
}

export type BonusSource =
  | "turn"
  | "counter"
  | "gold"
  | "turqRow"
  | "turqCol"
  | "blue"
  | "brownGap"
  | "pink";

export interface SlotDef {
  slotId: string;
  source: BonusSource;
  effect: BonusEffect;
  /** Whether the unlock condition holds for this board (excludes the already-unlocked guard). */
  predicate: (b: PlayerBoard) => boolean;
  /** Position metadata used by the UI. */
  meta: Record<string, number>;
}

// ---- Catalog tables ----

const GOLD_ROW1: BonusEffect[] = [relance, joker, die("pink"), plus1, die("turquoise"), fox];
const GOLD_ROW2: BonusEffect[] = [joker, die("turquoise"), die("darkblue"), die("brown"), die("yellow"), plus1];

// Turquoise row bonuses (rows 1..5); row 1 is the fox, row 5 has none.
const TURQ_ROW: BonusEffect[] = [fox, plus1, die("brown"), die("turquoise"), none];
// Turquoise column bonuses left to right (6 columns).
const TURQ_COL: BonusEffect[] = [die("brown"), die("pink"), die("yellow"), joker, die("darkblue"), relance];

const BLUE_BONUS: Record<number, BonusEffect> = {
  1: plus1,
  2: die("pink"),
  4: die("yellow"),
  5: joker,
  9: relance,
  10: die("brown"),
  12: die("turquoise"),
  13: fox,
};

// Brown gaps (left,right cell positions) skipping value-transitions (3,4),(6,4),(2,1)
// which fall between cells 3-4, 6-7 and 9-10.
const BROWN_GAPS: { left: number; right: number; effect: BonusEffect }[] = [
  { left: 1, right: 2, effect: joker },
  { left: 2, right: 3, effect: die("pink") },
  { left: 4, right: 5, effect: relance },
  { left: 5, right: 6, effect: die("turquoise") },
  { left: 7, right: 8, effect: plus1 },
  { left: 8, right: 9, effect: die("darkblue") },
  { left: 10, right: 11, effect: die("yellow") },
  { left: 11, right: 12, effect: fox },
];

const TURN_BONUS: Record<number, BonusEffect> = {
  1: relance,
  2: plus1,
  3: joker,
  4: die("black"),
};

// Pink line: cell 1 has no displayed multiplier (automatic ceil(v/2) write).
export const PINK_MULTIPLIERS = [0, 1, 2, 2, 1, 2, 2, 1, 3, 2, 2, 3];
export const PINK_BONUSES: BonusEffect[] = [
  none,
  relance,
  die("darkblue"),
  plus1,
  joker,
  die("yellow"),
  die("brown"),
  relance,
  fox,
  die("darkblue"),
  die("turquoise"),
  die("black"),
];

// ---- Slot construction ----

function goldSlots(): SlotDef[] {
  const slots: SlotDef[] = [];
  const rows: [number, BonusEffect[]][] = [
    [1, GOLD_ROW1],
    [2, GOLD_ROW2],
  ];
  for (const [betweenRow, effects] of rows) {
    effects.forEach((effect, i) => {
      const col = i + 1;
      const above = `yellow-r${betweenRow}-c${col}`;
      const below = `yellow-r${betweenRow + 1}-c${col}`;
      slots.push({
        slotId: `gold-r${betweenRow}-c${col}`,
        source: "gold",
        effect,
        meta: { betweenRow, col },
        predicate: (b) => !!b.checks[above] && !!b.checks[below],
      });
    });
  }
  return slots;
}

function turquoiseRowSlots(): SlotDef[] {
  return TURQ_ROW.map((effect, i) => {
    const row = i + 1;
    const count = TURQUOISE_DARK_COUNT[row - 1];
    const cells = Array.from({ length: count }, (_, c) => `turquoise-r${row}-c${c + 1}`);
    return {
      slotId: `turqRow-${row}`,
      source: "turqRow" as const,
      effect,
      meta: { row },
      predicate: (b: PlayerBoard) => cells.every((id) => b.checks[id]),
    };
  });
}

function turquoiseColSlots(): SlotDef[] {
  return TURQ_COL.map((effect, i) => {
    const col = i + 1;
    const rows: string[] = [];
    for (let r = 1; r <= TURQUOISE_DARK_COUNT.length; r++) {
      if (isTurquoiseDark(r, col)) rows.push(`turquoise-r${r}-c${col}`);
    }
    return {
      slotId: `turqCol-${col}`,
      source: "turqCol" as const,
      effect,
      meta: { col },
      predicate: (b: PlayerBoard) => rows.every((id) => b.checks[id]),
    };
  });
}

function blueSlots(): SlotDef[] {
  return Object.entries(BLUE_BONUS).map(([posStr, effect]) => {
    const pos = Number(posStr);
    return {
      slotId: `blue-${pos}`,
      source: "blue" as const,
      effect,
      meta: { pos },
      predicate: (b: PlayerBoard) => b.values[`blue-cell-${pos}`] !== undefined,
    };
  });
}

function brownGapSlots(): SlotDef[] {
  return BROWN_GAPS.map(({ left, right, effect }) => ({
    slotId: `brownGap-${left}-${right}`,
    source: "brownGap" as const,
    effect,
    meta: { left, right },
    predicate: (b: PlayerBoard) =>
      !!b.checks[`brown-cell-${left}`] && !!b.checks[`brown-cell-${right}`],
  }));
}

function turnSlots(): SlotDef[] {
  return Object.entries(TURN_BONUS).map(([nStr, effect]) => {
    const n = Number(nStr);
    return {
      slotId: `turn-${n}`,
      source: "turn" as const,
      effect,
      meta: { n },
      predicate: (b: PlayerBoard) => !!b.checks[`turn-${n}`],
    };
  });
}

/** Numbered joker tokens (3,4,5,6); remaining track slots are wild. */
export const NUMBERED_JOKERS = 4;
export const WILD_JOKERS = 3;

function allCatalogEffects(): BonusEffect[] {
  return [
    ...GOLD_ROW1,
    ...GOLD_ROW2,
    ...TURQ_ROW,
    ...TURQ_COL,
    ...Object.values(BLUE_BONUS),
    ...BROWN_GAPS.map((g) => g.effect),
    ...Object.values(TURN_BONUS),
    ...PINK_BONUSES,
  ];
}

function countCumulative(bonus: CumulativeBonus): number {
  return allCatalogEffects().filter((e) => e.kind === "cumulative" && e.bonus === bonus)
    .length;
}

export const TOTAL_RELANCE = countCumulative("relance");
export const TOTAL_JOKERS = countCumulative("joker");
export const TOTAL_PLUS1 = countCumulative("plus1");

function counterSlots(): SlotDef[] {
  return [
    {
      slotId: "counter-relance-all",
      source: "counter",
      effect: fox,
      meta: {},
      predicate: (b) => b.bonuses.relance.unlocked >= TOTAL_RELANCE,
    },
    {
      slotId: "counter-joker-all",
      source: "counter",
      effect: die("brown"),
      meta: {},
      predicate: (b) => b.bonuses.joker.unlocked >= TOTAL_JOKERS,
    },
    {
      slotId: "counter-plus1-all",
      source: "counter",
      effect: die("pink"),
      meta: {},
      predicate: (b) => b.bonuses.plus1.unlocked >= TOTAL_PLUS1,
    },
  ];
}

function pinkSlots(): SlotDef[] {
  // Displayed only in Phase 1: predicate never fires (unlock mechanic deferred).
  return PINK_BONUSES.map((effect, i) => ({
    slotId: `pink-${i + 1}`,
    source: "pink" as const,
    effect,
    meta: { n: i + 1, multiplier: PINK_MULTIPLIERS[i] },
    predicate: () => false,
  }));
}

export const ALL_SLOTS: SlotDef[] = [
  ...turnSlots(),
  ...goldSlots(),
  ...turquoiseRowSlots(),
  ...turquoiseColSlots(),
  ...blueSlots(),
  ...brownGapSlots(),
  ...counterSlots(),
  ...pinkSlots(),
];

export function slotsBySource(source: BonusSource): SlotDef[] {
  return ALL_SLOTS.filter((s) => s.source === source);
}

// ---- Empty state ----

export function emptyBonusState(): BonusState {
  return {
    relance: { unlocked: 0, used: 0 },
    plus1: { unlocked: 0, used: 0 },
    joker: { unlocked: 0, used: 0 },
    slotsUnlocked: {},
  };
}

/**
 * Apply a cumulative effect (relance / joker / +1) to the counters. Die effects
 * are NOT stored here: they are collected by applyUnlocks for immediate
 * resolution. "none" is a no-op.
 */
function applyEffect(bonuses: BonusState, effect: BonusEffect): BonusState {
  if (effect.kind === "cumulative") {
    return {
      ...bonuses,
      [effect.bonus]: {
        ...bonuses[effect.bonus],
        unlocked: bonuses[effect.bonus].unlocked + 1,
      },
    };
  }
  return bonuses;
}

/** Newly-unlocked slot ids on the last applyUnlocks call (for debug logging). */
export let lastUnlockedSlotIds: string[] = [];

/** Result of applyUnlocks: the updated board and any colored dice to resolve. */
export interface UnlockResult {
  board: PlayerBoard;
  /** Colored bonus dice newly unlocked, in deterministic slot order. */
  dieBonuses: BonusDieColor[];
}

/**
 * Detect and apply all newly-satisfied bonus unlocks for a board. Idempotent and
 * run to a fixpoint so counter-completion bonuses (which depend on other unlocks)
 * are picked up in the same pass. Never re-applies an already-unlocked slot.
 *
 * Cumulative effects update the counters. Colored die effects are collected and
 * returned (not stored) so the caller can resolve them immediately.
 */
export function applyUnlocks(board: PlayerBoard): UnlockResult {
  let bonuses = board.bonuses;
  let working: PlayerBoard = board;
  const newlyUnlocked: string[] = [];
  const dieBonuses: BonusDieColor[] = [];
  let changed = true;
  while (changed) {
    changed = false;
    for (const slot of ALL_SLOTS) {
      if (bonuses.slotsUnlocked[slot.slotId]) continue;
      if (!slot.predicate(working)) continue;
      bonuses = {
        ...applyEffect(bonuses, slot.effect),
        slotsUnlocked: { ...bonuses.slotsUnlocked, [slot.slotId]: true },
      };
      working = { ...working, bonuses };
      newlyUnlocked.push(slot.slotId);
      if (slot.effect.kind === "die") dieBonuses.push(slot.effect.color);
      changed = true;
    }
  }
  lastUnlockedSlotIds = newlyUnlocked;
  return { board: working, dieBonuses };
}
