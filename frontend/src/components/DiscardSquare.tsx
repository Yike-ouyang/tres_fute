import Die from "./Die";
import { ALL_DIE_COLORS, type DieColor, type GameState } from "../game/types";

interface DiscardSquareProps {
  state: GameState;
  /** Dice are clickable (passive choice phase, awaiting a selection). */
  selectable: boolean;
  onSelectDie: (color: DieColor) => void;
}

/** The gray square holding dice set aside. During a passive choice the player
 * selects one die from here. */
function DiscardSquare({ state, selectable, onSelectDie }: DiscardSquareProps) {
  const discarded = ALL_DIE_COLORS.filter(
    (c) => state.dice[c].location === "discarded"
  );
  const selectedColor = state.selection?.color ?? null;

  return (
    <div className={`discard-square${selectable ? " is-selectable" : ""}`} aria-label="Carré gris des dés écartés">
      <span className="discard-label">Carré gris</span>
      <div className="discard-cells">
        {discarded.length === 0 && (
          <span className="dice-pool-empty">Vide</span>
        )}
        {discarded.map((color) => (
          <Die
            key={color}
            color={color}
            value={state.dice[color].value}
            size="small"
            selected={selectedColor === color}
            disabled={selectable ? false : undefined}
            onClick={selectable ? () => onSelectDie(color) : undefined}
          />
        ))}
      </div>
    </div>
  );
}

export default DiscardSquare;
