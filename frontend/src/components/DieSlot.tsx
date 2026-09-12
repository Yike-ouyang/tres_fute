import {
  DIE_COLOR_OPTIONS,
  DIE_VALUES,
  type DieColor,
  type DieState,
} from "../boardData";

interface DieSlotProps {
  id: string;
  label: string;
  state: DieState;
  onValueChange: (id: string, value: number | "") => void;
  onColorChange: (id: string, color: DieColor | "") => void;
}

/**
 * A die slot: lets the user manually pick a value (1-6 or none) and a color.
 * The chosen color becomes the die background, with a contrasted digit.
 */
function DieSlot({ id, label, state, onValueChange, onColorChange }: DieSlotProps) {
  const colorOption = DIE_COLOR_OPTIONS.find((c) => c.value === state.color);
  const valueId = `${id}-value`;
  const colorId = `${id}-color`;

  const dieStyle = colorOption
    ? { background: colorOption.background, color: colorOption.text }
    : undefined;

  return (
    <div className="die-slot">
      <div className="die-slot-title">{label}</div>
      <div id={id} className="die-face" style={dieStyle} aria-label={`Dé ${label}`}>
        {state.value !== "" ? state.value : ""}
      </div>
      <div className="die-controls">
        <label className="die-control" htmlFor={valueId}>
          <span>Valeur</span>
          <select
            id={valueId}
            value={state.value === "" ? "" : String(state.value)}
            onChange={(event) => {
              const raw = event.target.value;
              onValueChange(id, raw === "" ? "" : Number(raw));
            }}
          >
            <option value="">—</option>
            {DIE_VALUES.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label className="die-control" htmlFor={colorId}>
          <span>Couleur</span>
          <select
            id={colorId}
            value={state.color}
            onChange={(event) =>
              onColorChange(id, event.target.value as DieColor | "")
            }
          >
            <option value="">—</option>
            {DIE_COLOR_OPTIONS.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </label>
      </div>
    </div>
  );
}

export default DieSlot;
