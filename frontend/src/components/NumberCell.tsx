interface NumberCellProps {
  id: string;
  label: string;
  value: string;
  onChange: (id: string, value: string) => void;
}

/**
 * A numeric input cell. The user may type, change or clear an integer.
 * An empty cell stays empty; it does not become zero automatically.
 */
function NumberCell({ id, label, value, onChange }: NumberCellProps) {
  return (
    <input
      id={id}
      className="number-cell"
      type="text"
      inputMode="numeric"
      pattern="-?[0-9]*"
      aria-label={label}
      value={value}
      onChange={(event) => {
        const next = event.target.value;
        // Allow empty, or an optional leading minus followed by digits only.
        if (next === "" || /^-?\d*$/.test(next)) {
          onChange(id, next);
        }
      }}
    />
  );
}

export default NumberCell;
