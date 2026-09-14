import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import BoardView from "./components/BoardView";
import DicePool from "./components/DicePool";
import DiscardSquare from "./components/DiscardSquare";
import WhiteColorChooser from "./components/WhiteColorChooser";
import GameControls from "./components/GameControls";
import BonusResolutionPanel from "./components/BonusResolutionPanel";
import PinkChoiceDialog from "./components/PinkChoiceDialog";
import ScoreTable from "./components/ScoreTable";
import Die from "./components/Die";
import {
  ApiError,
  createGame,
  getGame,
  postAction,
  postAdvance,
  resetGame,
  type EngineAction,
  type GameSnapshot,
} from "./api/client";
import {
  ALL_DIE_COLORS,
  PLAYER_IDS,
  type DieColor,
  type PlayerId,
} from "./game/types";
import "./App.css";

const JOKER_VALUES = [1, 2, 3, 4, 5, 6];
const EMPTY_SET = new Set<string>();

function App() {
  const [snap, setSnap] = useState<GameSnapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [simulating, setSimulating] = useState(false);
  const [simProgress, setSimProgress] = useState<string | null>(null);
  const snapRef = useRef(snap);
  snapRef.current = snap;
  const busyRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    createGame()
      .then((g) => {
        if (!cancelled) setSnap(g);
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Serveur indisponible");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const applySnap = (next: GameSnapshot) => {
    setSnap(next);
    setError(null);
  };

  const send = useCallback(async (action: EngineAction) => {
    const current = snapRef.current;
    if (!current || busyRef.current || current.advance.running) return;
    busyRef.current = true;
    setBusy(true);
    try {
      const next = await postAction(current.id, current.version, action);
      applySnap(next);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && e.snapshot) {
        applySnap(e.snapshot);
        setError("État resynchronisé (version dépassée).");
      } else {
        setError(e instanceof Error ? e.message : "Serveur indisponible");
      }
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }, []);

  const onReset = useCallback(async () => {
    const current = snapRef.current;
    if (!current || busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    try {
      applySnap(await resetGame(current.id, current.version));
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && e.snapshot) {
        applySnap(e.snapshot);
      } else {
        setError(e instanceof Error ? e.message : "Serveur indisponible");
      }
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }, []);

  const onAdvance = useCallback(async (n: number) => {
    const current = snapRef.current;
    if (!current || busyRef.current || current.advance.running) return;
    busyRef.current = true;
    setBusy(true);
    setSimulating(true);
    setSimProgress(`Avance automatique : 0 / ${n} tour(s)…`);
    try {
      let next = await postAdvance(current.id, current.version, n);
      applySnap(next);
      while (next.advance.running) {
        await new Promise((r) => setTimeout(r, 200));
        next = await getGame(next.id);
        applySnap(next);
        setSimProgress(
          next.advance.message ??
            `Avance automatique : ${next.advance.completed} / ${next.advance.quota} tour(s)…`
        );
      }
      setSimProgress(next.advance.message);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409 && e.snapshot) {
        applySnap(e.snapshot);
        setError("Avance refusée (conflit).");
      } else {
        setError(e instanceof Error ? e.message : "Serveur indisponible");
      }
    } finally {
      busyRef.current = false;
      setBusy(false);
      setSimulating(false);
    }
  }, []);

  const legalSet = useMemo(() => new Set(snap?.state.selection?.legal ?? []), [snap]);
  const pickedSet = useMemo(() => new Set(snap?.state.selection?.picked ?? []), [snap]);

  if (!snap) {
    return (
      <div className="board">
        <h1 className="board-title">Plateau de dés — Duel à deux joueurs</h1>
        <p className="game-message" role="status">
          {error ?? "Connexion au moteur de règles…"}
        </p>
      </div>
    );
  }

  const state = snap.state;
  const { phase, selection } = state;

  const overlayActive = !!(state.bonusResolution || state.pinkChoice);
  const overlayOwner: PlayerId | null =
    state.bonusResolution?.owner ?? state.pinkChoice?.owner ?? null;
  const actingPlayer: PlayerId | null =
    overlayOwner ??
    (phase.kind === "active"
      ? phase.player
      : phase.kind === "fill-slots"
      ? phase.player
      : phase.kind === "passive" && !phase.done
      ? phase.player
      : phase.kind === "plus1" && state.plus1Active !== null
      ? state.plus1Active
      : null);

  const locked = overlayActive || simulating || busy;
  const isActive = phase.kind === "active" && !locked;
  const isPassiveOpen = phase.kind === "passive" && !phase.done && !locked;
  const isPlus1Selecting =
    phase.kind === "plus1" && state.plus1Active !== null && !locked;
  const isFillSlots = phase.kind === "fill-slots" && !locked;

  const discardedHasMove = isPassiveOpen && snap.passiveFlags.discardedHasMove;
  const chosenFallback = isPassiveOpen && snap.passiveFlags.chosenFallback;
  const stuck = snap.stuck && !locked;
  const canValidate =
    !!selection && selection.actingColor !== null && selection.picked.length >= 1;
  const hasSelection = !!selection;
  const jokerPending = !!state.jokerPending;
  const jokerNeedsValue = !!state.jokerPending && state.jokerPending.value === null;
  const canUsePlus1 = snap.legalActions.some((a) => a.type === "begin_plus1");
  const showWhiteChooser =
    !!selection &&
    selection.color === "white" &&
    selection.actingColor === null &&
    actingPlayer !== null;
  const whiteAvailability = snap.whiteAvailability;

  return (
    <div className="board">
      <h1 className="board-title">Plateau de dés — Duel à deux joueurs</h1>

      {error && (
        <div className="game-message" role="alert">
          {error}
        </div>
      )}

      <GameControls
        globalTurn={state.globalTurn}
        phase={phase}
        message={state.message}
        canValidate={canValidate}
        hasSelection={hasSelection}
        stuck={stuck}
        plus1Active={state.plus1Active}
        canUsePlus1={canUsePlus1}
        onValidate={() => void send({ type: "confirm_move" })}
        onCancel={() => void send({ type: "cancel_selection" })}
        onEndTurn={() => void send({ type: "end_active_early" })}
        onPass={() => void send({ type: "pass_passive" })}
        onContinue={() => void send({ type: "continue" })}
        onPlus1Use={() => void send({ type: "begin_plus1" })}
        onPlus1Skip={() => void send({ type: "skip_plus1" })}
        onReset={() => void onReset()}
        overlayActive={overlayActive}
        remainingTurns={snap.remainingTurns}
        simulating={simulating || busy}
        simProgress={simProgress}
        onAdvance={(n) => void onAdvance(n)}
      />

      {state.bonusResolution && (
        <div className={simulating ? "is-sim-locked" : undefined}>
          <BonusResolutionPanel
            resolution={state.bonusResolution}
            legalActions={snap.legalActions}
            onChooseColor={(color) => void send({ type: "choose_bonus_color", color })}
            onChooseValue={(value) => void send({ type: "choose_bonus_value", value })}
            onPlaceBlue={(cellId, value) =>
              void send({ type: "place_bonus_blue", cell_id: cellId, value })
            }
            onNoMoveDone={() => void send({ type: "dismiss_impossible_bonus" })}
          />
        </div>
      )}

      {state.pinkChoice && (
        <div className={simulating ? "is-sim-locked" : undefined}>
          <PinkChoiceDialog
            choice={state.pinkChoice}
            onChoose={(option) => void send({ type: "choose_pink_option", option })}
            onCancel={() => void send({ type: "cancel_pink_option" })}
          />
        </div>
      )}

      <section className="zone shared-dice" aria-label="Dés communs">
        <div className="shared-dice-row">
          <DicePool
            state={state}
            selectable={isActive && !jokerNeedsValue}
            onSelectDie={(color) => void send({ type: "select_die", color })}
          />
          <DiscardSquare
            state={state}
            selectable={isFillSlots || (isPassiveOpen && discardedHasMove)}
            onSelectDie={(color) =>
              void send(
                isFillSlots
                  ? { type: "fill_slot_dummy", color }
                  : { type: "select_die", color }
              )
            }
          />
        </div>

        {jokerNeedsValue && !simulating && (
          <div className="joker-value-chooser" aria-label="Choix de la valeur du joker">
            <span className="joker-value-label">Valeur du joker :</span>
            {JOKER_VALUES.map((v) => (
              <button
                key={v}
                type="button"
                className="btn btn-small"
                onClick={() => void send({ type: "set_joker_value", value: v })}
              >
                {v}
              </button>
            ))}
            <button
              type="button"
              className="btn btn-small"
              onClick={() => void send({ type: "cancel_joker" })}
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
                  onClick={() => void send({ type: "select_die", color })}
                />
              ))}
            </div>
          </div>
        )}

        {showWhiteChooser && whiteAvailability && !simulating && (
          <WhiteColorChooser
            availability={whiteAvailability}
            selected={selection?.actingColor ?? null}
            onChoose={(actingColor) =>
              void send({ type: "choose_white_color", acting_color: actingColor })
            }
          />
        )}
      </section>

      <div className="boards-row">
        {PLAYER_IDS.map((playerId) => {
          const interactive = actingPlayer === playerId;
          const activeRound =
            phase.kind === "active" && phase.player === playerId ? phase.round : null;
          const activeOwner =
            phase.kind === "active" && phase.player === playerId && !locked;
          return (
            <BoardView
              key={playerId}
              playerId={playerId}
              board={state.boards[playerId]}
              score={snap.scores[String(playerId) as "1" | "2"]}
              interactive={interactive && !simulating && !busy}
              legal={interactive && !simulating ? legalSet : EMPTY_SET}
              picked={interactive && !simulating ? pickedSet : EMPTY_SET}
              activeRound={activeRound}
              activeOwner={activeOwner}
              jokerPending={Boolean(activeOwner && jokerPending)}
              onSelect={(cellId) => void send({ type: "pick_cell", cell_id: cellId })}
              onRelance={() => void send({ type: "use_relance" })}
              onJoker={() => {
                if (phase.kind !== "active") return;
                void send({
                  type: "start_joker",
                  token_index: state.boards[phase.player].bonuses.joker.used,
                });
              }}
              onSelectDie={(color) => void send({ type: "select_die", color })}
              selectedDie={selection?.color ?? null}
              slotDiceSelectable={
                chosenFallback && phase.kind === "passive" && playerId === phase.player
              }
            />
          );
        })}
      </div>

      {phase.kind === "game-over" && (
        <ScoreTable scores={snap.scores} />
      )}
    </div>
  );
}

export default App;
