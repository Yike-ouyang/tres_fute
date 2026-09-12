import { DIE_COLOR_OPTIONS } from "../boardData";
import { ACTING_COLORS, type ActingColor } from "../game/types";

interface WhiteColorChooserProps {
  availability: Record<ActingColor, boolean>;
  selected: ActingColor | null;
  onChoose: (color: ActingColor) => void;
}

/**
 * Shown when the white die is selected: the player picks one of the five acting
 * colors. Colors with no legal move for the white value are disabled.
 */
function WhiteColorChooser({ availability, selected, onChoose }: WhiteColorChooserProps) {
  return (
    <div className="white-chooser" role="group" aria-label="Choix de couleur du dé blanc">
      <span className="white-chooser-label">Dé blanc — choisir une couleur :</span>
      <div className="white-chooser-options">
        {ACTING_COLORS.map((color) => {
          const meta = DIE_COLOR_OPTIONS.find((c) => c.value === color)!;
          const disabled = !availability[color];
          return (
            <button
              key={color}
              type="button"
              className={`white-chooser-option${selected === color ? " is-selected" : ""}`}
              style={{ background: meta.background, color: meta.text }}
              disabled={disabled}
              aria-disabled={disabled}
              onClick={() => onChoose(color)}
            >
              {meta.label}
              {disabled && <span className="white-chooser-na"> (indisponible)</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default WhiteColorChooser;
