import {
  ALL_DIE_COLORS,
  otherPlayer,
  PLAYER_IDS,
  type ChosenDie,
  type DieColor,
  type DieRuntime,
  type GameAction,
  type GameState,
  type PlayerBoard,
  type PlayerId,
  type Selection,
} from "./types";
import {
  activeContext,
  anyAvailableDieHasMove,
  anyDiscardedDieHasMove,
  blueSum,
  legalDestinations,
  passiveContext,
  pinkValue,
  rollValue,
  type MoveContext,
} from "./rules";

const STUCK_ACTIVE = "Aucun coup possible. Terminez le tour.";
const STUCK_PASSIVE = "Aucun coup possible. Vous pouvez passer.";
const NO_DIE_MOVE = "Aucun coup possible avec ce dé.";
const NO_COLOR_MOVE = "Cette couleur ne permet aucun coup.";

function rollAllDice(): Record<DieColor, DieRuntime> {
  const dice = {} as Record<DieColor, DieRuntime>;
  for (const color of ALL_DIE_COLORS) {
    dice[color] = { value: rollValue(), location: "available" };
  }
  return dice;
}

function rerollAvailable(
  dice: Record<DieColor, DieRuntime>
): Record<DieColor, DieRuntime> {
  const next = {} as Record<DieColor, DieRuntime>;
  for (const color of ALL_DIE_COLORS) {
    const d = dice[color];
    next[color] =
      d.location === "available" ? { ...d, value: rollValue() } : { ...d };
  }
  return next;
}

function emptyBoard(): PlayerBoard {
  return {
    checks: {},
    values: {},
    brownLastChecked: null,
    brownDisabled: {},
    chosenThisTurn: [],
    slots: [null, null, null],
  };
}

function countAvailable(dice: Record<DieColor, DieRuntime>): number {
  return ALL_DIE_COLORS.filter((c) => dice[c].location === "available").length;
}

/** Set a non-blocking stuck message appropriate to the current phase. */
function withStuckMessage(state: GameState): GameState {
  const { phase } = state;
  if (phase.kind === "active") {
    if (
      countAvailable(state.dice) > 0 &&
      !anyAvailableDieHasMove(state, phase.player, phase.round)
    ) {
      return { ...state, message: STUCK_ACTIVE };
    }
  } else if (phase.kind === "passive" && !phase.done) {
    if (!anyDiscardedDieHasMove(state, phase.player)) {
      return { ...state, message: STUCK_PASSIVE };
    }
  }
  return state;
}

/** Begin an active sequence: reset & reroll six dice, free the player's slots. */
function startActiveSequence(state: GameState, player: PlayerId): GameState {
  const board = state.boards[player];
  const base: GameState = {
    ...state,
    phase: { kind: "active", player, round: 1 },
    dice: rollAllDice(),
    boards: {
      ...state.boards,
      [player]: { ...board, slots: [null, null, null], chosenThisTurn: [] },
    },
    selection: null,
    message: null,
  };
  return withStuckMessage(base);
}

/** End an active sequence: discard remaining dice, hand over to the passive player. */
function endActiveSequence(state: GameState, activePlayerId: PlayerId): GameState {
  const dice = {} as Record<DieColor, DieRuntime>;
  for (const color of ALL_DIE_COLORS) {
    const d = state.dice[color];
    dice[color] =
      d.location === "available" ? { ...d, location: "discarded" } : { ...d };
  }
  const passivePlayer = otherPlayer(activePlayerId);
  const base: GameState = {
    ...state,
    dice,
    phase: { kind: "passive", player: passivePlayer, done: false },
    selection: null,
    message: null,
  };
  return withStuckMessage(base);
}

export function createInitialState(): GameState {
  const base: GameState = {
    globalTurn: 1,
    phase: { kind: "active", player: 1, round: 1 },
    boards: { 1: emptyBoard(), 2: emptyBoard() },
    dice: rollAllDice(),
    selection: null,
    message: null,
  };
  return withStuckMessage(base);
}

