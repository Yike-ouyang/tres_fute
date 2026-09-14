import { gameReducer } from "./reducer";
import { FOX_SLOT_IDS } from "./bonuses";
import { computeScore } from "./score";
import type { AutoplayDecisionMeta } from "./autoplay";
import {
  ALL_DIE_COLORS,
  PLAYER_IDS,
  type DieColor,
  type GameAction,
  type GameState,
  type Phase,
} from "./types";

const PREFIX = "[GameDebug]";
const STORAGE_KEY = "gameDebug";

/**
 * Debug mode is easy to toggle:
 *   - default: enabled
 *   - disable at runtime: window.GameDebug.disable()  (persisted in localStorage)
 *   - enable at runtime:  window.GameDebug.enable()
 * It can also be turned off before load with localStorage.setItem("gameDebug","0").
 */
function readInitialEnabled(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) !== "0";
  } catch {
    return true;
  }
}

let enabled = readInitialEnabled();

export function isDebugEnabled(): boolean {
  return enabled;
}

function setEnabled(on: boolean): void {
  enabled = on;
  try {
    localStorage.setItem(STORAGE_KEY, on ? "1" : "0");
  } catch {
    /* ignore storage errors */
  }
  console.log(`${PREFIX} debug ${on ? "activé" : "désactivé"}`);
}

/** Expose a small toggle API on window for convenience in the browser console. */
export function installDebugGlobals(): void {
  if (typeof window === "undefined") return;
  (window as unknown as { GameDebug: unknown }).GameDebug = {
    enable: () => setEnabled(true),
    disable: () => setEnabled(false),
    isEnabled: () => enabled,
  };
}

/** Deep, detached snapshot so the console never shows a later-mutated object. */
function snapshot<T>(value: T): T {
  try {
    return structuredClone(value);
  } catch {
    return JSON.parse(JSON.stringify(value)) as T;
  }
}

function phaseText(phase: Phase): string {
  switch (phase.kind) {
    case "active":
      return `active(J${phase.player}, manche ${phase.round})`;
    case "passive":
      return `passive(J${phase.player}, ${phase.done ? "terminé" : "en cours"})`;
    case "plus1":
      return `+1(J${phase.order[phase.current]}, ${phase.current + 1}/${phase.order.length})`;
    case "fill-slots":
      return `compléter-dés(J${phase.player})`;
    case "game-over":
      return "game-over";
  }
}

function actingPlayerOf(phase: Phase): number | null {
  if (phase.kind === "active") return phase.player;
  if (phase.kind === "fill-slots") return phase.player;
  if (phase.kind === "passive" && !phase.done) return phase.player;
  if (phase.kind === "plus1") return phase.order[phase.current];
  return null;
}

/** Newly-unlocked bonus slot ids per player between two states. */
function unlockDiff(before: GameState, after: GameState) {
  const out: { player: number; slots: string[] }[] = [];
  for (const p of PLAYER_IDS) {
    const b = before.boards[p].bonuses.slotsUnlocked;
    const a = after.boards[p].bonuses.slotsUnlocked;
    const slots = Object.keys(a).filter((id) => a[id] && !b[id]);
    if (slots.length > 0) out.push({ player: p, slots });
  }
  return out;
}

/** Compact, readable summary of the game state for logging. */
function summarize(state: GameState) {
  return snapshot({
    globalTurn: state.globalTurn,
    phase: phaseText(state.phase),
    actingPlayer: actingPlayerOf(state.phase),
    message: state.message,
    selection: state.selection
      ? {
          color: state.selection.color,
          value: state.selection.value,
          actingColor: state.selection.actingColor,
          legal: state.selection.legal,
          picked: state.selection.picked,
          maxPick: state.selection.maxPick,
        }
      : null,
    plus1Active: state.plus1Active,
    jokerPending: state.jokerPending,
    dice: ALL_DIE_COLORS.map((c) => ({
      color: c,
      value: state.dice[c].value,
      jokerValue: state.dice[c].jokerValue ?? null,
      location: state.dice[c].location,
    })),
    pendingBonuses: state.pendingBonuses,
    bonusResolution: state.bonusResolution,
    pinkChoice: state.pinkChoice
      ? {
          owner: state.pinkChoice.owner,
          cellId: state.pinkChoice.cellId,
          position: state.pinkChoice.position,
          effectiveValue: state.pinkChoice.effectiveValue,
          multiplier: state.pinkChoice.multiplier,
          bonusEffect: state.pinkChoice.bonusEffect,
        }
      : null,
    pendingAdvance: state.pendingAdvance,
    bonuses: PLAYER_IDS.map((p) => {
      const bs = state.boards[p].bonuses;
      return {
        player: p,
        relance: bs.relance,
        joker: bs.joker,
        plus1: bs.plus1,
      };
    }),
  });
}

