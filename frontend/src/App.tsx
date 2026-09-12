import { useMemo, useReducer } from "react";
import BoardView from "./components/BoardView";
import DicePool from "./components/DicePool";
import DiscardSquare from "./components/DiscardSquare";
import WhiteColorChooser from "./components/WhiteColorChooser";
import GameControls from "./components/GameControls";
import { createInitialState } from "./game/reducer";
import { loggingReducer } from "./game/debug";
import {
  activeContext,
  anyAvailableDieHasMove,
  anyDiscardedDieHasMove,
  colorAvailability,
  passiveContext,
} from "./game/rules";
import { ALL_DIE_COLORS, PLAYER_IDS, type PlayerId } from "./game/types";
import "./App.css";

function App() {
  const [state, dispatch] = useReducer(loggingReducer, undefined, createInitialState);
  const { phase, selection } = state;

  const legalSet = useMemo(() => new Set(selection?.legal ?? []), [selection]);
  const pickedSet = useMemo(() => new Set(selection?.picked ?? []), [selection]);

  // Who must act, and in which mode.
  const actingPlayer: PlayerId | null =
    phase.kind === "active"
      ? phase.player
      : phase.kind === "passive" && !phase.done
      ? phase.player
      : null;

  const isActive = phase.kind === "active";
  const isPassiveOpen = phase.kind === "passive" && !phase.done;

  const availableCount = ALL_DIE_COLORS.filter(
    (c) => state.dice[c].location === "available"
  ).length;

  const stuck = useMemo(() => {
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
        : null;
    return ctx ? colorAvailability(selection.value, ctx) : null;
  }, [showWhiteChooser, selection, state, phase]);

  const onSelectCell = (cellId: string) =>
    dispatch({ type: "PICK_CELL", cellId });

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
        onValidate={() => dispatch({ type: "VALIDATE_MOVE" })}
        onCancel={() => dispatch({ type: "CANCEL_SELECTION" })}
        onEndTurn={() => dispatch({ type: "END_TURN" })}
        onPass={() => dispatch({ type: "PASS_PASSIVE" })}
        onContinue={() => dispatch({ type: "CONTINUE" })}
        onReset={() => dispatch({ type: "RESET" })}
      />

      {/* Dés communs : disponibles + carré gris + choix du blanc */}
      <section className="zone shared-dice" aria-label="Dés communs">
        <div className="shared-dice-row">
          <DicePool
            state={state}
            selectable={isActive}
            onSelectDie={(color) => dispatch({ type: "SELECT_DIE", color })}
          />
          <DiscardSquare
            state={state}
            selectable={isPassiveOpen}
            onSelectDie={(color) => dispatch({ type: "SELECT_DIE", color })}
          />
        </div>
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
          return (
            <BoardView
              key={playerId}
              playerId={playerId}
              board={state.boards[playerId]}
              interactive={interactive}
              legal={interactive ? legalSet : EMPTY_SET}
              picked={interactive ? pickedSet : EMPTY_SET}
              activeRound={activeRound}
              onSelect={onSelectCell}
            />
          );
        })}
      </div>
    </div>
  );
}

const EMPTY_SET = new Set<string>();

export default App;
