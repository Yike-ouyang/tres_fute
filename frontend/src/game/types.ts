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
}

/** The current phase of the global turn. */
export type Phase =
  | { kind: "active"; player: PlayerId; round: number }
  | { kind: "passive"; player: PlayerId; done: boolean }
  | { kind: "game-over" };

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
}

export interface GameState {
  globalTurn: number; // 1..6
  phase: Phase;
  boards: Record<PlayerId, PlayerBoard>;
  /** The six shared dice. */
  dice: Record<DieColor, DieRuntime>;
  selection: Selection | null;
  message: string | null;
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
  | { type: "RESET" };