/** Context info requested in the spec, logged once per interaction. */
function logContext(state: GameState) {
  const s = state.selection;
  console.log(`${PREFIX} contexte`, {
    tour: state.globalTurn,
    phase: phaseText(state.phase),
    joueurActif: state.phase.kind === "active" ? state.phase.player : null,
    doitAgir: actingPlayerOf(state.phase),
    manche: state.phase.kind === "active" ? state.phase.round : null,
    de: s ? { couleur: s.color, valeur: s.value, couleurEffective: s.actingColor } : null,
    destinationsLegales: s?.legal ?? null,
    selectionProvisoire: s?.picked ?? null,
  });
}

function diceMovements(before: GameState, after: GameState) {
  const moves: { color: DieColor; from: string; to: string }[] = [];
  for (const c of ALL_DIE_COLORS) {
    if (before.dice[c].location !== after.dice[c].location) {
      moves.push({
        color: c,
        from: before.dice[c].location,
        to: after.dice[c].location,
      });
    }
  }
  return moves;
}

function sameArray(a: string[] | undefined, b: string[] | undefined): boolean {
  if (!a || !b) return a === b;
  return a.length === b.length && a.every((v, i) => v === b[i]);
}

/** Action-specific commentary, using the freshly computed `after` state. */
function logDetails(action: GameAction, before: GameState, after: GameState) {
  switch (action.type) {
    case "SELECT_DIE": {
      const d = before.dice[action.color];
      console.log(`${PREFIX} clic sur dé`, {
        couleur: action.color,
        valeur: d?.value,
        emplacement: d?.location,
      });
      if (!after.selection) {
        console.log(`${PREFIX} dé refusé`, { raison: after.message });
      } else if (after.selection.actingColor === null) {
        console.log(`${PREFIX} dé blanc sélectionné`, {
          info: "en attente du choix de couleur",
        });
      } else {
        console.log(`${PREFIX} dé sélectionné`, {
          couleurEffective: after.selection.actingColor,
          destinationsLegales: after.selection.legal,
          nbCasesSelectionnables: after.selection.maxPick,
        });
      }
      break;
    }

    case "CHOOSE_WHITE_COLOR": {
      console.log(`${PREFIX} choix de couleur (blanc)`, {
        couleur: action.actingColor,
      });
      if (after.selection?.actingColor === action.actingColor) {
        console.log(`${PREFIX} destinations légales`, {
          destinationsLegales: after.selection.legal,
          nbCasesSelectionnables: after.selection.maxPick,
        });
      } else {
        console.log(`${PREFIX} couleur refusée`, { raison: after.message });
      }
      break;
    }

    case "PICK_CELL": {
      console.log(`${PREFIX} clic sur case`, { caseId: action.cellId });
      const beforePicked = before.selection?.picked;
      const afterPicked = after.selection?.picked;
      if (!before.selection || before.selection.actingColor === null) {
        console.log(`${PREFIX} sélection refusée`, {
          raison: "aucun dé sélectionné ou couleur non choisie",
        });
      } else if (!before.selection.legal.includes(action.cellId)) {
        console.log(`${PREFIX} sélection refusée`, {
          raison: "case non autorisée (absente des destinations légales)",
          destinationsLegales: before.selection.legal,
        });
      } else if (sameArray(beforePicked, afterPicked)) {
        console.log(`${PREFIX} sélection refusée`, {
          raison: "nombre maximal de cases déjà atteint",
          maxPick: before.selection.maxPick,
        });
      } else {
        const added =
          (afterPicked?.length ?? 0) > (beforePicked?.length ?? 0);
        console.log(`${PREFIX} sélection acceptée`, {
          action: added ? "ajout" : "retrait",
          selectionProvisoire: afterPicked,
        });
      }
      break;
    }

    case "CANCEL_SELECTION":
      console.log(`${PREFIX} sélection annulée`);
      break;

    case "VALIDATE_MOVE": {
      const wasComplete =
        before.selection &&
        before.selection.actingColor !== null &&
        before.selection.picked.length >= 1;
      if (!wasComplete) {
        console.log(`${PREFIX} validation refusée`, {
          raison: "sélection incomplète",
          selection: before.selection,
        });
        break;
      }
      const sameState = before === after;
      if (sameState) {
        console.log(`${PREFIX} validation refusée`, {
          raison: "état inchangé (déjà appliqué ou invalide)",
        });
        break;
      }
      console.log(`${PREFIX} coup appliqué`, {
        couleurEffective: before.selection?.actingColor,
        cases: before.selection?.picked,
      });
      console.log(`${PREFIX} déplacement des dés`, diceMovements(before, after));
      console.log(`${PREFIX} transition`, {
        avant: phaseText(before.phase),
        apres: phaseText(after.phase),
      });
      break;
    }

    case "END_TURN":
    case "PASS_PASSIVE":
    case "CONTINUE":
    case "PLUS1_SKIP": {
      console.log(`${PREFIX} déplacement des dés`, diceMovements(before, after));
      console.log(`${PREFIX} transition`, {
        avant: phaseText(before.phase),
        apres: phaseText(after.phase),
        tourAvant: before.globalTurn,
        tourApres: after.globalTurn,
      });
      break;
    }

    case "USE_RELANCE": {
      const applied = before !== after;
      console.log(`${PREFIX} relance`, {
        appliquee: applied,
        raison: applied ? undefined : "aucune relance disponible ou hors phase active",
      });
      if (applied) {
        console.log(`${PREFIX} nouveaux dés`, diceMovements(before, after));
      }
      break;
    }

    case "START_JOKER": {
      console.log(`${PREFIX} joker démarré`, {
        accepte: before !== after,
        pending: after.jokerPending,
        message: after.message,
      });
      break;
    }

    case "SET_JOKER_VALUE": {
      console.log(`${PREFIX} valeur du joker`, {
        valeur: action.value,
        pending: after.jokerPending,
      });
      break;
    }

    case "CANCEL_JOKER":
      console.log(`${PREFIX} joker annulé`);
      break;

    case "PLUS1_USE": {
      console.log(`${PREFIX} +1 : début de replay`, {
        accepte: before !== after,
        joueur: after.plus1Active,
      });
      break;
    }

    case "BONUS_CHOOSE_COLOR":
      console.log(`${PREFIX} bonus noir : couleur choisie`, {
        couleur: action.color,
        resolution: after.bonusResolution,
      });
      break;

    case "BONUS_CHOOSE_VALUE":
      console.log(`${PREFIX} bonus : valeur choisie`, {
        valeur: action.value,
        resolution: after.bonusResolution,
        dialogueRose: after.pinkChoice ? "ouvert" : null,
      });
      break;

    case "BONUS_PLACE_BLUE":
      console.log(`${PREFIX} bonus bleu foncé : case remplie`, {
        caseId: action.cellId,
        valeur: action.value,
      });
      break;

    case "BONUS_NOMOVE_DONE":
      console.log(`${PREFIX} bonus sans coup possible : résolution terminée`, {
        avant: before.bonusResolution,
      });
      break;

    case "PINK_CHOOSE": {
      const c = before.pinkChoice;
      const applied = before !== after;
      console.log(`${PREFIX} case rose : option choisie`, {
        option: action.option,
        position: c?.position,
        valeurEffective: c?.effectiveValue,
        multiplicateur: c?.multiplier,
        valeurInscrite:
          c == null
            ? null
            : action.option === "points"
            ? c.effectiveValue * c.multiplier
            : Math.ceil(c.effectiveValue / 2),
        bonusAccorde: action.option === "bonus" ? c?.bonusEffect : null,
        applique: applied,
      });
      break;
    }

    case "PINK_CANCEL":
      console.log(`${PREFIX} case rose : choix annulé (rien consommé)`);
      break;

    case "FILL_SLOT":
      console.log(`${PREFIX} complément d’emplacement (sans effet)`, {
        couleur: action.color,
        phase: phaseText(after.phase),
      });
      break;

    case "RESET":
      console.log(`${PREFIX} partie réinitialisée`);
      break;
  }

  const unlocks = unlockDiff(before, after);
  if (unlocks.length > 0) {
    console.log(`${PREFIX} bonus débloqués`, unlocks);
    const foxes = unlocks
      .map((u) => ({
        player: u.player,
        slots: u.slots.filter((id) => (FOX_SLOT_IDS as readonly string[]).includes(id)),
      }))
      .filter((u) => u.slots.length > 0);
    if (foxes.length > 0) {
      console.log(`${PREFIX} renard débloqué`, foxes);
    }
  }

  if (before.phase.kind !== "game-over" && after.phase.kind === "game-over") {
    console.log(`${PREFIX} scores finaux`, {
      joueur1: computeScore(after.boards[1]),
      joueur2: computeScore(after.boards[2]),
    });
  }

  // Immediate colored-bonus queue and resolution flow.
  if (after.pendingBonuses.length > before.pendingBonuses.length) {
    console.log(`${PREFIX} bonus immédiats en file`, {
      file: after.pendingBonuses,
    });
  }
  if (before.bonusResolution?.owner !== after.bonusResolution?.owner ||
      before.bonusResolution?.color !== after.bonusResolution?.color ||
      before.bonusResolution?.stage !== after.bonusResolution?.stage) {
    if (after.bonusResolution) {
      console.log(`${PREFIX} résolution de bonus`, after.bonusResolution);
    } else if (before.bonusResolution) {
      console.log(`${PREFIX} bonus résolu`, { avant: before.bonusResolution });
    }
  }
  if (!before.pinkChoice && after.pinkChoice) {
    console.log(`${PREFIX} choix rose ouvert`, {
      position: after.pinkChoice.position,
      valeurEffective: after.pinkChoice.effectiveValue,
      multiplicateur: after.pinkChoice.multiplier,
      bonus: after.pinkChoice.bonusEffect,
    });
  }
}

