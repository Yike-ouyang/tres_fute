import { DIE_COLOR_OPTIONS, type DieColor } from "../boardData";

interface DieProps {
  color: DieColor;
  value: number | null;
  /** Render as a button that can be clicked (available die). */
  onClick?: () => void;
  selected?: boolean;
  disabled?: boolean;
  /** Optional element id (used for the round slots die-1/2/3). */
  id?: string;
  size?: "normal" | "small";
}

export function dieColorMeta(color: DieColor) {
  return DIE_COLOR_OPTIONS.find((c) => c.value === color)!;
}

/** Visual representation of a die with its permanent color and current value. */
function Die({ color, value, onClick, selected, disabled, id, size = "normal" }: DieProps) {
  const meta = dieColorMeta(color);
  const style = { background: meta.background, color: meta.text };
  const className = [
    "die",
    `die-${size}`,
    selected ? "is-selected" : "",
    disabled ? "is-disabled" : "",
    onClick ? "is-clickable" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const label = `Dé ${meta.label}${value !== null ? `, valeur ${value}` : ""}`;

  if (onClick) {
    return (
      <button
        id={id}
        type="button"
        className={className}
        style={style}
        onClick={onClick}
        disabled={disabled}
        aria-label={label}
        aria-pressed={selected}
      >
        {value ?? ""}
      </button>
    );
  }

  return (
    <div id={id} className={className} style={style} aria-label={label} role="img">
      {value ?? ""}
    </div>
  );
}

export default Die;
