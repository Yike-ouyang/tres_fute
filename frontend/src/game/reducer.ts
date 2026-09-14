import {
  ALL_DIE_COLORS,
  effectiveValue,
  otherPlayer,
  PLAYER_IDS,
  type BonusDieColor,
  type BonusResolution,
  type ChosenDie,
  type DieColor,
  type DieRuntime,
  type GameAction,
  type GameState,
  type PendingAdvance,
  type PinkResume,
  type PlayerBoard,
  type PlayerId,
  type Selection,
} from "./types";
import {
  activeContext,
  allUncheckedTurquoise,
  anyAvailableDieHasMove,
  anyChosenDieHasMove,
  anyDieHasPassiveMove,
  anyDiscardedDieHasMove,
  blueBonusOptions,
  blueSum,
  bonusBrownLegal,
  bonusHasAnyPlaceableValue,
  bonusYellowLegal,
  firstEmptyPink,
  legalDestinations,
  passiveContext,
  pinkPoints,
  pinkValue,
  rollValue,
  type MoveContext,
} from "./rules";
import {
  applyUnlocks,
  emptyBonusState,
  jokerTokenValue,
  PINK_BONUSES,
  PINK_MULTIPLIERS,
} from "./bonuses";

const STUCK_ACTIVE = "Aucun coup possible. Terminez le tour.";
const STUCK_PASSIVE = "Aucun coup possible. Vous pouvez passer.";
const NO_DIE_MOVE = "Aucun coup possible avec ce dé.";
const NO_COLOR_MOVE = "Cette couleur ne permet aucun coup.";
const JOKER_NEED_VALUE = "Joker : choisissez d'abord une valeur.";
const JOKER_PICK_DIE = "Joker : choisissez un dé à transformer.";
const JOKER_NEED_AVAILABLE = "Le joker s'applique à un dé disponible.";
const PINK_CHOICE_MSG = "Case rose : choisissez les points ou le bonus.";
const BONUS_NO_VALUE = "Aucune case disponible pour cette valeur.";
const FILL_SLOTS_MSG =
  "Compléter les dés actifs — sans effet. Ces choix ne produisent aucun coup.";
const PASSIVE_FALLBACK =
  "Aucun dé passif n’est jouable : vous pouvez choisir un dé actif.";

const DIE_COLOR_LABEL: Record<BonusDieColor, string> = {
  yellow: "jaune",
  turquoise: "turquoise",
  darkblue: "bleu foncé",
  brown: "marron",
  pink: "rose",
  black: "noir",
};

/** Colors that require the owner to pick a die value before placing. */
function needsValue(color: BonusDieColor): boolean {
  return color === "yellow" || color === "brown" || color === "pink";
}

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
    // Rerolling drops any joker value (fresh roll).
    next[color] =
      d.location === "available"
        ? { value: rollValue(), location: "available" }
        : { ...d };
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
    bonuses: emptyBonusState(),
  };
}

/** If there is exactly one legal destination, preselect it (still provisional). */
function withUniquePick(sel: Selection): Selection {
  if (sel.legal.length === 1 && sel.picked.length === 0) {
    return { ...sel, picked: [sel.legal[0]] };
  }
  return sel;
}

function hasEmptySlot(board: PlayerBoard): boolean {
  return board.slots.some((s) => s === null);
}

function dumpAvailable(dice: Record<DieColor, DieRuntime>): Record<DieColor, DieRuntime> {
  const next = {} as Record<DieColor, DieRuntime>;
  for (const color of ALL_DIE_COLORS) {
    const d = dice[color];
    next[color] =
      d.location === "available" ? { ...d, location: "discarded" } : { ...d };
  }
  return next;
}

function countAvailable(dice: Record<DieColor, DieRuntime>): number {
  return ALL_DIE_COLORS.filter((c) => dice[c].location === "available").length;
}

/** Open fill-slots if any I–III slot is empty; otherwise end the active sequence. */
function enterFillSlotsOrEnd(state: GameState, player: PlayerId): GameState {
  if (!hasEmptySlot(state.boards[player])) {
    return endActiveSequence(state, player);
  }
  return {
    ...state,
    phase: { kind: "fill-slots", player },
    selection: null,
    message: FILL_SLOTS_MSG,
    jokerPending: null,
  };
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
    if (anyDiscardedDieHasMove(state, phase.player)) {
      return state;
    }
    if (anyChosenDieHasMove(state, phase.player)) {
      return { ...state, message: PASSIVE_FALLBACK };
    }
    return { ...state, message: STUCK_PASSIVE };
  }
  return state;
}

