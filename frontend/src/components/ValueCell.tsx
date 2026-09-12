interface ValueCellProps {
  id: string;
  label: string;
  /** Inscribed number, or undefined when the cell is still empty. */
  value?: number;
  /** Legal destination for the current selection (highlighted, clickable). */
  highlighted?: boolean;
  /** Provisionally picked as part of the current selection. */
  provisional?: boolean;
  /** Called when the cell is clicked as a legal destination. */
  onSelect?: (id: string) => void;
}

/**
 * A numeric board cell (blue / pink tracks). Numbers are inscribed automatically
 * by the game and cannot be edited or erased. Clicks only do something when the
 * cell is a highlighted legal destination.
 */
function ValueCell({
  id,
  label,
  value,
  highlighted = false,
  provisional = false,
  onSelect,
}: ValueCellProps) {
  const clickable = highlighted && !!onSelect;
  const className = [
    "value-cell",
    value !== undefined ? "is-filled" : "",
    highlighted ? "is-highlighted" : "",
    provisional ? "is-provisional" : "",
    clickable ? "" : "is-locked",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      id={id}
      type="button"
      aria-label={label}
      aria-disabled={!clickable}
      className={className}
      onClick={clickable ? () => onSelect(id) : undefined}
    >
      {value !== undefined ? value : ""}
    </button>
  );
}

export default ValueCell;
