import Die, { dieColorMeta } from "./Die";
import type { ChosenDie, DieColor } from "../game/types";

interface DieSlotProps {
  /** Slot element id: e.g. p1-die-1. */
  id: string;
  /** Roman label I, II, III. */
  label: string;
  /** The die placed in this slot, or null when still empty. */
  slot: ChosenDie | null;
  /** True when this slot corresponds to the current active round. */
  active: boolean;
  selected?: boolean;
  /** When set, the placed die can be clicked (passive fallback to active dice). */
  onSelectDie?: (color: DieColor) => void;
}

/**
 * A round slot. Game-driven: it displays the die validated during that round
 * (die-1, die-2, die-3). The player never edits it manually.
 */
function DieSlot({ id, label, slot, active, selected, onSelectDie }: DieSlotProps) {
  return (
    <div className={`die-slot${active ? " is-active" : ""}`}>
      <div className="die-slot-title">{label}</div>
      {slot ? (
        <Die
          id={id}
          color={slot.color}
          value={slot.value}
          selected={selected}
          onClick={onSelectDie ? () => onSelectDie(slot.color) : undefined}
        />
      ) : (
        <div id={id} className="die-face-empty" aria-label={`Emplacement ${label} vide`} />
      )}
      {slot && <span className="die-slot-caption">{dieColorMeta(slot.color).label}</span>}
    </div>
  );
}

export default DieSlot;