/** Append colored bonus dice to the resolution queue, tagged with their owner. */
function enqueueDice(
  state: GameState,
  owner: PlayerId,
  colors: BonusDieColor[]
): GameState {
  if (colors.length === 0) return state;
  return {
    ...state,
    pendingBonuses: [
      ...state.pendingBonuses,
      ...colors.map((color) => ({ owner, color })),
    ],
  };
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
    plus1Active: null,
    jokerPending: null,
    bonusResolution: null,
    pinkChoice: null,
    pendingAdvance: null,
  };
  return withStuckMessage(base);
}

/**
 * Resolve the +1 window: skip any actor with no +1 left; when both actors have
 * been offered a +1, move on to the passive phase for the second actor.
 */
function settlePlus1(state: GameState): GameState {
  if (state.phase.kind !== "plus1") return state;
  const { order } = state.phase;
  let current = state.phase.current;
  while (current < order.length) {
    const actor = order[current];
    const pb = state.boards[actor].bonuses.plus1;
    if (pb.unlocked > pb.used) break;
    current++;
  }
  if (current >= order.length) {
    return withStuckMessage({
      ...state,
      phase: { kind: "passive", player: order[1], done: false },
      selection: null,
      message: null,
      plus1Active: null,
      jokerPending: null,
    });
  }
  return {
    ...state,
    phase: { kind: "plus1", order, current },
    selection: null,
    plus1Active: null,
    message: `Joueur ${order[current]} peut utiliser un +1.`,
  };
}

/**
 * End an active sequence: discard remaining dice, then open the +1 window for the
 * active player followed by the passive player before the passive phase begins.
 */
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
    phase: { kind: "plus1", order: [activePlayerId, passivePlayer], current: 0 },
    selection: null,
    message: null,
    plus1Active: null,
    jokerPending: null,
  };
  return settlePlus1(base);
}

// ---- Deferred advancement + bonus queue ----

/** Human-readable prompt for the current bonus resolution stage. */
function resolutionMessage(br: BonusResolution): string {
  const label = DIE_COLOR_LABEL[br.color];
  switch (br.stage) {
    case "chooseColor":
      return "Bonus dé noir : choisissez la couleur du dé bonus.";
    case "chooseValue":
      return `Bonus ${label} : choisissez une valeur.`;
    case "placing":
      if (br.color === "turquoise")
        return "Bonus turquoise : cochez la case turquoise de votre choix.";
      if (br.color === "darkblue")
        return "Bonus bleu foncé : choisissez la case et la valeur.";
      return `Bonus ${label} : choisissez la case.`;
    case "noMove":
      return `Bonus ${label} : aucun coup possible, terminez la résolution.`;
  }
}

/** Set up placement for a resolution whose color and (if needed) value are known. */
function enterPlacement(state: GameState, br: BonusResolution): GameState {
  const board = state.boards[br.owner];
  if (br.color === "turquoise") {
    const legal = allUncheckedTurquoise(board);
    if (legal.length === 0) {
      const next = { ...br, stage: "noMove" as const };
      return { ...state, bonusResolution: next, selection: null, message: resolutionMessage(next) };
    }
    const next = { ...br, stage: "placing" as const };
    return {
      ...state,
      bonusResolution: next,
      selection: withUniquePick({
        color: "turquoise",
        value: 0,
        actingColor: "turquoise",
        legal,
        picked: [],
        maxPick: 1,
        eliminationValue: 0,
      }),
      message: resolutionMessage(next),
    };
  }
  if (br.color === "darkblue") {
    const options = blueBonusOptions(board);
    const next = { ...br, stage: options.length === 0 ? ("noMove" as const) : ("placing" as const) };
    return { ...state, bonusResolution: next, selection: null, message: resolutionMessage(next) };
  }
  // yellow / brown need a chosen value already present.
  if (br.value === null) {
    const next = { ...br, stage: "chooseValue" as const };
    return { ...state, bonusResolution: next, selection: null, message: resolutionMessage(next) };
  }
  const legal =
    br.color === "yellow"
      ? bonusYellowLegal(board, br.value)
      : bonusBrownLegal(board, br.value);
  if (legal.length === 0) {
    if (
      (br.color === "yellow" || br.color === "brown") &&
      !bonusHasAnyPlaceableValue(board, br.color)
    ) {
      const dead = { ...br, stage: "noMove" as const };
      return { ...state, bonusResolution: dead, selection: null, message: resolutionMessage(dead) };
    }
    // Let the owner pick a different value instead of dead-ending.
    const next = { ...br, stage: "chooseValue" as const, value: null };
    return { ...state, bonusResolution: next, selection: null, message: BONUS_NO_VALUE };
  }
  const next = { ...br, stage: "placing" as const };
  return {
    ...state,
    bonusResolution: next,
    selection: withUniquePick({
      color: br.color as DieColor,
      value: br.value,
      actingColor: br.color as Exclude<DieColor, "white">,
      legal,
      picked: [],
      maxPick: 1,
      eliminationValue: 0,
    }),
    message: resolutionMessage(next),
  };
}

