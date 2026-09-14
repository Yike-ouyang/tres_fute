import type { DieColor } from "../boardData";

export type { DieColor };

/** Colors a die can act as (white excluded, since white borrows another color). */
export type ActingColor = Exclude<DieColor, "white">;

export const ACTING_COLORS: ActingColor[] = [
  "yellow",
  "turquoise",
  "darkblue",
  "brown",
  "pink",
];

/** All six permanent dice, keyed by their permanent color identity. */
export const ALL_DIE_COLORS: DieColor[] = [
  "yellow",
  "turquoise",
  "darkblue",
  "brown",
  "pink",
  "white",
];

export type DiceLocation = "available" | "chosen" | "discarded";

export interface DieRuntime {
  value: number;
  location: DiceLocation;
  /** Temporary value forced by a joker for this active sequence (elimination still uses `value`). */
  jokerValue?: number;
}

/** Effective value of a die: the joker value if one was applied, else the rolled value. */
export function effectiveValue(die: DieRuntime): number {
  return die.jokerValue ?? die.value;
}

// ---- Bonuses ----

export type CumulativeBonus = "relance" | "joker" | "plus1";

export type BonusDieColor =
  | "yellow"
  | "turquoise"
  | "darkblue"
  | "brown"
  | "pink"
  | "black";

export const BONUS_DIE_COLORS: BonusDieColor[] = [
  "yellow",
  "turquoise",
  "darkblue",
  "brown",
  "pink",
  "black",
];

export type BonusEffect =
  | { kind: "cumulative"; bonus: CumulativeBonus }
  | { kind: "die"; color: BonusDieColor }
  | { kind: "fox" }
  | { kind: "none" };

export interface BonusTally {
  unlocked: number;
  used: number;
}

/**
 * Per-board bonus state. Only relance / joker / +1 are storable (cumulative
 * counters). Colored bonus dice are NOT stored: they are resolved immediately.
 */
export interface BonusState {
  relance: BonusTally;
  plus1: BonusTally;
  joker: BonusTally;
  /** slotId -> true once that board slot has been unlocked (so it counts once). */
  slotsUnlocked: Record<string, boolean>;
}

/** A die that has been chosen (placed in a slot or otherwise recorded). */
export interface ChosenDie {
  color: DieColor;
  value: number;
}

export type PlayerId = 1 | 2;

export const PLAYER_IDS: PlayerId[] = [1, 2];

export function otherPlayer(player: PlayerId): PlayerId {
  return player === 1 ? 2 : 1;
}

/** Independent state for a single player's board. Keys are unprefixed cell ids. */
export interface PlayerBoard {
  checks: Record<string, boolean>;
  values: Record<string, number>;
  brownLastChecked: number | null;
  brownDisabled: Record<string, boolean>;
  /** Dice placed in this player's slots during the current active sequence. */
  chosenThisTurn: ChosenDie[];
  /** die-1, die-2, die-3 -> the die placed there, or null. */
  slots: (ChosenDie | null)[];
  /** Bonus counters, bonus-die tallies and unlocked-slot guards. */
  bonuses: BonusState;
}

/** The current phase of the global turn. */
export type Phase =
  | { kind: "active"; player: PlayerId; round: number }
  | { kind: "passive"; player: PlayerId; done: boolean }
  /** +1 window after an active sequence: each player in `order` may use a +1. */
  | { kind: "plus1"; order: [PlayerId, PlayerId]; current: number }
  /** Fill remaining active slots from the grey square, without board effect. */
  | { kind: "fill-slots"; player: PlayerId }
  | { kind: "game-over" };

/** A colored bonus die awaiting immediate resolution, tied to its owner. */
export interface PendingBonus {
  owner: PlayerId;
  color: BonusDieColor;
}

/**
 * The bonus currently being resolved (an interactive overlay on the owner's
 * board). Colored bonus dice are resolved one at a time, in a deterministic
 * order, before normal play resumes.
 */
export interface BonusResolution {
  owner: PlayerId;
  /** The color originally unlocked ("black" lets the owner choose a color). */
  originColor: BonusDieColor;
  /** The effective color being resolved (equals originColor unless black). */
  color: BonusDieColor;
  stage: "chooseColor" | "chooseValue" | "placing" | "noMove";
  /** Chosen value for yellow / brown / pink (null until picked). */
  value: number | null;
}

