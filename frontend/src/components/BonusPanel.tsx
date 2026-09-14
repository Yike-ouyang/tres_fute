import { DIE_COLOR_OPTIONS } from "../boardData";
import { NUMBERED_JOKERS, TOTAL_PLUS1, jokerTokenLabel } from "../game/bonuses";
import { type BonusDieColor, type PlayerBoard } from "../game/types";

interface BonusPanelProps {
  board: PlayerBoard;
  /** This board belongs to the player who is currently the active player. */
  activeOwner: boolean;
  /** A joker is pending (awaiting a value or a die), so re-clicking is blocked. */
  jokerPending: boolean;
  onRelance: () => void;
  onJoker: () => void;
}

const DIE_BG: Record<string, string> = {
  ...Object.fromEntries(DIE_COLOR_OPTIONS.map((o) => [o.value, o.background])),
  black: "#20242c",
};
const DIE_FG: Record<string, string> = {
  ...Object.fromEntries(DIE_COLOR_OPTIONS.map((o) => [o.value, o.text])),
  black: "#ffffff",
};
/** Number of joker counter slots (3,4,5,6 then two wilds). */
const JOKER_SLOTS = NUMBERED_JOKERS + 2;

function remaining(t: { unlocked: number; used: number }): number {
  return Math.max(0, t.unlocked - t.used);
}

/** A small colored-square reward attached to the right end of a counter track. */
function CounterReward({
  color,
  unlocked,
  label,
}: {
  color: BonusDieColor;
  unlocked: boolean;
  label: string;
}) {
  return (
    <span
      className={`counter-reward${unlocked ? " is-unlocked" : ""}`}
      style={{ background: DIE_BG[color], color: DIE_FG[color] }}
      title={`${label}${unlocked ? " (débloqué)" : ""}`}
      aria-label={`${label}${unlocked ? ", débloqué" : ""}`}
    >
      <span className="counter-reward-glyph">▪</span>
      {unlocked && (
        <span className="bonus-slot-check" aria-hidden="true">
          ✓
        </span>
      )}
    </span>
  );
}

/** Bonus counters (relance / joker / +1), bonus-die tallies and active controls. */
function BonusPanel({ board, activeOwner, jokerPending, onRelance, onJoker }: BonusPanelProps) {
  const b = board.bonuses;
  const relanceLeft = remaining(b.relance);
  const jokerLeft = remaining(b.joker);
  const plus1Left = remaining(b.plus1);
  const nextJoker = jokerTokenLabel(b.joker.used);

  const jokerRewardUnlocked = !!b.slotsUnlocked["counter-joker-all"];
  const plus1RewardUnlocked = !!b.slotsUnlocked["counter-plus1-all"];

  return (
    <section className="zone zone-bonus" aria-label="Bonus">
      <h3 className="zone-title">Bonus</h3>

      <div className="bonus-counters">
        {/* Relance : représenté par un cercle */}
        <div className="bonus-counter">
          <span className="bonus-counter-label">
            <span className="relance-token" aria-hidden="true">
              ↻
            </span>
            Relance
          </span>
          <span className="bonus-counter-tally">
            {relanceLeft} dispo. / {b.relance.unlocked} débloqué(s)
          </span>
          <button
            type="button"
            className="btn btn-small"
            disabled={!activeOwner || relanceLeft <= 0}
            onClick={onRelance}
          >
            Relancer
          </button>
        </div>

        {/* Joker chiffre : piste de dés 3,4,5,6,?,? + récompense marron à droite */}
        <div className="bonus-counter">
          <span className="bonus-counter-label">Joker</span>
          <div className="counter-track" aria-label="Compteur de jokers">
            {Array.from({ length: JOKER_SLOTS }, (_, i) => {
              const filled = i < b.joker.unlocked;
              return (
                <span
                  key={i}
                  className={`counter-slot counter-slot-joker${filled ? " is-filled" : ""}`}
                  title={`Joker ${jokerTokenLabel(i)}${filled ? " (débloqué)" : ""}`}
                >
                  {jokerTokenLabel(i)}
                </span>
              );
            })}
            <CounterReward
              color="brown"
              unlocked={jokerRewardUnlocked}
              label="Dé bonus marron (tous les jokers)"
            />
          </div>
          <button
            type="button"
            className="btn btn-small"
            disabled={!activeOwner || jokerLeft <= 0 || jokerPending}
            onClick={onJoker}
          >
            Joker ({nextJoker})
          </button>
        </div>

        {/* +1 : piste de +1 + récompense rose à droite */}
        <div className="bonus-counter">
          <span className="bonus-counter-label">+1</span>
          <div className="counter-track" aria-label="Compteur de +1">
            {Array.from({ length: TOTAL_PLUS1 }, (_, i) => {
              const filled = i < b.plus1.unlocked;
              return (
                <span
                  key={i}
                  className={`counter-slot counter-slot-plus1${filled ? " is-filled" : ""}`}
                  title={`+1${filled ? " (débloqué)" : ""}`}
                >
                  +1
                </span>
              );
            })}
            <CounterReward
              color="pink"
              unlocked={plus1RewardUnlocked}
              label="Dé bonus rose (tous les +1)"
            />
          </div>
          <span className="bonus-counter-tally">
            {plus1Left} dispo. / {b.plus1.unlocked} débloqué(s)
          </span>
        </div>
      </div>
    </section>
  );
}

export default BonusPanel;