/** Open the next queued bonus (or return unchanged when the queue is empty). */
function openNextBonus(state: GameState): GameState {
  const [head, ...rest] = state.pendingBonuses;
  const base: GameState = { ...state, pendingBonuses: rest, selection: null, pinkChoice: null };
  const br: BonusResolution = {
    owner: head.owner,
    originColor: head.color,
    color: head.color,
    stage: "chooseValue",
    value: null,
  };
  if (head.color === "black") {
    const next = { ...br, stage: "chooseColor" as const };
    return { ...base, bonusResolution: next, message: resolutionMessage(next) };
  }
  if (needsValue(head.color)) {
    const board = state.boards[head.owner];
    if (
      (head.color === "yellow" || head.color === "brown" || head.color === "pink") &&
      !bonusHasAnyPlaceableValue(board, head.color)
    ) {
      const next = { ...br, stage: "noMove" as const };
      return { ...base, bonusResolution: next, message: resolutionMessage(next) };
    }
    return { ...base, bonusResolution: br, message: resolutionMessage(br) };
  }
  // turquoise / darkblue place immediately.
  return enterPlacement(base, br);
}

/**
 * Proceed after a move or a bonus resolution: if bonuses remain, open the next
 * one; otherwise perform the deferred transition, if any.
 */
function drainOrAdvance(state: GameState): GameState {
  if (state.bonusResolution || state.pinkChoice) return state;
  if (state.pendingBonuses.length > 0) return openNextBonus(state);
  if (state.pendingAdvance) {
    const pending = state.pendingAdvance;
    return advance({ ...state, pendingAdvance: null }, pending);
  }
  return state;
}

/** Execute a deferred transition once all pending bonuses are resolved. */
function advance(state: GameState, pending: PendingAdvance): GameState {
  switch (pending.kind) {
    case "activeNext":
      return withStuckMessage({
        ...state,
        phase: { kind: "active", player: pending.player, round: pending.round },
        dice: rerollAvailable(state.dice),
        selection: null,
        message: null,
        jokerPending: null,
      });
    case "endActive":
      return endActiveSequence(state, pending.player);
    case "fillSlots":
      return enterFillSlotsOrEnd(state, pending.player);
    case "passiveDone":
      return {
        ...state,
        phase: { kind: "passive", player: pending.player, done: true },
        selection: null,
        message: null,
      };
    case "plus1Next":
      return settlePlus1({
        ...state,
        phase: { kind: "plus1", order: pending.order, current: pending.current },
        selection: null,
        plus1Active: null,
        message: null,
      });
    case "startTurn":
      return startActiveSequence(state, pending.player);
  }
}

/** Finish the currently open bonus resolution (no lingering overlay), then drain. */
function finishBonusResolution(state: GameState): GameState {
  return drainOrAdvance({
    ...state,
    bonusResolution: null,
    selection: null,
    message: null,
  });
}

// ---- Turn bonuses granted at the start of each global turn ----

/** Check turn-N on both boards and enqueue any resulting colored dice (J1 then J2). */
function grantTurnBonuses(state: GameState, turn: number): GameState {
  const turnId = `turn-${turn}`;
  let s = state;
  for (const p of PLAYER_IDS) {
    const withCheck: PlayerBoard = {
      ...s.boards[p],
      checks: { ...s.boards[p].checks, [turnId]: true },
    };
    const { board, dieBonuses } = applyUnlocks(withCheck);
    s = enqueueDice({ ...s, boards: { ...s.boards, [p]: board } }, p, dieBonuses);
  }
  return s;
}

/**
 * Begin a global turn: grant the turn bonuses to both players first, resolve any
 * immediate colored dice (e.g. turn 4 black dice), then roll and start player 1.
 */
function beginGlobalTurn(state: GameState, turn: number): GameState {
  const granted = grantTurnBonuses(
    {
      ...state,
      globalTurn: turn,
      phase: { kind: "active", player: 1, round: 1 },
    },
    turn
  );
  return drainOrAdvance({
    ...granted,
    pendingAdvance: { kind: "startTurn", player: 1 },
  });
}

export function createInitialState(): GameState {
  const base: GameState = {
    globalTurn: 1,
    phase: { kind: "active", player: 1, round: 1 },
    boards: { 1: emptyBoard(), 2: emptyBoard() },
    dice: rollAllDice(),
    selection: null,
    message: null,
    plus1Active: null,
    jokerPending: null,
    pendingBonuses: [],
    bonusResolution: null,
    pinkChoice: null,
    pendingAdvance: null,
  };
  return beginGlobalTurn(base, 1);
}

