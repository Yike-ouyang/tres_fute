import { useEffect, useMemo, useState } from "react";
import BoardView from "./BoardView";
import DicePool from "./DicePool";
import DiscardSquare from "./DiscardSquare";
import ReplayControls from "./ReplayControls";
import ReplaySummaryPanel from "./ReplaySummaryPanel";
import ScoreTable from "./ScoreTable";
import { getReplay, listReplays, type ReplayManifestEntry, type ReplayTrace } from "../api/replays";
import { frameAt, nextAgentIndex, prevAgentIndex } from "../replayNav";
import { PLAYER_IDS, type PlayerScore } from "../game/types";

const EMPTY_SET = new Set<string>();

const ZERO_SCORE: PlayerScore = {
  yellow: 0,
  turquoise: 0,
  blue: 0,
  brown: 0,
  pink: 0,
  colorSubtotal: 0,
  foxCount: 0,
  foxValue: 0,
  foxPoints: 0,
  total: 0,
};

const ZERO_SCORES: Record<"1" | "2", PlayerScore> = { "1": ZERO_SCORE, "2": ZERO_SCORE };

function ReplayView() {
  const [replays, setReplays] = useState<ReplayManifestEntry[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [trace, setTrace] = useState<ReplayTrace | null>(null);
  const [index, setIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listReplays()
      .then((list) => {
        if (cancelled) return;
        setReplays(list);
        setSelectedId((current) => current ?? list[0]?.id ?? null);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Replays indisponibles");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    setLoading(true);
    getReplay(selectedId)
      .then((data) => {
        if (cancelled) return;
        setTrace(data);
        setIndex(0);
        setError(null);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Replay introuvable");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const frames = trace?.frames ?? [];
  const total = frames.length;

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "ArrowRight") setIndex((i) => Math.min(total, i + 1));
      else if (event.key === "ArrowLeft") setIndex((i) => Math.max(0, i - 1));
      else if (event.key === "Home") setIndex(0);
      else if (event.key === "End") setIndex(total);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [total]);

  const frame = useMemo(() => frameAt(index, frames), [index, frames]);
  const state = index === 0 ? trace?.initial_state ?? null : frames[index - 1]?.state ?? null;
  const scores = index === 0 ? ZERO_SCORES : frames[index - 1]?.scores ?? ZERO_SCORES;
  const atEnd = total > 0 && index >= total;

  if (error) {
    return <p className="game-message" role="alert">{error}</p>;
  }
  if (replays.length === 0) {
    return (
      <p className="game-message" role="status">
        Aucun replay disponible. Générer une partie avec :{" "}
        <code>python rl_env/replay.py --seed 1000000 --agent-player 1</code>
      </p>
    );
  }

  return (
    <section className="replay-view" aria-label="Visionneuse de partie">
      <header className="replay-header">
        <label>
          Replay :{" "}
          <select value={selectedId ?? ""} onChange={(e) => setSelectedId(e.target.value)}>
            {replays.map((entry) => (
              <option key={entry.id} value={entry.id}>
                {entry.run} · {entry.checkpoint} · graine {entry.seed} · P{entry.agent_player}
                {entry.result ? ` · ${entry.result}` : ""}
              </option>
            ))}
          </select>
        </label>
        {trace && (
          <span className="replay-meta">
            graine {trace.seed} · agent = joueur {trace.agent_player} · {trace.agent_decisions} décisions
            {trace.final_scores
              ? ` · agent ${trace.final_scores.agent} – adversaire ${trace.final_scores.adversary}`
              : ""}
          </span>
        )}
        {loading && <span className="replay-meta">chargement…</span>}
      </header>

      <ReplayControls
        index={index}
        total={total}
        onFirst={() => setIndex(0)}
        onPrev={() => setIndex((i) => Math.max(0, i - 1))}
        onNext={() => setIndex((i) => Math.min(total, i + 1))}
        onLast={() => setIndex(total)}
        onPrevDecision={() => setIndex((i) => prevAgentIndex(i, frames))}
        onNextDecision={() => setIndex((i) => nextAgentIndex(i, frames))}
        onIndex={(i) => setIndex(i)}
      />

      <ReplaySummaryPanel frame={frame} atStart={index === 0} />

      {state && (
        <>
          <section className="zone shared-dice" aria-label="Dés de la partie rejouée">
            <div className="shared-dice-row">
              <DicePool state={state} selectable={false} onSelectDie={() => {}} />
              <DiscardSquare state={state} selectable={false} onSelectDie={() => {}} />
            </div>
          </section>

          <div className="boards-row">
            {PLAYER_IDS.map((playerId) => (
              <BoardView
                key={playerId}
                playerId={playerId}
                board={state.boards[playerId]}
                score={scores[String(playerId) as "1" | "2"]}
                interactive={false}
                legal={EMPTY_SET}
                picked={EMPTY_SET}
                activeRound={
                  state.phase.kind === "active" && state.phase.player === playerId
                    ? state.phase.round
                    : null
                }
                activeOwner={false}
                jokerPending={false}
                onSelect={() => {}}
                onRelance={() => {}}
                onJoker={() => {}}
                selectedDie={state.selection?.color ?? null}
              />
            ))}
          </div>

          {atEnd && <ScoreTable scores={scores} />}
        </>
      )}
    </section>
  );
}

export default ReplayView;
