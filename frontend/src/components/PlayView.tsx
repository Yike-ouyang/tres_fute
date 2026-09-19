import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import BoardView from "./BoardView";
import DicePool from "./DicePool";
import DiscardSquare from "./DiscardSquare";
import ScoreTable from "./ScoreTable";
import StatusBar from "./StatusBar";
import WhiteColorChooser from "./WhiteColorChooser";
import {
  cancelHumanSession,
  createHumanSession,
  deleteHumanSession,
  listHumanModels,
  saveHumanSession,
  stepHumanSession,
  type HumanLegalAction,
  type HumanModelEntry,
  type HumanPlayState,
} from "../api/humanPlay";
import {
  classifySelectDice,
  destinationActions,
  findCellAction,
  findDieAction,
  findFillAction,
  findTurquoiseAction,
  findByDetail,
  findWhiteColorAction,
  formatOpponent,
  isUniqueDestination,
  parseDetail,
  turquoiseColumn,
  turquoiseLegalCells,
  turquoiseShouldPlay,
  utilityActions,
} from "../game/playClicks";
import {
  ALL_DIE_COLORS,
  PLAYER_IDS,
  type ActingColor,
  type DiceLocation,
  type DieColor,
  type PlayerId,
} from "../game/types";

function destinationCellIds(legal: HumanLegalAction[]): Set<string> {
  const ids = new Set<string>();
  for (const action of destinationActions(legal)) {
    if (action.category === "dest_turquoise") continue;
    ids.add(parseDetail(action.detail).value);
  }
  for (const cell of turquoiseLegalCells(legal)) ids.add(cell);
  return ids;
}

interface PlayViewProps {
  mode: "human" | "ai";
  onOpenReplay: () => void;
}