function cellNumber(id: string): number {
  return Number(id.split("-").pop());
}

/**
 * Apply a validated non-pink selection's effect to a board (checks / values).
 * Pink is handled separately via the points-vs-bonus dialog.
 */
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

/** Which player must act, given the phase and any overlay. */
function actingPlayer(state: GameState): PlayerId | null {
  if (state.pinkChoice) return state.pinkChoice.owner;
  if (state.bonusResolution) return state.bonusResolution.owner;
  const { phase } = state;
  if (phase.kind === "active") return phase.player;
  if (phase.kind === "fill-slots") return phase.player;
  if (phase.kind === "passive" && !phase.done) return phase.player;
  if (phase.kind === "plus1" && state.plus1Active !== null) return state.plus1Active;
  return null;
}

function ctxForPhase(state: GameState, selectedColor: DieColor): MoveContext | null {
  const { phase } = state;
  if (phase.kind === "active") {
    return activeContext(state, phase.player, phase.round, selectedColor);
  }
  if (phase.kind === "passive" && !phase.done) {
    return passiveContext(state, phase.player, selectedColor);
  }
  if (phase.kind === "plus1" && state.plus1Active !== null) {
    // A +1 replay uses the actor's board with passive rules.
    return passiveContext(state, state.plus1Active, selectedColor);
  }
  return null;
}

/** Eliminate lower dice for a validated active move (chosen die + discards). */
function eliminateForMove(
  dice: Record<DieColor, DieRuntime>,
  sel: Selection
): Record<DieColor, DieRuntime> {
  const next = {} as Record<DieColor, DieRuntime>;
  for (const color of ALL_DIE_COLORS) {
    const d = dice[color];
    if (color === sel.color) {
      next[color] = { ...d, location: "chosen" };
    } else if (d.location === "available" && d.value < sel.eliminationValue) {
      next[color] = { ...d, location: "discarded" };
    } else {
      next[color] = { ...d };
    }
  }
  return next;
}

// ---- Move completion (deferred advancement + bonus enqueue) ----

function finishActiveAfterWrite(
  state: GameState,
  player: PlayerId,
  round: number,
  sel: Selection,
  extraDice: BonusDieColor[],
  boardWritten: PlayerBoard
): GameState {
  const slots = [...boardWritten.slots];
  slots[round - 1] = { color: sel.color, value: sel.value };
  const chosenThisTurn: ChosenDie[] = [
    ...boardWritten.chosenThisTurn,
    { color: sel.color, value: sel.value },
  ];
  const { board, dieBonuses } = applyUnlocks({ ...boardWritten, slots, chosenThisTurn });
  const dice = eliminateForMove(state.dice, sel);
  let next: GameState = {
    ...state,
    boards: { ...state.boards, [player]: board },
    dice,
    selection: null,
    message: null,
    jokerPending: null,
  };
  next = enqueueDice(next, player, [...extraDice, ...dieBonuses]);
  const pendingAdvance: PendingAdvance =
    round < 3 && countAvailable(dice) > 0
      ? { kind: "activeNext", player, round: round + 1 }
      : hasEmptySlot(board)
      ? { kind: "fillSlots", player }
      : { kind: "endActive", player };
  return drainOrAdvance({ ...next, pendingAdvance });
}

function finishPassiveAfterWrite(
  state: GameState,
  player: PlayerId,
  extraDice: BonusDieColor[],
  boardWritten: PlayerBoard
): GameState {
  const { board, dieBonuses } = applyUnlocks(boardWritten);
  let next: GameState = {
    ...state,
    boards: { ...state.boards, [player]: board },
    selection: null,
    message: null,
  };
  next = enqueueDice(next, player, [...extraDice, ...dieBonuses]);
  return drainOrAdvance({ ...next, pendingAdvance: { kind: "passiveDone", player } });
}

function finishPlus1AfterWrite(
  state: GameState,
  actor: PlayerId,
  extraDice: BonusDieColor[],
  boardWritten: PlayerBoard
): GameState {
  if (state.phase.kind !== "plus1") return state;
  const pb = boardWritten.bonuses.plus1;
  const withUse: PlayerBoard = {
    ...boardWritten,
    bonuses: { ...boardWritten.bonuses, plus1: { ...pb, used: pb.used + 1 } },
  };
  const { board, dieBonuses } = applyUnlocks(withUse);
  let next: GameState = {
    ...state,
    boards: { ...state.boards, [actor]: board },
    selection: null,
    plus1Active: null,
    message: null,
  };
  next = enqueueDice(next, actor, [...extraDice, ...dieBonuses]);
  return drainOrAdvance({
    ...next,
    pendingAdvance: {
      kind: "plus1Next",
      order: state.phase.order,
      current: state.phase.current + 1,
    },
  });
}

