import type { ReplayFrame } from "../api/replays";

interface ReplaySummaryPanelProps {
  frame: ReplayFrame | null;
  atStart: boolean;
}

const DIE_COLOR_LABEL: Record<string, string> = {
  yellow: "jaune",
  turquoise: "turquoise",
  darkblue: "bleu foncé",
  brown: "marron",
  pink: "rose",
  white: "blanc",
};

const ROLE_LABEL: Record<ReplayFrame["role"], string> = {
  agent: "Agent (RL)",
  opponent: "Adversaire (heuristique)",
  auto: "Automatique / forcé",
};

const LOCATION_LABEL: Record<string, string> = {
  available: "disponible",
  chosen: "choisi",
  discarded: "écarté",
};

const BONUS_COLOR_LABEL: Record<string, string> = {
  yellow: "jaune",
  turquoise: "turquoise",
  darkblue: "bleu foncé",
  brown: "marron",
  pink: "rose",
  black: "noir",
};

/** Current action + the human-readable summary of the observation the agent saw. */
function ReplaySummaryPanel({ frame, atStart }: ReplaySummaryPanelProps) {
  if (atStart || !frame) {
    return (
      <section className="replay-summary" aria-label="État initial">
        <p className="replay-summary-start">
          État initial — utilisez ▶ pour avancer dans les {""}
          décisions et coups joués.
        </p>
      </section>
    );
  }

  const summary = frame.observation_summary;
  const actionLabel = frame.rl?.label ?? JSON.stringify(frame.action);

  return (
    <section className="replay-summary" aria-label="Détail du coup courant">
      <header className="replay-summary-header">
        <span className={`replay-role replay-role-${frame.role}`}>{ROLE_LABEL[frame.role]}</span>
        <span className="replay-actor">
          {frame.actor ? `Joueur ${frame.actor}` : "—"} · {frame.decision_kind}
        </span>
        <span className="replay-seq">étape {frame.index + 1}</span>
      </header>

      <div className="replay-action">
        <strong>Action :</strong> {actionLabel}
        {frame.rl && <code className="replay-rl-id">#{frame.rl.id}</code>}
      </div>

      {frame.message && <div className="replay-message">{frame.message}</div>}

      {summary && (
        <details className="replay-observation" open>
          <summary>Observation de l’agent (résumé)</summary>
          <div className="replay-obs-grid">
            <div>
              <h4>Contexte</h4>
              <ul className="replay-kv">
                <li>
                  <span>Tour / manche</span>
                  <b>
                    {summary.turn} / {summary.round || "—"}
                  </b>
                </li>
                <li>
                  <span>Phase</span>
                  <b>{summary.phase}</b>
                </li>
                <li>
                  <span>Décision</span>
                  <b>{summary.decision}</b>
                </li>
                <li>
                  <span>À qui</span>
                  <b>{summary.actor === "agent" ? "agent" : "adversaire"}</b>
                </li>
              </ul>
            </div>

            <div>
              <h4>Scores (vus par l’agent)</h4>
              <ul className="replay-kv">
                <li>
                  <span>Agent</span>
                  <b>{summary.scores.agent}</b>
                </li>
                <li>
                  <span>Adversaire</span>
                  <b>{summary.scores.adversary}</b>
                </li>
                <li>
                  <span>Renards</span>
                  <b>
                    {summary.fox_count.agent} / {summary.fox_count.adversary}
                  </b>
                </li>
              </ul>
            </div>

            <div>
              <h4>Dés</h4>
              <ul className="replay-dice">
                {summary.dice.map((die) => (
                  <li key={die.color} className={die.color === summary.selected_die ? "is-selected" : ""}>
                    <b>{DIE_COLOR_LABEL[die.color] ?? die.color}</b>{" "}
                    {die.value}
                    {die.joker_value !== null && <em> (joker {die.joker_value})</em>}
                    <span className="replay-die-loc">{LOCATION_LABEL[die.location]}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h4>Sélection en cours</h4>
              {summary.selection ? (
                <ul className="replay-kv">
                  <li>
                    <span>Dé / couleur</span>
                    <b>
                      {summary.selection.color ?? "—"} / {summary.selection.acting_color ?? "—"}
                    </b>
                  </li>
                  <li>
                    <span>Valeur</span>
                    <b>{summary.selection.value}</b>
                  </li>
                  <li>
                    <span>Cases</span>
                    <b>
                      {summary.selection.picked_cells} cochée(s) / {summary.selection.legal_cells} légale(s)
                    </b>
                  </li>
                </ul>
              ) : (
                <p className="replay-muted">Aucune sélection ouverte.</p>
              )}
            </div>

            <div>
              <h4>Ressources (agent / adversaire)</h4>
              <ul className="replay-kv">
                {(["relance", "joker", "plus1"] as const).map((bonus) => (
                  <li key={bonus}>
                    <span>{bonus}</span>
                    <b>
                      {summary.bonuses.agent[bonus].used}/{summary.bonuses.agent[bonus].unlocked} ·{" "}
                      {summary.bonuses.adversary[bonus].used}/{summary.bonuses.adversary[bonus].unlocked}
                    </b>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h4>File de bonus</h4>
              {summary.pending_bonuses.length === 0 ? (
                <p className="replay-muted">Vide.</p>
              ) : (
                <ol className="replay-pending">
                  {summary.pending_bonuses.map((bonus, i) => (
                    <li key={i}>
                      {bonus.owner === "agent" ? "agent" : "adversaire"} ·{" "}
                      {BONUS_COLOR_LABEL[bonus.color] ?? bonus.color}
                    </li>
                  ))}
                </ol>
              )}
            </div>
          </div>
        </details>
      )}

      {frame.legal_actions && frame.legal_actions.length > 0 && (
        <details className="replay-legal">
          <summary>
            Actions légales à cette décision ({frame.legal_actions.length})
          </summary>
          <ul className="replay-legal-list">
            {frame.legal_actions.map((action) => (
              <li key={action.id} className={frame.rl?.id === action.id ? "is-chosen" : ""}>
                <code>#{action.id}</code> {action.label}
                {frame.rl?.id === action.id && <b> ← choisi</b>}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

export default ReplaySummaryPanel;
