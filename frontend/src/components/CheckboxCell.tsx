interface CheckboxCellProps {
  id: string;
  label: string;
  checked: boolean;
  /** Optional pre-printed fixed number; stays visible and cannot be changed. */
  number?: number;
  /** Legal destination for the current selection (highlighted, clickable). */
  highlighted?: boolean;
  /** Provisionally picked as part of the current selection. */
  provisional?: boolean;
  /** Definitively inaccessible (e.g. brown cells to the left of the last check). */
  inaccessible?: boolean;
  /** Marks one of the six passive-yellow cells (grayed background on both boards). */
  passiveYellow?: boolean;
  /** Marks a dark turquoise cell (part of the triangle used for bonus unlocks). */
  dark?: boolean;
  /** Called when the cell is clicked as a legal destination. */
  onSelect?: (id: string) => void;
}

/**
 * A board checkbox cell. Once checked it stays checked (board is game-driven and
 * locked). A number, when present, stays visible under the check mark. Clicks only
 * do something when the cell is a highlighted legal destination.
 */
function CheckboxCell({
  id,
  label,
  checked,
  number,
  highlighted = false,
  provisional = false,
  inaccessible = false,
  passiveYellow = false,
  dark = false,
  onSelect,
}: CheckboxCellProps) {
  const clickable = highlighted && !!onSelect;
  const className = [
    "checkbox-cell",
    checked ? "is-checked" : "",
    highlighted ? "is-highlighted" : "",
    provisional ? "is-provisional" : "",
    inaccessible ? "is-inaccessible" : "",
    passiveYellow ? "is-passive-yellow" : "",
    dark ? "is-turquoise-dark" : "",
    clickable ? "" : "is-locked",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      id={id}
      type="button"
      role="checkbox"
      aria-checked={checked}
      aria-label={label}
      aria-disabled={!clickable}
      className={className}
      onClick={clickable ? () => onSelect(id) : undefined}
    >
      {number !== undefined && <span className="cell-number">{number}</span>}
      {(checked || provisional) && (
        <span className="cell-check" aria-hidden="true">
          ✓
        </span>
      )}
    </button>
  );
}

export default CheckboxCell;