/** Open the pink dialog for a normal (non-bonus) pink move, or write cell 1 directly. */
function openPinkForMove(
  state: GameState,
  owner: PlayerId,
  sel: Selection,
  resume: PinkResume
): GameState {
  const dest = sel.picked[0];
  const n = cellNumber(dest);
  const effectiveValue = sel.value;
  if (n === 1) {
    const board: PlayerBoard = {
      ...state.boards[owner],
      values: { ...state.boards[owner].values, [dest]: effectiveValue },
    };
    return completeAfterPinkWrite(state, resume, [], board);
  }
  const bonusEffect = PINK_BONUSES[n - 1];
  return {
    ...state,
    pinkChoice: {
      owner,
      cellId: dest,
      position: n,
      effectiveValue,
      multiplier: PINK_MULTIPLIERS[n - 1],
      bonusSlotId: bonusEffect.kind === "none" ? null : `pink-${n}`,
      bonusEffect,
      resume,
    },
    selection: null,
    message: PINK_CHOICE_MSG,
  };
}

/** Route a written board to the correct completion, given the pink resume kind. */
function completeAfterPinkWrite(
  state: GameState,
  resume: PinkResume,
  extraDice: BonusDieColor[],
  boardWritten: PlayerBoard
): GameState {
  switch (resume.kind) {
    case "active":
      return finishActiveAfterWrite(state, resume.player, resume.round, resume.sel, extraDice, boardWritten);
    case "passive":
      return finishPassiveAfterWrite(state, resume.player, extraDice, boardWritten);
    case "plus1":
      return finishPlus1AfterWrite(state, resume.actor, extraDice, boardWritten);
    case "bonusDie": {
      const withBoard: GameState = {
        ...state,
        boards: { ...state.boards, [resume.owner]: boardWritten },
      };
      const enqueued = enqueueDice(withBoard, resume.owner, extraDice);
      return finishBonusResolution(enqueued);
    }
  }
}

function validateActive(state: GameState, sel: Selection, player: PlayerId, round: number): GameState {
  if (sel.actingColor === "pink") {
    return openPinkForMove(state, player, sel, { kind: "active", player, round, sel });
  }
  const moved = applyMoveToBoard(state.boards[player], sel, state.dice);
  return finishActiveAfterWrite(state, player, round, sel, [], moved);
}

function validatePassive(state: GameState, sel: Selection, player: PlayerId): GameState {
  if (sel.actingColor === "pink") {
    return openPinkForMove(state, player, sel, { kind: "passive", player, sel });
  }
  const moved = applyMoveToBoard(state.boards[player], sel, state.dice);
  return finishPassiveAfterWrite(state, player, [], moved);
}

function validatePlus1(state: GameState, sel: Selection, actor: PlayerId): GameState {
  if (sel.actingColor === "pink") {
    return openPinkForMove(state, actor, sel, { kind: "plus1", actor, sel });
  }
  const moved = applyMoveToBoard(state.boards[actor], sel, state.dice);
  return finishPlus1AfterWrite(state, actor, [], moved);
}

function continueAfterPassive(state: GameState, player: PlayerId): GameState {
  if (player === 2) {
    // Player 2 becomes active in the same global turn.
    return startActiveSequence(state, 2);
  }
  // Player 1 was passive: the global turn ends.
  if (state.globalTurn >= 6) {
    return {
      ...state,
      phase: { kind: "game-over" },
      selection: null,
      message: "Partie terminée",
      plus1Active: null,
      jokerPending: null,
    };
  }
  return beginGlobalTurn(state, state.globalTurn + 1);
}

