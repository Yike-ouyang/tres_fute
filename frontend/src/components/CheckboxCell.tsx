interface CheckboxCellProps {
  id: string;
  label: string;
  checked: boolean;
  onToggle: (id: string) => void;
  /** Optional pre-printed fixed number; stays visible and cannot be changed. */
  number?: number;
}

/**
 * A checkbox cell: one click checks it, another unchecks it.
 * If it carries a number, the number stays visible and unmodifiable.
 * A visible check mark is shown when checked, without hiding the number.
 */
function CheckboxCell({ id, label, checked, onToggle, number }: CheckboxCellProps) {
  return (
    <button
      id={id}
      type="button"
      role="checkbox"
      aria-checked={checked}
      aria-label={label}
      className={`checkbox-cell${checked ? " is-checked" : ""}`}
      onClick={() => onToggle(id)}
    >
      {number !== undefined && <span className="cell-number">{number}</span>}
      {checked && (
        <span className="cell-check" aria-hidden="true">
          ✓
        </span>
      )}
    </button>
  );
}

export default CheckboxCell;