function PlayView({ mode, onOpenReplay }: PlayViewProps) {
  const [seat, setSeat] = useState<PlayerId>(1);
  const [models, setModels] = useState<HumanModelEntry[]>([]);
  const [checkpoint, setCheckpoint] = useState<string>("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [state, setState] = useState<HumanPlayState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [slow, setSlow] = useState(false);
  const [savedId, setSavedId] = useState<string | null>(null);
  const [turquoiseRows, setTurquoiseRows] = useState<number[]>([]);
  const startedRef = useRef(false);

  const applyState = useCallback((next: HumanPlayState) => {
    setState(next);
    setTurquoiseRows([]);
  }, []);

  const withBusy = useCallback(
    async (task: () => Promise<void>) => {
      setBusy(true);
      setError(null);
      setSlow(false);
      const timer = window.setTimeout(() => setSlow(true), 100);
      try {
        await task();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Action refusée");
      } finally {
        window.clearTimeout(timer);
        setSlow(false);
        setBusy(false);
      }
    },
    []
  );

  const start = useCallback(
    async (seatChoice: PlayerId, modelPath?: string) => {
      setError(null);
      setSavedId(null);
      setBusy(true);
      try {
        const created = await createHumanSession({
          agent_player: seatChoice,
          opponent: mode === "ai" ? "ai" : "human",
          checkpoint: mode === "ai" ? modelPath || null : null,
        });
        setSessionId(created.session_id);
        applyState(created.state);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Serveur indisponible");
      } finally {
        setBusy(false);
      }
    },
    [mode, applyState]
  );

  useEffect(() => {
    if (mode === "human" && !startedRef.current) {
      startedRef.current = true;
      void start(1);
    }
  }, [mode, start]);

  useEffect(() => {
    if (mode !== "ai") return;
    let cancelled = false;
    listHumanModels()
      .then((list) => {
        if (cancelled) return;
        setModels(list);
        const preferred = list.find((m) => m.is_default) ?? list.find((m) => m.catalogue === "v2") ?? list[0];
        if (preferred) setCheckpoint(preferred.path);
      })
      .catch(() => {
        /* la sélection reste vide : le back prendra le défaut */
      });
    return () => {
      cancelled = true;
    };
  }, [mode]);

  const legal = state?.legal_actions ?? [];
  const utilitySet = useMemo(() => new Set(utilityActions(legal).map((a) => a.detail)), [legal]);
  const destCount = destinationActions(legal).length;
  const diceLocations = useMemo(() => {
    const map: Record<string, DiceLocation> = {};
    if (state) {
      for (const color of ALL_DIE_COLORS) map[color] = state.state.dice[color].location;
    }
    return map;
  }, [state]);
  const selectTargets = useMemo(
    () => classifySelectDice(legal, diceLocations),
    [legal, diceLocations]
  );
  const humanTurn = !!state?.human_turn;
  // Dé phase active → DicePool ; phase passive → carré gris (écartés) ;
  // fallback → dés placés dans les emplacements du joueur.
  const dieSelectable = humanTurn && selectTargets.available.length > 0;
  const discardSelectable =
    humanTurn &&
    (legal.some((a) => a.category === "fill_slot") || selectTargets.discarded.length > 0);
  const slotSelectable = humanTurn && selectTargets.chosen.length > 0;

  const onStep = useCallback(
    (actionId: number) => {
      if (!sessionId) return;
      void withBusy(async () => applyState(await stepHumanSession(sessionId, actionId)));
    },
    [sessionId, withBusy, applyState]
  );

  const onPlayDie = useCallback(
    (color: DieColor) => {
      if (!sessionId) return;
      const fill = findFillAction(legal, color);
      if (fill) {
        onStep(fill.id);
        return;
      }
      const die = findDieAction(legal, color);
      if (!die) return;
      void withBusy(async () => {
        const after = await stepHumanSession(sessionId, die.id);
        if (isUniqueDestination(after.legal_actions)) {
          const dest = destinationActions(after.legal_actions)[0];
          applyState(await stepHumanSession(sessionId, dest.id));
        } else {
          applyState(after);
        }
      });
    },
    [sessionId, legal, withBusy, applyState, onStep]
  );

  const onPlayCell = useCallback(
    (cellId: string) => {
      if (!sessionId || !state) return;
      const col = turquoiseColumn(legal);
      if (col !== null && cellId.startsWith("turquoise-")) {
        const match = /^turquoise-r(\d)-c(\d+)$/.exec(cellId);
        if (!match || Number(match[2]) !== col) return;
        const row = Number(match[1]);
        const rows = turquoiseRows.includes(row)
          ? turquoiseRows.filter((r) => r !== row)
          : [...turquoiseRows, row];
        setTurquoiseRows(rows);
        const maxPick = state.state.selection?.maxPick ?? 1;
        if (turquoiseShouldPlay(legal, rows, maxPick)) {
          const action = findTurquoiseAction(legal, rows);
          if (action) onStep(action.id);
        }
        return;
      }
      const action = findCellAction(legal, cellId);
      if (action) onStep(action.id);
    },
    [sessionId, state, legal, turquoiseRows, onStep]
  );

  const onUtility = useCallback(
    (name: string) => {
      const action = findByDetail(legal, name, "utility");
      if (action) onStep(action.id);
    },
    [legal, onStep]
  );

  const onCancel = useCallback(() => {
    if (turquoiseRows.length) {
      setTurquoiseRows([]);
      return;
    }
    if (!sessionId || !state) return;
    if (state.state.selection || state.awaiting_value) {
      void withBusy(async () => applyState(await cancelHumanSession(sessionId)));
    }
  }, [turquoiseRows, sessionId, state, withBusy, applyState]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);

  const onNewGame = useCallback(async () => {
    if (sessionId) {
      try {
        await deleteHumanSession(sessionId);
      } catch {
        /* ignore */
      }
    }
    await start(seat, checkpoint);
  }, [sessionId, seat, checkpoint, start]);

  const onSave = useCallback(() => {
    if (!sessionId) return;
    void withBusy(async () => {
      const result = await saveHumanSession(sessionId);
      setSavedId(result.replay_id);
      onOpenReplay();
    });
  }, [sessionId, withBusy, onOpenReplay]);

  if (mode === "ai" && !sessionId) {
    return (
      <section className="play-view">
        <h2 className="play-title">Play against AI</h2>
        <p className="play-muted">Choisissez votre siège et le modèle adverse :</p>
        <div className="play-seat">
          {PLAYER_IDS.map((p) => (
            <button
              key={p}
              type="button"
              className={`btn${seat === p ? " btn-primary" : ""}`}
              onClick={() => setSeat(p)}
            >
              Joueur {p}
            </button>
          ))}
        </div>
        <label className="play-model-select">
          Modèle :{" "}
          <select value={checkpoint} onChange={(e) => setCheckpoint(e.target.value)}>
            {models.length === 0 && <option value="">(défaut du serveur)</option>}
            {models.map((m) => (
              <option key={m.path} value={m.path}>
                {m.run}
                {m.subdir ? ` / ${m.subdir}` : ""} ({m.file}){m.is_default ? " — défaut" : ""}
              </option>
            ))}
          </select>
        </label>
        <button
          className="btn btn-primary"
          type="button"
          onClick={() => void start(seat, checkpoint)}
          disabled={busy}
        >
          {busy ? "Démarrage…" : "Démarrer la partie"}
        </button>
        {error && (
          <div className="game-message" role="alert">
            {error}
          </div>
        )}
      </section>
    );
  }

  if (!state) {
    return (
      <p className="game-message" role="status">
        {error ?? "Connexion au moteur de règles…"}
      </p>
    );
  }

  const game = state.state;
  const acting = state.acting_player;
  const player = (acting ?? state.human_player) as PlayerId;
  const playingBoard = player;
  const lastAi = state.last_ai_actions[state.last_ai_actions.length - 1];
  const canInteract = state.human_turn && !state.is_over && !busy;
  const legalCells = destinationCellIds(legal);
  const col = turquoiseColumn(legal);
  const picked = new Set(turquoiseRows.map((r) => `turquoise-r${r}-c${col}`));
  const whiteAvailability = state.whiteAvailability;

  return (
    <section className="play-view">
      <StatusBar
        globalTurn={game.globalTurn}
        phase={game.phase}
        actingPlayer={acting}
        humanTurn={state.human_turn && !state.is_over}
        player={player}
        board={game.boards[player]}
        utility={utilitySet}
        onUtility={onUtility}
      />

      <header className="play-header">
        <span className="play-banner">
          {state.is_over
            ? "Partie terminée"
            : state.human_turn
            ? mode === "ai"
              ? `À vous de jouer (Joueur ${state.human_player})`
              : `Tour du joueur ${acting}`
            : "L'IA réfléchit…"}
        </span>
        {mode === "ai" && (
          <span className="play-opponent">
            Adversaire : {state.opponent_name ?? formatOpponent(state.checkpoint)}
          </span>
        )}
        <span className="play-meta">
          {mode === "ai" ? "vs IA" : "hot-seat"} · seed {state.seed} · {state.human_decisions} décisions
        </span>
        <span className="play-actions">
          <button className="btn" type="button" onClick={() => void onNewGame()} disabled={busy}>
            Nouvelle partie
          </button>
          <button className="btn" type="button" onClick={onSave} disabled={busy}>
            Sauvegarder
          </button>
        </span>
      </header>

      {savedId && (
        <div className="game-message" role="status">
          Replay enregistré : {savedId}
        </div>
      )}
      {error && (
        <div className="game-message" role="alert">
          {error}
        </div>
      )}
      {mode === "ai" && lastAi && (
        <div className="play-ai-move">
          Coup IA : {lastAi.label ?? lastAi.kind}
        </div>
      )}
      {slow && <div className="play-slow">L'IA réfléchit…</div>}

      <section className="zone shared-dice" aria-label="Dés">
        <div className="shared-dice-row">
          <DicePool state={game} selectable={dieSelectable} onSelectDie={onPlayDie} />
          <DiscardSquare state={game} selectable={discardSelectable} onSelectDie={onPlayDie} />
        </div>

        {legal.some((a) => a.category === "white_color") && whiteAvailability && (
          <WhiteColorChooser
            availability={whiteAvailability}
            selected={game.selection?.actingColor ?? null}
            onChoose={(color: ActingColor) => {
              const action = findWhiteColorAction(legal, color);
              if (!action) return;
              if (!sessionId) return;
              void withBusy(async () => {
                const after = await stepHumanSession(sessionId, action.id);
                if (isUniqueDestination(after.legal_actions)) {
                  const dest = destinationActions(after.legal_actions)[0];
                  applyState(await stepHumanSession(sessionId, dest.id));
                } else {
                  applyState(after);
                }
              });
            }}
          />
        )}

        <div className="play-controls">
          {legal
            .filter((a) => a.category === "bonus_color")
            .map((a) => (
              <button key={a.id} type="button" className="btn btn-small" onClick={() => onStep(a.id)}>
                {parseDetail(a.detail).value}
              </button>
            ))}
          {legal
            .filter((a) => a.category === "bonus_value" || a.category === "joker_value")
            .map((a) => (
              <button key={a.id} type="button" className="btn btn-small" onClick={() => onStep(a.id)}>
                valeur {parseDetail(a.detail).value}
              </button>
            ))}
          {legal
            .filter((a) => a.category === "blue_bonus_cell")
            .map((a) => (
              <button key={a.id} type="button" className="btn btn-small" onClick={() => onStep(a.id)}>
                case {parseDetail(a.detail).value}
              </button>
            ))}
          {legal
            .filter((a) => a.category === "blue_bonus_value")
            .map((a) => (
              <button key={a.id} type="button" className="btn btn-small" onClick={() => onStep(a.id)}>
                {parseDetail(a.detail).value.replace("=", " → ")}
              </button>
            ))}
          {legal
            .filter((a) => a.category === "turquoise_bonus_row")
            .map((a) => (
              <button key={a.id} type="button" className="btn btn-small" onClick={() => onStep(a.id)}>
                ligne {parseDetail(a.detail).value}
              </button>
            ))}
          {legal
            .filter((a) => a.category === "turquoise_bonus_col")
            .map((a) => (
              <button key={a.id} type="button" className="btn btn-small" onClick={() => onStep(a.id)}>
                {parseDetail(a.detail).value}
              </button>
            ))}
          {legal
            .filter((a) => a.category === "pink_option")
            .map((a) => (
              <button key={a.id} type="button" className="btn btn-small" onClick={() => onStep(a.id)}>
                rose : {parseDetail(a.detail).value}
              </button>
            ))}
          {utilityActions(legal)
            .filter((a) => a.detail !== "use_relance" && a.detail !== "start_joker")
            .map((a) => (
              <button key={a.id} type="button" className="btn btn-small" onClick={() => onStep(a.id)}>
                {a.detail}
              </button>
            ))}
          {state.state.selection && (
            <button type="button" className="btn btn-small" onClick={onCancel} disabled={busy}>
              Annuler (Échap)
            </button>
          )}
        </div>
      </section>

      <div className="boards-row">
        {PLAYER_IDS.map((playerId) => (
          <BoardView
            key={playerId}
            playerId={playerId}
            board={game.boards[playerId]}
            score={state.scores[String(playerId) as "1" | "2"]}
            interactive={canInteract && playingBoard === playerId && destCount > 0}
            legal={playingBoard === playerId ? legalCells : new Set<string>()}
            picked={playingBoard === playerId ? picked : new Set<string>()}
            activeRound={
              game.phase.kind === "active" && game.phase.player === playerId ? game.phase.round : null
            }
            activeOwner={false}
            jokerPending={false}
            onSelect={onPlayCell}
            onRelance={() => onUtility("use_relance")}
            onJoker={() => onUtility("start_joker")}
            onSelectDie={onPlayDie}
            selectedDie={game.selection?.color ?? null}
            slotDiceSelectable={playingBoard === playerId && slotSelectable}
          />
        ))}
      </div>

      {state.is_over && (
        <>
          <p className="play-result">
            Score final — agent {state.final_scores?.agent} / adversaire {state.final_scores?.adversary}
          </p>
          <ScoreTable scores={state.scores} />
        </>
      )}
    </section>
  );
}

export default PlayView;