export function gameReducer(state: GameState, action: GameAction): GameState {
  switch (action.type) {
    case "SELECT_DIE": {
      if (state.bonusResolution || state.pinkChoice) return state;
      const { phase } = state;
      const actor = actingPlayer(state);
      if (actor === null) return state;

      let dice = state.dice;
      let boards = state.boards;
      let jokerPending = state.jokerPending;
      let jokerApplied = false;

      // If a joker is pending, apply it to the picked die before selecting.
      if (jokerPending && phase.kind === "active") {
        if (jokerPending.value === null) {
          return { ...state, message: JOKER_NEED_VALUE };
        }
        const target = state.dice[action.color];
        if (!target || target.location !== "available") {
          return { ...state, message: JOKER_NEED_AVAILABLE };
        }
        dice = {
          ...dice,
          [action.color]: { ...target, jokerValue: jokerPending.value },
        };
        const jb = boards[actor].bonuses.joker;
        boards = {
          ...boards,
          [actor]: {
            ...boards[actor],
            bonuses: { ...boards[actor].bonuses, joker: { ...jb, used: jb.used + 1 } },
          },
        };
        jokerPending = null;
        jokerApplied = true;
      }

      const d = dice[action.color];
      if (!d) return state;
      if (phase.kind === "active") {
        if (d.location !== "available") return state;
      } else if (phase.kind === "passive" && !phase.done) {
        const discardedOk = anyDiscardedDieHasMove(state, phase.player);
        if (discardedOk) {
          if (d.location !== "discarded") return state;
        } else if (d.location !== "chosen") {
          return state;
        }
      } else if (phase.kind === "plus1" && state.plus1Active !== null) {
        // A +1 replay may use any die, regardless of location.
      } else {
        return state;
      }

      const baseState: GameState = jokerApplied
        ? { ...state, dice, boards, jokerPending: null }
        : state;
      const value = effectiveValue(d);
      const eliminationValue = d.value;

      if (action.color === "white") {
        return {
          ...baseState,
          selection: {
            color: "white",
            value,
            actingColor: null,
            legal: [],
            picked: [],
            maxPick: 1,
            eliminationValue,
          },
          message: null,
        };
      }

      const ctx = ctxForPhase(baseState, action.color);
      if (!ctx) return baseState;
      const { legal, maxPick } = legalDestinations(action.color, value, ctx);
      if (legal.length === 0) {
        return { ...baseState, selection: null, message: NO_DIE_MOVE };
      }
      const fallbackMsg =
        phase.kind === "passive" &&
        !phase.done &&
        !anyDiscardedDieHasMove(baseState, phase.player)
          ? PASSIVE_FALLBACK
          : null;
      return {
        ...baseState,
        selection: withUniquePick({
          color: action.color,
          value,
          actingColor: action.color,
          legal,
          picked: [],
          maxPick,
          eliminationValue,
        }),
        message: fallbackMsg,
      };
    }

    case "CHOOSE_WHITE_COLOR": {
      if (state.bonusResolution || state.pinkChoice) return state;
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
        selection: withUniquePick({
          ...sel,
          actingColor: action.actingColor,
          legal,
          picked: [],
          maxPick,
        }),
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

    case "CANCEL_SELECTION": {
      // During a bonus placement, cancelling steps back to the value choice
      // (yellow / brown) or just clears the provisional pick (turquoise).
      if (state.bonusResolution && state.bonusResolution.stage === "placing") {
        const br = state.bonusResolution;
        if (br.color === "yellow" || br.color === "brown") {
          const next = { ...br, stage: "chooseValue" as const, value: null };
          return { ...state, selection: null, bonusResolution: next, message: resolutionMessage(next) };
        }
        return {
          ...state,
          selection: state.selection ? { ...state.selection, picked: [] } : null,
        };
      }
      return {
        ...state,
        selection: null,
        plus1Active: state.phase.kind === "plus1" ? null : state.plus1Active,
        message: null,
      };
    }

    case "VALIDATE_MOVE": {
      // Bonus placement (yellow / brown / turquoise) writes to the owner's board
      // without eliminating dice or consuming a shared die.
      if (state.bonusResolution && state.bonusResolution.stage === "placing") {
        const br = state.bonusResolution;
        const sel = state.selection;
        if (!sel || sel.picked.length === 0) return state;
        const owner = br.owner;
        let board = state.boards[owner];
        const cell = sel.picked[0];
        if (br.color === "turquoise" || br.color === "yellow") {
          board = { ...board, checks: { ...board.checks, [cell]: true } };
        } else if (br.color === "brown") {
          const idx = cellNumber(cell);
          const checks = { ...board.checks, [cell]: true };
          const brownDisabled = { ...board.brownDisabled };
          for (let n = 1; n < idx; n++) {
            const id = `brown-cell-${n}`;
            if (!checks[id]) brownDisabled[id] = true;
          }
          board = { ...board, checks, brownDisabled, brownLastChecked: idx };
        } else {
          return state;
        }
        const { board: unlocked, dieBonuses } = applyUnlocks(board);
        const next = enqueueDice(
          { ...state, boards: { ...state.boards, [owner]: unlocked }, selection: null },
          owner,
          dieBonuses
        );
        return finishBonusResolution(next);
      }

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
      if (phase.kind === "plus1" && state.plus1Active !== null) {
        return validatePlus1(state, sel, state.plus1Active);
      }
      return state;
    }

    case "END_TURN": {
      if (state.bonusResolution || state.pinkChoice) return state;
      const { phase } = state;
      if (phase.kind !== "active") return state;
      const dumped: GameState = {
        ...state,
        dice: dumpAvailable(state.dice),
        selection: null,
        jokerPending: null,
      };
      return enterFillSlotsOrEnd(dumped, phase.player);
    }

    case "PASS_PASSIVE": {
      if (state.bonusResolution || state.pinkChoice) return state;
      const { phase } = state;
      if (phase.kind !== "passive" || phase.done) return state;
      if (anyDieHasPassiveMove(state, phase.player)) return state;
      return {
        ...state,
        phase: { kind: "passive", player: phase.player, done: true },
        selection: null,
        message: null,
      };
    }

    case "CONTINUE": {
      if (state.bonusResolution || state.pinkChoice) return state;
      const { phase } = state;
      if (phase.kind !== "passive" || !phase.done) return state;
      return continueAfterPassive(state, phase.player);
    }

    case "USE_RELANCE": {
      if (state.bonusResolution || state.pinkChoice) return state;
      const { phase } = state;
      if (phase.kind !== "active") return state;
      const board = state.boards[phase.player];
      const rb = board.bonuses.relance;
      if (rb.unlocked <= rb.used) return state;
      const boards = {
        ...state.boards,
        [phase.player]: {
          ...board,
          bonuses: { ...board.bonuses, relance: { ...rb, used: rb.used + 1 } },
        },
      };
      return withStuckMessage({
        ...state,
        boards,
        dice: rerollAvailable(state.dice),
        selection: null,
        jokerPending: null,
        message: null,
      });
    }

    case "START_JOKER": {
      if (state.bonusResolution || state.pinkChoice) return state;
      const { phase } = state;
      if (phase.kind !== "active") return state;
      const jb = state.boards[phase.player].bonuses.joker;
      // Tokens are consumed in unlock order; only the next token may be used.
      const idx = jb.used;
      if (idx >= jb.unlocked) return state;
      if (state.jokerPending) return state;
      const value = jokerTokenValue(idx);
      return {
        ...state,
        jokerPending: { tokenIndex: idx, value },
        selection: null,
        message: value === null ? JOKER_NEED_VALUE : JOKER_PICK_DIE,
      };
    }

    case "SET_JOKER_VALUE": {
      const { phase } = state;
      if (phase.kind !== "active") return state;
      if (!state.jokerPending || state.jokerPending.value !== null) return state;
      if (action.value < 1 || action.value > 6) return state;
      return {
        ...state,
        jokerPending: { ...state.jokerPending, value: action.value },
        message: JOKER_PICK_DIE,
      };
    }

    case "CANCEL_JOKER": {
      if (!state.jokerPending) return state;
      return { ...state, jokerPending: null, message: null };
    }

    case "PLUS1_USE": {
      if (state.bonusResolution || state.pinkChoice) return state;
      const { phase } = state;
      if (phase.kind !== "plus1") return state;
      if (state.plus1Active !== null) return state;
      const actor = phase.order[phase.current];
      const pb = state.boards[actor].bonuses.plus1;
      if (pb.unlocked <= pb.used) return state;
      return {
        ...state,
        plus1Active: actor,
        selection: null,
        message: `Joueur ${actor} : choisissez un dé pour le +1.`,
      };
    }

    case "PLUS1_SKIP": {
      if (state.bonusResolution || state.pinkChoice) return state;
      const { phase } = state;
      if (phase.kind !== "plus1") return state;
      return settlePlus1({
        ...state,
        phase: { kind: "plus1", order: phase.order, current: phase.current + 1 },
        selection: null,
        plus1Active: null,
        message: null,
      });
    }

    case "BONUS_CHOOSE_COLOR": {
      const br = state.bonusResolution;
      if (!br || br.stage !== "chooseColor") return state;
      const chosen: BonusDieColor = action.color;
      const withColor: BonusResolution = { ...br, color: chosen, value: null };
      if (needsValue(chosen)) {
        const board = state.boards[br.owner];
        if (
          (chosen === "yellow" || chosen === "brown" || chosen === "pink") &&
          !bonusHasAnyPlaceableValue(board, chosen)
        ) {
          const next = { ...withColor, stage: "noMove" as const };
          return { ...state, bonusResolution: next, selection: null, message: resolutionMessage(next) };
        }
        const next = { ...withColor, stage: "chooseValue" as const };
        return { ...state, bonusResolution: next, message: resolutionMessage(next) };
      }
      return enterPlacement(state, withColor);
    }

    case "BONUS_CHOOSE_VALUE": {
      const br = state.bonusResolution;
      if (!br || br.stage !== "chooseValue") return state;
      if (action.value < 1 || action.value > 6) return state;
      if (br.color === "pink") {
        const board = state.boards[br.owner];
        const dest = firstEmptyPink(board.values);
        if (!dest) {
          const next = { ...br, stage: "noMove" as const };
          return { ...state, bonusResolution: next, selection: null, message: resolutionMessage(next) };
        }
        // Pink bonus die: reuse the pink dialog (or write cell 1 directly).
        return openPinkForMove(
          { ...state, bonusResolution: { ...br, value: action.value, stage: "placing" } },
          br.owner,
          {
            color: "pink",
            value: action.value,
            actingColor: "pink",
            legal: [dest],
            picked: [dest],
            maxPick: 1,
            eliminationValue: 0,
          },
          { kind: "bonusDie", owner: br.owner }
        );
      }
      return enterPlacement(state, { ...br, value: action.value });
    }

    case "BONUS_PLACE_BLUE": {
      const br = state.bonusResolution;
      if (!br || br.color !== "darkblue" || br.stage !== "placing") return state;
      const owner = br.owner;
      const board: PlayerBoard = {
        ...state.boards[owner],
        values: { ...state.boards[owner].values, [action.cellId]: action.value },
      };
      const { board: unlocked, dieBonuses } = applyUnlocks(board);
      const next = enqueueDice(
        { ...state, boards: { ...state.boards, [owner]: unlocked } },
        owner,
        dieBonuses
      );
      return finishBonusResolution(next);
    }

    case "BONUS_NOMOVE_DONE": {
      const br = state.bonusResolution;
      if (!br) return state;
      if (br.stage === "noMove") return finishBonusResolution(state);
      if (
        br.stage === "chooseValue" &&
        (br.color === "yellow" || br.color === "brown" || br.color === "pink") &&
        !bonusHasAnyPlaceableValue(state.boards[br.owner], br.color)
      ) {
        return finishBonusResolution(state);
      }
      return state;
    }

    case "PINK_CHOOSE": {
      const choice = state.pinkChoice;
      if (!choice) return state;
      if (action.option === "bonus" && choice.bonusEffect.kind === "none") {
        return state;
      }
      const owner = choice.owner;
      const src = state.boards[owner];
      let values = { ...src.values };
      let bonuses = src.bonuses;
      const extraDice: BonusDieColor[] = [];
      if (action.option === "points") {
        values[choice.cellId] = pinkPoints(choice.effectiveValue, choice.multiplier);
      } else {
        values[choice.cellId] = pinkValue(choice.effectiveValue);
        const eff = choice.bonusEffect;
        if (eff.kind === "cumulative") {
          bonuses = {
            ...bonuses,
            [eff.bonus]: { ...bonuses[eff.bonus], unlocked: bonuses[eff.bonus].unlocked + 1 },
          };
        } else if (eff.kind === "die") {
          extraDice.push(eff.color);
        }
        if (choice.bonusSlotId) {
          bonuses = {
            ...bonuses,
            slotsUnlocked: { ...bonuses.slotsUnlocked, [choice.bonusSlotId]: true },
          };
        }
      }
      const boardWritten: PlayerBoard = { ...src, values, bonuses };
      const cleared: GameState = { ...state, pinkChoice: null };
      return completeAfterPinkWrite(cleared, choice.resume, extraDice, boardWritten);
    }

    case "PINK_CANCEL": {
      const choice = state.pinkChoice;
      if (!choice) return state;
      if (choice.resume.kind === "bonusDie") {
        const br = state.bonusResolution;
        if (br) {
          const next = { ...br, stage: "chooseValue" as const, value: null };
          return { ...state, pinkChoice: null, bonusResolution: next, message: resolutionMessage(next) };
        }
        return { ...state, pinkChoice: null };
      }
      // Restore the prior selection so nothing is consumed.
      return { ...state, pinkChoice: null, selection: choice.resume.sel, message: null };
    }

    case "FILL_SLOT": {
      if (state.bonusResolution || state.pinkChoice) return state;
      const { phase } = state;
      if (phase.kind !== "fill-slots") return state;
      const d = state.dice[action.color];
      if (!d || d.location !== "discarded") return state;
      const board = state.boards[phase.player];
      const idx = board.slots.findIndex((s) => s === null);
      if (idx < 0) return enterFillSlotsOrEnd(state, phase.player);
      const slots = [...board.slots];
      slots[idx] = { color: action.color, value: d.value };
      const dice = {
        ...state.dice,
        [action.color]: { ...d, location: "chosen" as const },
      };
      const next: GameState = {
        ...state,
        dice,
        boards: { ...state.boards, [phase.player]: { ...board, slots } },
        selection: null,
      };
      return enterFillSlotsOrEnd(next, phase.player);
    }

    case "RESET":
      return createInitialState();

    default:
      return state;
  }
}