/** How a deferred pink choice should be completed once the option is confirmed. */
export type PinkResume =
  | { kind: "active"; player: PlayerId; round: number; sel: Selection }
  | { kind: "passive"; player: PlayerId; sel: Selection }
  | { kind: "plus1"; actor: PlayerId; sel: Selection }
  | { kind: "bonusDie"; owner: PlayerId };

/** The open pink points-vs-bonus dialog for a single pink inscription. */
export interface PinkChoice {
  owner: PlayerId;
  cellId: string;
  /** 1-based pink cell position. */
  position: number;
  /** Effective die value (joker-adjusted, or the chosen bonus-die value). */
  effectiveValue: number;
  /** Multiplier printed on the cell (0 when none). */
  multiplier: number;
  /** Slot id of the cell's associated bonus, or null when none. */
  bonusSlotId: string | null;
  /** The cell's associated bonus effect. */
  bonusEffect: BonusEffect;
  /** How to finish the move after the choice is confirmed. */
  resume: PinkResume;
}

/** A deferred game transition, run only once all pending bonuses are resolved. */
export type PendingAdvance =
  | { kind: "activeNext"; player: PlayerId; round: number }
  | { kind: "endActive"; player: PlayerId }
  | { kind: "fillSlots"; player: PlayerId }
  | { kind: "passiveDone"; player: PlayerId }
  | { kind: "plus1Next"; order: [PlayerId, PlayerId]; current: number }
  | { kind: "startTurn"; player: PlayerId };

/** Provisional (not yet validated) selection state, on the acting player's board. */
export interface Selection {
  /** The clicked die's permanent color. */
  color: DieColor;
  /** The clicked die's current value. */
  value: number;
  /** Chosen sub-color when the die is white; equals color otherwise. Null while white awaits a color choice. */
  actingColor: ActingColor | null;
  /** Highlighted destination cell ids (unprefixed). */
  legal: string[];
  /** Provisionally picked cells (turquoise allows several; single otherwise). */
  picked: string[];
  /** Maximum number of cells that may be picked (turquoise cap; 1 otherwise). */
  maxPick: number;
  /** Value used to eliminate lower dice (the die's initial value; differs from `value` under a joker). */
  eliminationValue: number;
}

export interface GameState {
  globalTurn: number; // 1..6
  phase: Phase;
  boards: Record<PlayerId, PlayerBoard>;
  /** The six shared dice. */
  dice: Record<DieColor, DieRuntime>;
  selection: Selection | null;
  message: string | null;
  /** During the +1 window, the player currently making a +1 play (null otherwise). */
  plus1Active: PlayerId | null;
  /** Pending joker: chosen token and its value (null value = wild, awaiting a chosen value). */
  jokerPending: { tokenIndex: number; value: number | null } | null;
  /** FIFO queue of colored bonus dice awaiting immediate resolution. */
  pendingBonuses: PendingBonus[];
  /** The colored bonus currently being resolved (overlay), or null. */
  bonusResolution: BonusResolution | null;
  /** The open pink points-vs-bonus dialog, or null. */
  pinkChoice: PinkChoice | null;
  /** A transition deferred until all pending bonuses are resolved, or null. */
  pendingAdvance: PendingAdvance | null;
}

export type GameAction =
  | { type: "SELECT_DIE"; color: DieColor }
  | { type: "CHOOSE_WHITE_COLOR"; actingColor: ActingColor }
  | { type: "PICK_CELL"; cellId: string }
  | { type: "CANCEL_SELECTION" }
  | { type: "VALIDATE_MOVE" }
  | { type: "END_TURN" }
  | { type: "PASS_PASSIVE" }
  | { type: "CONTINUE" }
  | { type: "USE_RELANCE" }
  | { type: "START_JOKER"; tokenIndex: number }
  | { type: "SET_JOKER_VALUE"; value: number }
  | { type: "CANCEL_JOKER" }
  | { type: "PLUS1_USE" }
  | { type: "PLUS1_SKIP" }
  | { type: "BONUS_CHOOSE_COLOR"; color: ActingColor }
  | { type: "BONUS_CHOOSE_VALUE"; value: number }
  | { type: "BONUS_PLACE_BLUE"; cellId: string; value: number }
  | { type: "BONUS_NOMOVE_DONE" }
  | { type: "PINK_CHOOSE"; option: "points" | "bonus" }
  | { type: "PINK_CANCEL" }
  | { type: "FILL_SLOT"; color: DieColor }
  | { type: "RESET" };