// React StrictMode double-invokes reducers in development with the SAME
// prev-state and action references. Dedupe those to avoid duplicate logs.
let lastPrev: GameState | null = null;
let lastAction: GameAction | null = null;

function shouldLog(prev: GameState, action: GameAction): boolean {
  if (prev === lastPrev && action === lastAction) return false;
  lastPrev = prev;
  lastAction = action;
  return true;
}

/**
 * Extra autoplay-step log: phase, physical dice, max-die filter, chosen action.
 * Gated on debug mode. Does not replace the per-action loggingReducer groups.
 */
export function logAutoplayDecision(
  state: GameState,
  action: GameAction,
  meta: AutoplayDecisionMeta | null
): void {
  if (!enabled) return;
  const available = ALL_DIE_COLORS.filter((c) => state.dice[c].location === "available").map(
    (c) => ({ couleur: c, valeur: state.dice[c].value })
  );
  const autoTypes = new Set([
    "VALIDATE_MOVE",
    "CONTINUE",
    "END_TURN",
    "PASS_PASSIVE",
    "FILL_SLOT",
    "PINK_CHOOSE",
    "BONUS_CHOOSE_COLOR",
    "BONUS_CHOOSE_VALUE",
    "BONUS_PLACE_BLUE",
    "BONUS_NOMOVE_DONE",
  ]);
  console.log(`${PREFIX} avance`, {
    tour: state.globalTurn,
    phase: phaseText(state.phase),
    manche: state.phase.kind === "active" ? state.phase.round : null,
    joueur: actingPlayerOf(state.phase),
    desDisponibles: available,
    jouables: meta?.playable ?? [],
    exclusParMax: meta?.excluded ?? [],
    deChoisi: meta?.chosenDie ?? null,
    maxAutorise: meta?.maxAllowedReason ?? null,
    action: action.type,
    validationAuto: autoTypes.has(action.type),
  });
}

/**
 * Reducer wrapper that logs each interaction/transition in a collapsed group.
 * Pure with respect to the returned state: it only adds console side effects.
 */
export function loggingReducer(state: GameState, action: GameAction): GameState {
  if (!enabled) return gameReducer(state, action);
  if (!shouldLog(state, action)) return gameReducer(state, action);

  const before = summarize(state);
  const next = gameReducer(state, action);
  const after = summarize(next);

  console.groupCollapsed(`${PREFIX} ${action.type}`);
  logContext(state);
  logDetails(action, state, next);
  console.log(`${PREFIX} état avant`, before);
  console.log(`${PREFIX} état après`, after);
  console.groupEnd();

  return next;
}
