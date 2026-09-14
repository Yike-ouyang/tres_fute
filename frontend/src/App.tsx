import { useMemo, useReducer } from "react";
import BoardView from "./components/BoardView";
import DicePool from "./components/DicePool";
import DiscardSquare from "./components/DiscardSquare";
import WhiteColorChooser from "./components/WhiteColorChooser";
import GameControls from "./components/GameControls";
import BonusResolutionPanel from "./components/BonusResolutionPanel";
import PinkChoiceDialog from "./components/PinkChoiceDialog";
import ScoreTable from "./components/ScoreTable";
import Die from "./components/Die";
import { createInitialState } from "./game/reducer";
import { loggingReducer } from "./game/debug";
import {
  activeContext,
  anyAvailableDieHasMove,
  anyDiscardedDieHasMove,
  colorAvailability,
  passiveContext,
} from "./game/rules";
import {
  ALL_DIE_COLORS,
  PLAYER_IDS,
  type ActingColor,
  type DieColor,
  type PlayerId,
} from "./game/types";
import "./App.css";

const JOKER_VALUES = [1, 2, 3, 4, 5, 6];

function App() {
  const [state, dispatch] = useReducer(loggingReducer, undefined, createInitialState);
  const { phase, selection } = state;

  const legalSet = useMemo(() => new Set(selection?.legal ?? []), [selection]);
  const pickedSet = useMemo(() => new Set(selection?.picked ?? []), [selection]);

  // An immediate bonus or the pink dialog freezes normal progression.
  const overlayActive = !!(state.bonusResolution || state.pinkChoice);
  const overlayOwner: PlayerId | null =
    state.bonusResolution?.owner ?? state.pinkChoice?.owner ?? null;

  // Who must act, and in which mode.
  const actingPlayer: PlayerId | null =
    overlayOwner ??
    (phase.kind === "active"
      ? phase.player
      : phase.kind === "passive" && !phase.done
      ? phase.player
      : phase.kind === "plus1" && state.plus1Active !== null
      ? state.plus1Active
      : null);

  const isActive = phase.kind === "active" && !overlayActive;
  const isPassiveOpen = phase.kind === "passive" && !phase.done && !overlayActive;
  const isPlus1Selecting =
    phase.kind === "plus1" && state.plus1Active !== null && !overlayActive;

  const availableCount = ALL_DIE_COLORS.filter(
    (c) => state.dice[c].location === "available"
  ).length;

  const stuck = useMemo(() => {
    if (overlayActive) return false;
    if (phase.kind === "active") {
      return (
        availableCount > 0 &&
        !anyAvailableDieHasMove(state, phase.player, phase.round)
      );
    }
    if (phase.kind === "passive" && !phase.done) {
      return !anyDiscardedDieHasMove(state, phase.player);
    }
    return false;
  }, [state, phase, availableCount]);

  const canValidate =
    !!selection && selection.actingColor !== null && selection.picked.length >= 1;
  const hasSelection = !!selection;

  const jokerPending = !!state.jokerPending;
  const jokerNeedsValue = !!state.jokerPending && state.jokerPending.value === null;

  const canUsePlus1 = useMemo(() => {
    if (phase.kind !== "plus1") return false;
    const actor = phase.order[phase.current];
    const pb = state.boards[actor].bonuses.plus1;
    return pb.unlocked > pb.used;
  }, [phase, state.boards]);

  const showWhiteChooser =
    !!selection &&
    selection.color === "white" &&
    selection.actingColor === null &&
    actingPlayer !== null;

  const whiteAvailability = useMemo(() => {
    if (!showWhiteChooser || !selection) return null;
    const ctx =
      phase.kind === "active"
        ? activeContext(state, phase.player, phase.round, "white")
        : phase.kind === "passive"
        ? passiveContext(state, phase.player, "white")
        : phase.kind === "plus1" && state.plus1Active !== null
        ? passiveContext(state, state.plus1Active, "white")
        : null;
    return ctx ? colorAvailability(selection.value, ctx) : null;
  }, [showWhiteChooser, selection, state, phase]);

  const onSelectCell = (cellId: string) =>
    dispatch({ type: "PICK_CELL", cellId });

  const onRelance = () => dispatch({ type: "USE_RELANCE" });
  const onJoker = () => {
    if (phase.kind !== "active") return;
    dispatch({
      type: "START_JOKER",
      tokenIndex: state.boards[phase.player].bonuses.joker.used,
    });
  };

  const onBonusColor = (color: ActingColor) =>
    dispatch({ type: "BONUS_CHOOSE_COLOR", color });
  const onBonusValue = (value: number) =>
    dispatch({ type: "BONUS_CHOOSE_VALUE", value });
  const onBonusPlaceBlue = (cellId: string, value: number) =>
    dispatch({ type: "BONUS_PLACE_BLUE", cellId, value });
  const onBonusNoMove = () => dispatch({ type: "BONUS_NOMOVE_DONE" });
  const onPinkChoose = (option: "points" | "bonus") =>
    dispatch({ type: "PINK_CHOOSE", option });
  const onPinkCancel = () => dispatch({ type: "PINK_CANCEL" });

  return (
    <div className="board">
      <h1 className="board-title">Plateau de dés — Duel à deux joueurs</h1>

      <GameControls
        globalTurn={state.globalTurn}
        phase={phase}
        message={state.message}
        canValidate={canValidate}
        hasSelection={hasSelection}
        stuck={stuck}
        plus1Active={state.plus1Active}
        canUsePlus1={canUsePlus1}
        onValidate={() => dispatch({ type: "VALIDATE_MOVE" })}
        onCancel={() => dispatch({ type: "CANCEL_SELECTION" })}
        onEndTurn={() => dispatch({ type: "END_TURN" })}
        onPass={() => dispatch({ type: "PASS_PASSIVE" })}
        onContinue={() => dispatch({ type: "CONTINUE" })}
        onPlus1Use={() => dispatch({ type: "PLUS1_USE" })}
        onPlus1Skip={() => dispatch({ type: "PLUS1_SKIP" })}
        onReset={() => dispatch({ type: "RESET" })}
        overlayActive={overlayActive}
      />

      {state.bonusResolution && (
        <BonusResolutionPanel
          resolution={state.bonusResolution}
          board={state.boards[state.bonusResolution.owner]}
          onChooseColor={onBonusColor}
          onChooseValue={onBonusValue}
          onPlaceBlue={onBonusPlaceBlue}
          onNoMoveDone={onBonusNoMove}
        />
      )}

      {state.pinkChoice && (
        <PinkChoiceDialog
          choice={state.pinkChoice}
          onChoose={onPinkChoose}
          onCancel={onPinkCancel}
        />
      )}

      {/* Dés communs : disponibles + carré gris + choix du blanc */}
      <section className="zone shared-dice" aria-label="Dés communs">
        <div className="shared-dice-row">
          <DicePool
            state={state}
            selectable={isActive && !jokerNeedsValue}
            onSelectDie={(color) => dispatch({ type: "SELECT_DIE", color })}
          />
          <DiscardSquare
            state={state}
            selectable={isPassiveOpen}
            onSelectDie={(color) => dispatch({ type: "SELECT_DIE", color })}
          />
        </div>

        {jokerNeedsValue && (
          <div className="joker-value-chooser" aria-label="Choix de la valeur du joker">
            <span className="joker-value-label">Valeur du joker :</span>
            {JOKER_VALUES.map((v) => (
              <button
                key={v}
                type="button"
                className="btn btn-small"
                onClick={() => dispatch({ type: "SET_JOKER_VALUE", value: v })}
              >
                {v}
              </button>
            ))}
            <button
              type="button"
              className="btn btn-small"
              onClick={() => dispatch({ type: "CANCEL_JOKER" })}
            >
              Annuler
            </button>
          </div>
        )}

        {isPlus1Selecting && (
          <div className="plus1-picker" aria-label="Choix du dé pour le +1">
            <span className="plus1-picker-label">+1 : choisissez un dé</span>
            <div className="plus1-picker-row">
              {ALL_DIE_COLORS.map((color: DieColor) => (
                <Die
                  key={color}
                  color={color}
                  value={state.dice[color].value}
                  selected={selection?.color === color}
                  onClick={() => dispatch({ type: "SELECT_DIE", color })}
                />
              ))}
            </div>
          </div>
        )}

        {showWhiteChooser && whiteAvailability && (
          <WhiteColorChooser
            availability={whiteAvailability}
            selected={selection?.actingColor ?? null}
            onChoose={(actingColor) =>
              dispatch({ type: "CHOOSE_WHITE_COLOR", actingColor })
            }
          />
        )}
      </section>

      {/* Deux plateaux : Joueur 1 à gauche, Joueur 2 à droite */}
      <div className="boards-row">
        {PLAYER_IDS.map((playerId) => {
          const interactive = actingPlayer === playerId;
          const activeRound =
            phase.kind === "active" && phase.player === playerId
              ? phase.round
              : null;
          const activeOwner =
            phase.kind === "active" && phase.player === playerId && !overlayActive;
          return (
            <BoardView
              key={playerId}
              playerId={playerId}
              board={state.boards[playerId]}
              interactive={interactive}
              legal={interactive ? legalSet : EMPTY_SET}
              picked={interactive ? pickedSet : EMPTY_SET}
              activeRound={activeRound}
              activeOwner={activeOwner}
              jokerPending={activeOwner && jokerPending}
              onSelect={onSelectCell}
              onRelance={onRelance}
              onJoker={onJoker}
            />
          );
        })}
      </div>

      {phase.kind === "game-over" && <ScoreTable boards={state.boards} />}
    </div>
  );
}

const EMPTY_SET = new Set<string>();

export default App;
