interface FixedCellProps {
  id: string;
  label: string;
  value: number | string;
}

/** A fixed cell displaying a non-modifiable value. */
function FixedCell({ id, label, value }: FixedCellProps) {
  return (
    <div id={id} className="fixed-cell" aria-label={label} role="img">
      <span className="cell-number">{value}</span>
    </div>
  );
}

export default FixedCell;
