interface ReplayControlsProps {
  index: number;
  total: number;
  onFirst: () => void;
  onPrev: () => void;
  onNext: () => void;
  onLast: () => void;
  onPrevDecision: () => void;
  onNextDecision: () => void;
  onIndex: (index: number) => void;
}

/** Read-only scrubbing controls: arrows, decision jumps and a slider. */
function ReplayControls({
  index,
  total,
  onFirst,
  onPrev,
  onNext,
  onLast,
  onPrevDecision,
  onNextDecision,
  onIndex,
}: ReplayControlsProps) {
  const atStart = index <= 0;
  const atEnd = index >= total;
  return (
    <div className="replay-controls" role="group" aria-label="Navigation dans la partie rejouée">
      <div className="replay-buttons">
        <button type="button" className="btn" onClick={onFirst} disabled={atStart} aria-label="Début">
          ⏮
        </button>
        <button type="button" className="btn" onClick={onPrevDecision} disabled={atStart} aria-label="Décision précédente">
          ⏪ décision
        </button>
        <button type="button" className="btn" onClick={onPrev} disabled={atStart} aria-label="Étape précédente">
          ◀
        </button>
        <button type="button" className="btn" onClick={onNext} disabled={atEnd} aria-label="Étape suivante">
          ▶
        </button>
        <button type="button" className="btn" onClick={onNextDecision} disabled={atEnd} aria-label="Décision suivante">
          décision ⏩
        </button>
        <button type="button" className="btn" onClick={onLast} disabled={atEnd} aria-label="Fin">
          ⏭
        </button>
      </div>
      <input
        className="replay-slider"
        type="range"
        min={0}
        max={total}
        step={1}
        value={index}
        onChange={(e) => onIndex(Number(e.target.value))}
        aria-label="Position dans la partie"
      />
      <span className="replay-counter" aria-live="polite">
        {index} / {total}
      </span>
    </div>
  );
}

export default ReplayControls;
