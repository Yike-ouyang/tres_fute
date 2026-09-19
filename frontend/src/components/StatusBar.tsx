import { formatBonusTally } from "../game/playClicks";
import type { Phase, PlayerBoard, PlayerId } from "../game/types";

interface StatusBarProps {
  globalTurn: number;
  phase: Phase;
  actingPlayer: PlayerId | null;
  humanTurn: boolean;
  player: PlayerId;
  board: PlayerBoard;
  /** Noms d'utilitaires légaux (ex. "use_relance") -> contre cliquable. */
  utility: Set<string>;
  onUtility: (name: string) => void;
}

function phaseLabel(phase: Phase): string {
  switch (phase.kind) {
    case "active":
      return `active — manche ${phase.round}`;
    case "passive":
      return phase.done ? "passive (terminée)" : "passive";
    case "plus1":
      return "+1";
    case "fill-slots":
      return "remplissage";
    case "game-over":
      return "partie terminée";
  }
}

function BonusCounter({
  label,
  unlocked,
  used,
  action,
  utility,
  active,
  onUtility,
}: {
  label: string;
  unlocked: number;
  used: number;
  action: string;
  utility: Set<string>;
  active: boolean;
  onUtility: (name: string) => void;
}) {
  const available = Math.max(0, unlocked - used);
  const clickable = active && available > 0 && utility.has(action);
  return (
    <button
      type="button"
      className={`bonus-counter${available === 0 ? " is-empty" : ""}${clickable ? " is-clickable" : ""}`}
      title={`${label} : ${available} disponible(s) / ${unlocked}`}
      disabled={!clickable}
      onClick={clickable ? () => onUtility(action) : undefined}
    >
      <span className="bonus-counter-label">{label}</span>
      <span className="bonus-counter-value">{formatBonusTally(unlocked, used)}</span>
    </button>
  );
}

/** Bandeau haut : tour + compteurs de bonus du joueur concerné (dispo/total). */
function StatusBar({
  globalTurn,
  phase,
  actingPlayer,
  humanTurn,
  player,
  board,
  utility,
  onUtility,
}: StatusBarProps) {
  const bonuses = board.bonuses;
  return (
    <header className="status-bar">
      <div className="status-turn">
        <span className="status-turn-number">Tour {globalTurn}</span>
        <span className="status-turn-phase">{phaseLabel(phase)}</span>
        {actingPlayer && (
          <span className="status-turn-actor">
            {humanTurn ? `Joueur ${actingPlayer}` : `Joueur ${actingPlayer} (IA)`}
          </span>
        )}
      </div>
      <div className="status-bonuses" role="group" aria-label={`Bonus du joueur ${player}`}>
        <BonusCounter
          label="Relances"
          unlocked={bonuses.relance.unlocked}
          used={bonuses.relance.used}
          action="use_relance"
          utility={utility}
          active={humanTurn}
          onUtility={onUtility}
        />
        <BonusCounter
          label="Jokers"
          unlocked={bonuses.joker.unlocked}
          used={bonuses.joker.used}
          action="start_joker"
          utility={utility}
          active={humanTurn}
          onUtility={onUtility}
        />
        <BonusCounter
          label="+1"
          unlocked={bonuses.plus1.unlocked}
          used={bonuses.plus1.used}
          action="begin_plus1"
          utility={utility}
          active={humanTurn}
          onUtility={onUtility}
        />
      </div>
    </header>
  );
}

export default StatusBar;
