export type DieColor =
  | "yellow"
  | "turquoise"
  | "darkblue"
  | "brown"
  | "pink"
  | "white";

export interface DieColorOption {
  value: DieColor;
  label: string;
  background: string;
  text: string;
}

export const DIE_COLOR_OPTIONS: DieColorOption[] = [
  { value: "yellow", label: "Jaune", background: "#f4c542", text: "#1a1a1a" },
  { value: "turquoise", label: "Turquoise", background: "#2fb3ad", text: "#1a1a1a" },
  { value: "darkblue", label: "Bleu foncé", background: "#1f3b73", text: "#ffffff" },
  { value: "brown", label: "Marron", background: "#7a4b2b", text: "#ffffff" },
  { value: "pink", label: "Rose", background: "#e28bb4", text: "#1a1a1a" },
  { value: "white", label: "Blanc", background: "#ffffff", text: "#1a1a1a" },
];

export const DIE_VALUES = [1, 2, 3, 4, 5, 6] as const;

/** Fixed numbers printed on every yellow / turquoise row, left to right. */
export const ROW_NUMBERS = [1, 2, 3, 4, 5, 6] as const;

/** Number of rows in the yellow zone. */
export const YELLOW_ROWS = 3;
/** Number of rows in the turquoise zone (corrected to 5). */
export const TURQUOISE_ROWS = 5;

/** Fixed numbers printed on the brown track, left to right. */
export const BROWN_NUMBERS = [1, 5, 3, 4, 2, 6, 4, 5, 2, 1, 6, 3] as const;

/** Number of pink cells. */
export const PINK_CELLS = 12;

/** Blue track: 6 cells + central 7 + 6 cells = 13 cells, center at position 7. */
export const BLUE_CELL_COUNT = 13;
export const BLUE_CENTER_INDEX = 7;
export const BLUE_CENTER_VALUE = 7;

export interface DieState {
  value: number | "";
  color: DieColor | "";
}

export const DIE_IDS = ["die-1", "die-2", "die-3"] as const;
export const DIE_LABELS = ["I", "II", "III"] as const;
