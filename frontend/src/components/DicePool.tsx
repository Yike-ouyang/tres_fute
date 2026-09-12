import Die from "./Die";
import { ALL_DIE_COLORS, type DieColor, type GameState } from "../game/types";

interface DicePoolProps {
  state: GameState;
  /** Dice are clickable (active phase, awaiting a selection). */
  selectable: boolean;
  onSelectDie: (color: DieColor) => void;
}

/** The dice still available this round. Clicking one starts an active selection. */
function DicePool({ state, selectable, onSelectDie }: DicePoolProps) {
  const available = ALL_DIE_COLORS.filter(
    (c) => state.dice[c].location === "available"
  );
  const selectedColor = state.selection?.color ?? null;

  return (
    <div className="dice-pool" aria-label="Dés disponibles">
      <span className="dice-pool-label">Dés disponibles</span>
      <div className="dice-pool-row">
        {available.length === 0 && (
          <span className="dice-pool-empty">Aucun dé disponible</span>
        )}
        {available.map((color) => (
          <Die
            key={color}
            color={color}
            value={state.dice[color].value}
            selected={selectedColor === color}
            disabled={!selectable}
            onClick={selectable ? () => onSelectDie(color) : undefined}
          />
        ))}
      </div>
    </div>
  );
}

export default DicePool;
