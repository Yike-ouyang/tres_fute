import type { Phase, PlayerId } from "../game/types";

interface GameControlsProps {
  globalTurn: number;
  phase: Phase;
  message: string | null;
  canValidate: boolean;
  hasSelection: boolean;
  stuck: boolean;
  /** The player currently making a +1 replay (null during the choose step). */
  plus1Active: PlayerId | null;
  /** Whether the current +1-window actor still has a +1 to use. */
  canUsePlus1: boolean;
  /** An immediate bonus / pink dialog is open: hide the normal action buttons. */
  overlayActive?: boolean;
  onValidate: () => void;
  onCancel: () => void;
  onEndTurn: () => void;
  onPass: () => void;
  onContinue: () => void;
  onPlus1Use: () => void;
  onPlus1Skip: () => void;
  onReset: () => void;
}

function phaseLabel(phase: Phase): string {
  switch (phase.kind) {
    case "active":
      return `Joueur ${phase.player} actif — Manche active ${phase.round} / 3`;
    case "passive":
      return phase.done
        ? `Joueur ${phase.player} — choix passif terminé`
        : `Joueur ${phase.player} — choix passif`;
    case "plus1":
      return `Fenêtre +1 — Joueur ${phase.order[phase.current]}`;
    case "game-over":
      return "Partie terminée";
  }
}

function actingPlayer(phase: Phase): number | null {
  if (phase.kind === "active") return phase.player;
  if (phase.kind === "passive" && !phase.done) return phase.player;
  if (phase.kind === "plus1") return phase.order[phase.current];
  return null;
}

/** Status bar: global turn, active/acting player, phase and the action buttons. */
function GameControls({
  globalTurn,
  phase,
  message,
  canValidate,
  hasSelection,
  stuck,
  plus1Active,
  canUsePlus1,
  overlayActive = false,
  onValidate,
  onCancel,
  onEndTurn,
  onPass,
  onContinue,
  onPlus1Use,
  onPlus1Skip,
  onReset,
}: GameControlsProps) {
  const acting = actingPlayer(phase);
  const isGameOver = phase.kind === "game-over";
  const isActive = phase.kind === "active" && !overlayActive;
  const isPassiveOpen = phase.kind === "passive" && !phase.done && !overlayActive;
  const isPassiveDone = phase.kind === "passive" && phase.done && !overlayActive;
  const isPlus1Choosing =
    phase.kind === "plus1" && plus1Active === null && !overlayActive;

  return (
    <section className="game-controls" aria-label="Contrôles de jeu">
      <div className="game-status" aria-live="polite">
        {isGameOver ? (
          <strong className="status-over">Partie terminée</strong>
        ) : (
          <>
            <span className="status-turn">
              Tour global <strong>{globalTurn}</strong> / 6
            </span>
            <span className="status-phase">{phaseLabel(phase)}</span>
            {acting !== null && (
              <span className="status-acting">Doit agir : Joueur {acting}</span>
            )}
          </>
        )}
      </div>

      <div className="game-buttons">
        {!isGameOver && hasSelection && (
          <>
            <button
              type="button"
              className="btn btn-primary"
              onClick={onValidate}
              disabled={!canValidate}
            >
              Valider
            </button>
            <button type="button" className="btn" onClick={onCancel}>
              Annuler
            </button>
          </>
        )}
        {isActive && stuck && (
          <button type="button" className="btn btn-warn" onClick={onEndTurn}>
            Terminer le tour
          </button>
        )}
        {isPassiveOpen && stuck && (
          <button type="button" className="btn btn-warn" onClick={onPass}>
            Passer
          </button>
        )}
        {isPassiveDone && (
          <button type="button" className="btn btn-primary" onClick={onContinue}>
            Continuer
          </button>
        )}
        {isPlus1Choosing && (
          <>
            <button
              type="button"
              className="btn btn-primary"
              onClick={onPlus1Use}
              disabled={!canUsePlus1}
            >
              Utiliser +1
            </button>
            <button type="button" className="btn" onClick={onPlus1Skip}>
              Passer le +1
            </button>
          </>
        )}
        <button type="button" className="btn btn-reset" onClick={onReset}>
          Réinitialiser la partie
        </button>
      </div>

      {message && (
        <div className="game-message" role="status" aria-live="polite">
          {message}
        </div>
      )}
    </section>
  );
}

export default GameControls;