function cellNumber(id: string): number {
  return Number(id.split("-").pop());
}

/** Apply a validated selection's effect to a board (checks / values only). */
function applyMoveToBoard(
  board: PlayerBoard,
  sel: Selection,
  dice: Record<DieColor, DieRuntime>
): PlayerBoard {
  let checks = board.checks;
  let values = board.values;
  let brownLastChecked = board.brownLastChecked;
  let brownDisabled = board.brownDisabled;

  switch (sel.actingColor) {
    case "yellow":
      checks = { ...checks, [sel.picked[0]]: true };
      break;
    case "turquoise": {
      checks = { ...checks };
      for (const id of sel.picked) checks[id] = true;
      break;
    }
    case "pink":
      values = { ...values, [sel.picked[0]]: pinkValue(sel.value) };
      break;
    case "darkblue":
      values = { ...values, [sel.picked[0]]: blueSum(dice) };
      break;
    case "brown": {
      const cell = sel.picked[0];
      const idx = cellNumber(cell);
      checks = { ...checks, [cell]: true };
      brownDisabled = { ...brownDisabled };
      for (let n = 1; n < idx; n++) {
        const id = `brown-cell-${n}`;
        if (!checks[id]) brownDisabled[id] = true;
      }
      brownLastChecked = idx;
      break;
    }
  }

  return { ...board, checks, values, brownLastChecked, brownDisabled };
}

function ctxForPhase(state: GameState, selectedColor: DieColor): MoveContext | null {
  const { phase } = state;
  if (phase.kind === "active") {
    return activeContext(state, phase.player, phase.round, selectedColor);
  }
  if (phase.kind === "passive" && !phase.done) {
    return passiveContext(state, phase.player, selectedColor);
  }
  return null;
}

function validateActive(state: GameState, sel: Selection, player: PlayerId, round: number): GameState {
  const board = applyMoveToBoard(state.boards[player], sel, state.dice);
  const slots = [...board.slots];
  slots[round - 1] = { color: sel.color, value: sel.value };
  const chosenThisTurn: ChosenDie[] = [
    ...board.chosenThisTurn,
    { color: sel.color, value: sel.value },
  ];

  const dice = {} as Record<DieColor, DieRuntime>;
  for (const color of ALL_DIE_COLORS) {
    const d = state.dice[color];
    if (color === sel.color) {
      dice[color] = { ...d, location: "chosen" };
    } else if (d.location === "available" && d.value < sel.value) {
      dice[color] = { ...d, location: "discarded" };
    } else {
      dice[color] = { ...d };
    }
  }

  let next: GameState = {
    ...state,
    boards: { ...state.boards, [player]: { ...board, slots, chosenThisTurn } },
    dice,
    selection: null,
    message: null,
  };

  if (round < 3 && countAvailable(next.dice) > 0) {
    next = withStuckMessage({
      ...next,
      phase: { kind: "active", player, round: round + 1 },
      dice: rerollAvailable(next.dice),
    });
  } else {
    next = endActiveSequence(next, player);
  }
  return next;
}

function validatePassive(state: GameState, sel: Selection, player: PlayerId): GameState {
  const board = applyMoveToBoard(state.boards[player], sel, state.dice);
  return {
    ...state,
    boards: { ...state.boards, [player]: board },
    phase: { kind: "passive", player, done: true },
    selection: null,
    message: null,
  };
}

function continueAfterPassive(state: GameState, player: PlayerId): GameState {
  if (player === 2) {
    // Player 2 becomes active in the same global turn.
    return startActiveSequence(state, 2);
  }
  // Player 1 was passive: the global turn ends. Check the turn box on both boards.
  const turnId = `turn-${state.globalTurn}`;
  const boards = { ...state.boards };
  for (const p of PLAYER_IDS) {
    boards[p] = { ...boards[p], checks: { ...boards[p].checks, [turnId]: true } };
  }
  if (state.globalTurn >= 6) {
    return {
      ...state,
      boards,
      phase: { kind: "game-over" },
      selection: null,
      message: "Partie terminée",
    };
  }
  return startActiveSequence(
    { ...state, boards, globalTurn: state.globalTurn + 1 },
    1
  );
}

