import type { HumanLegalAction } from "../api/humanPlay";
import type { DiceLocation } from "../game/types";

/** Utilitaires purs de mapping clic → action v2 (testables sans DOM). */

export interface ParsedDetail {
  kind: string;
  value: string;
}

export function parseDetail(detail: string): ParsedDetail {
  const idx = detail.indexOf(":");
  if (idx < 0) return { kind: detail, value: detail };
  return { kind: detail.slice(0, idx), value: detail.slice(idx + 1) };
}

export interface TurquoiseAction {
  action: HumanLegalAction;
  rows: number[];
  col: number;
}

/** Actions de destination (normales + bonus jaune/marron). */
export function destinationActions(legal: HumanLegalAction[]): HumanLegalAction[] {
  return legal.filter((a) => a.category.startsWith("dest_"));
}

export function findDieAction(legal: HumanLegalAction[], color: string): HumanLegalAction | undefined {
  return legal.find((a) => a.category === "select_die" && a.detail === `die:${color}`);
}

export function findFillAction(legal: HumanLegalAction[], color: string): HumanLegalAction | undefined {
  return legal.find((a) => a.category === "fill_slot" && a.detail === `fill:${color}`);
}

export type SelectTarget = "available" | "discarded" | "chosen";

/**
 * Répartit les dés sélectionnables (actions `select_die`) selon leur
 * localisation : `available` → DicePool, `discarded` → carré gris (phase
 * passive), `chosen` → emplacements du joueur (fallback).
 */
export function classifySelectDice(
  legal: HumanLegalAction[],
  locations: Record<string, DiceLocation>
): Record<SelectTarget, string[]> {
  const out: Record<SelectTarget, string[]> = { available: [], discarded: [], chosen: [] };
  for (const action of legal) {
    if (action.category !== "select_die") continue;
    const color = parseDetail(action.detail).value;
    const location = locations[color];
    if (location === "available" || location === "discarded" || location === "chosen") {
      out[location].push(color);
    }
  }
  return out;
}

export function findWhiteColorAction(legal: HumanLegalAction[], color: string): HumanLegalAction | undefined {
  return legal.find((a) => a.category === "white_color" && a.detail === `white:${color}`);
}

/** Case → action de destination non-turquoise (le suffixe après ":" est le cell_id). */
export function findCellAction(legal: HumanLegalAction[], cellId: string): HumanLegalAction | undefined {
  return destinationActions(legal).find(
    (a) => a.category !== "dest_turquoise" && parseDetail(a.detail).value === cellId
  );
}

export function isUniqueDestination(legal: HumanLegalAction[]): boolean {
  return destinationActions(legal).length === 1;
}

export function parseTurquoise(legal: HumanLegalAction[]): TurquoiseAction[] {
  const out: TurquoiseAction[] = [];
  for (const action of legal) {
    if (action.category !== "dest_turquoise") continue;
    const match = /^turquoise:rows([1-5]+)@c(\d+)$/.exec(action.detail);
    if (!match) continue;
    out.push({ action, rows: match[1].split("").map(Number), col: Number(match[2]) });
  }
  return out;
}

export function turquoiseColumn(legal: HumanLegalAction[]): number | null {
  const parsed = parseTurquoise(legal);
  return parsed.length ? parsed[0].col : null;
}

/** Cellules turquoise cliquables (union des lignes atteignables, colonne fixe). */
export function turquoiseLegalCells(legal: HumanLegalAction[]): Set<string> {
  const cells = new Set<string>();
  for (const { rows, col } of parseTurquoise(legal)) {
    for (const row of rows) cells.add(`turquoise-r${row}-c${col}`);
  }
  return cells;
}

function sameRows(a: number[], b: number[]): boolean {
  if (a.length !== b.length) return false;
  const sa = [...a].sort();
  const sb = [...b].sort();
  return sa.every((v, i) => v === sb[i]);
}

function isStrictSuperset(candidate: number[], rows: number[]): boolean {
  return candidate.length > rows.length && rows.every((r) => candidate.includes(r));
}

export function findTurquoiseAction(legal: HumanLegalAction[], rows: number[]): HumanLegalAction | undefined {
  return parseTurquoise(legal).find((t) => sameRows(t.rows, rows))?.action;
}

/**
 * T1 : joue dès que l'ensemble courant est un sous-ensemble légal de taille
 * `maxPick`, ou qu'aucun sur-ensemble strict n'est encore légal (maximal).
 */
export function turquoiseShouldPlay(legal: HumanLegalAction[], rows: number[], maxPick: number): boolean {
  if (rows.length === 0) return false;
  const action = findTurquoiseAction(legal, rows);
  if (!action) return false;
  if (rows.length >= maxPick) return true;
  return !parseTurquoise(legal).some((t) => isStrictSuperset(t.rows, rows));
}

/** Trouve une action par catégorie + détail exact (utilitaires, bonus, option rose…). */
export function findByDetail(
  legal: HumanLegalAction[],
  detail: string,
  category?: string
): HumanLegalAction | undefined {
  return legal.find((a) => a.detail === detail && (!category || a.category === category));
}

export function utilityActions(legal: HumanLegalAction[]): HumanLegalAction[] {
  return legal.filter((a) => a.category === "utility");
}

/** `Relances` : available/total-unlocked, ex. « 2/3 ». */
export function formatBonusTally(unlocked: number, used: number): string {
  const available = Math.max(0, unlocked - used);
  return `${available}/${unlocked}`;
}

/**
 * Nom lisible d'un checkpoint : `run / sous-dossier (fichier)`.
 * Ex. `…/agent/runs/shaped_20260917_203604/run_min_zone/best_model.zip`
 *  -> `shaped_20260917_203604 / run_min_zone (best_model.zip)`.
 */
export function formatOpponent(checkpoint: string | null | undefined): string {
  if (!checkpoint) return "IA";
  const parts = checkpoint.split("/").filter(Boolean);
  if (parts.length === 0) return "IA";
  const runsIndex = parts.lastIndexOf("runs");
  const relevant = runsIndex >= 0 ? parts.slice(runsIndex + 1) : parts;
  const file = relevant[relevant.length - 1];
  const dirs = relevant.slice(0, -1);
  const tail = dirs.slice(-2).join(" / ");
  return tail ? `${tail} (${file})` : file;
}