export function gameReducer(state: GameState, action: GameAction): GameState {
  switch (action.type) {
    case "SELECT_DIE": {
      const { phase } = state;
      const d = state.dice[action.color];
      if (!d) return state;
      if (phase.kind === "active") {
        if (d.location !== "available") return state;
      } else if (phase.kind === "passive" && !phase.done) {
        if (d.location !== "discarded") return state;
      } else {
        return state;
      }

      if (action.color === "white") {
        return {
          ...state,
          selection: {
            color: "white",
            value: d.value,
            actingColor: null,
            legal: [],
            picked: [],
            maxPick: 1,
          },
          message: null,
        };
      }

      const ctx = ctxForPhase(state, action.color);
      if (!ctx) return state;
      const { legal, maxPick } = legalDestinations(action.color, d.value, ctx);
      if (legal.length === 0) {
        return { ...state, selection: null, message: NO_DIE_MOVE };
      }
      return {
        ...state,
        selection: {
          color: action.color,
          value: d.value,
          actingColor: action.color,
          legal,
          picked: [],
          maxPick,
        },
        message: null,
      };
    }

    case "CHOOSE_WHITE_COLOR": {
      const sel = state.selection;
      if (!sel || sel.color !== "white") return state;
      const ctx = ctxForPhase(state, "white");
      if (!ctx) return state;
      const { legal, maxPick } = legalDestinations(action.actingColor, sel.value, ctx);
      if (legal.length === 0) {
        return { ...state, message: NO_COLOR_MOVE };
      }
      return {
        ...state,
        selection: { ...sel, actingColor: action.actingColor, legal, picked: [], maxPick },
        message: null,
      };
    }

    case "PICK_CELL": {
      const sel = state.selection;
      if (!sel || sel.actingColor === null) return state;
      if (!sel.legal.includes(action.cellId)) return state;
      let picked: string[];
      if (sel.picked.includes(action.cellId)) {
        picked = sel.picked.filter((id) => id !== action.cellId);
      } else if (sel.picked.length >= sel.maxPick) {
        if (sel.maxPick === 1) {
          picked = [action.cellId];
        } else {
          return state;
        }
      } else {
        picked = [...sel.picked, action.cellId];
      }
      return { ...state, selection: { ...sel, picked } };
    }

    case "CANCEL_SELECTION":
      return { ...state, selection: null, message: null };

    case "VALIDATE_MOVE": {
      const sel = state.selection;
      const { phase } = state;
      if (
        !sel ||
        sel.actingColor === null ||
        sel.picked.length === 0 ||
        sel.picked.length > sel.maxPick
      ) {
        return state;
      }
      if (phase.kind === "active") {
        return validateActive(state, sel, phase.player, phase.round);
      }
      if (phase.kind === "passive" && !phase.done) {
        return validatePassive(state, sel, phase.player);
      }
      return state;
    }

    case "END_TURN": {
      const { phase } = state;
      if (phase.kind !== "active") return state;
      return endActiveSequence(state, phase.player);
    }

    case "PASS_PASSIVE": {
      const { phase } = state;
      if (phase.kind !== "passive" || phase.done) return state;
      return {
        ...state,
        phase: { kind: "passive", player: phase.player, done: true },
        selection: null,
        message: null,
      };
    }

    case "CONTINUE": {
      const { phase } = state;
      if (phase.kind !== "passive" || !phase.done) return state;
      return continueAfterPassive(state, phase.player);
    }

    case "RESET":
      return createInitialState();

    default:
      return state;
  }
}
