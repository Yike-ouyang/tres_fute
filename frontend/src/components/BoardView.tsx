import CheckboxCell from "./CheckboxCell";
import ValueCell from "./ValueCell";
import FixedCell from "./FixedCell";
import DieSlot from "./DieSlot";
import {
  BLUE_CENTER_INDEX,
  BLUE_CENTER_VALUE,
  BROWN_NUMBERS,
  DIE_LABELS,
  ROW_NUMBERS,
} from "../boardData";
import { PASSIVE_YELLOW_CELLS } from "../game/rules";
import type { PlayerBoard, PlayerId } from "../game/types";

const PASSIVE_YELLOW_SET = new Set(PASSIVE_YELLOW_CELLS);
const BONUS_LABELS = ["Relance", "Joker", "+1"];

interface BoardViewProps {
  playerId: PlayerId;
  board: PlayerBoard;
  /** True when this board is the one that must act. */
  interactive: boolean;
  /** Legal / provisional cell ids (unprefixed) for the current selection. */
  legal: Set<string>;
  picked: Set<string>;
  /** Active round to highlight in the slots, or null when not this player's active phase. */
  activeRound: number | null;
  /** Called with the unprefixed cell id when a legal destination is clicked. */
  onSelect: (cellId: string) => void;
}

function range(count: number): number[] {
  return Array.from({ length: count }, (_, i) => i + 1);
}

/** Renders one player's full board. DOM ids are prefixed with p1-/p2-. */
function BoardView({
  playerId,
  board,
  interactive,
  legal,
  picked,
  activeRound,
  onSelect,
}: BoardViewProps) {
  const prefix = `p${playerId}-`;

  const cellProps = (id: string) => ({
    highlighted: interactive && legal.has(id),
    provisional: interactive && picked.has(id),
    onSelect: interactive ? onSelect : undefined,
  });

  return (
    <div className={`board-view${interactive ? " is-interactive" : ""}`}>
      <h2 className="board-view-title">
        Joueur {playerId} {interactive && <span className="acting-badge">à vous de jouer</span>}
      </h2>

      {/* Barre de suivi des tours */}
      <section className="zone zone-turns" aria-label={`Joueur ${playerId} tours`}>
        <h3 className="zone-title">Tours</h3>
        <div className="turn-bar">
          {range(6).map((n) => {
            const id = `turn-${n}`;
            return (
              <CheckboxCell
                key={id}
                id={`${prefix}${id}`}
                label={`Joueur ${playerId}, tour ${n}`}
                number={n}
                checked={!!board.checks[id]}
              />
            );
          })}
        </div>
      </section>

      {/* Emplacements de dés du joueur */}
      <section className="zone zone-dice" aria-label={`Joueur ${playerId} emplacements de dés`}>
        <h3 className="zone-title">Emplacements de dés</h3>
        <div className="dice-slots">
          {range(3).map((n) => (
            <DieSlot
              key={n}
              id={`${prefix}die-${n}`}
              label={DIE_LABELS[n - 1]}
              slot={board.slots[n - 1]}
              active={activeRound === n}
            />
          ))}
        </div>
      </section>

      {/* Zone jaune */}
      <section className="zone zone-yellow" aria-label={`Joueur ${playerId} zone jaune`}>
        <h3 className="zone-title">Zone jaune</h3>
        <div className="grid grid-6col">
          {range(3).map((r) =>
            ROW_NUMBERS.map((num, c) => {
              const col = c + 1;
              const id = `yellow-r${r}-c${col}`;
              return (
                <CheckboxCell
                  key={id}
                  id={`${prefix}${id}`}
                  label={`Joueur ${playerId}, jaune ligne ${r} colonne ${col}, nombre ${num}`}
                  number={num}
                  checked={!!board.checks[id]}
                  passiveYellow={PASSIVE_YELLOW_SET.has(id)}
                  {...cellProps(id)}
                />
              );
            })
          )}
        </div>
      </section>

      {/* Zone turquoise */}
      <section className="zone zone-turquoise" aria-label={`Joueur ${playerId} zone turquoise`}>
        <h3 className="zone-title">Zone turquoise</h3>
        <div className="grid grid-6col">
          {range(6).map((r) =>
            ROW_NUMBERS.map((num, c) => {
              const col = c + 1;
              const id = `turquoise-r${r}-c${col}`;
              return (
                <CheckboxCell
                  key={id}
                  id={`${prefix}${id}`}
                  label={`Joueur ${playerId}, turquoise ligne ${r} colonne ${col}, nombre ${num}`}
                  number={num}
                  checked={!!board.checks[id]}
                  {...cellProps(id)}
                />
              );
            })
          )}
        </div>
      </section>

      {/* Piste bleu foncé */}
      <section className="zone zone-blue" aria-label={`Joueur ${playerId} piste bleu foncé`}>
        <h3 className="zone-title">Piste bleu foncé</h3>
        <div className="track">
          {range(11).map((n) => {
            const id = `blue-cell-${n}`;
            if (n === BLUE_CENTER_INDEX) {
              return (
                <FixedCell
                  key={id}
                  id={`${prefix}${id}`}
                  label={`Joueur ${playerId}, bleu case ${n}, valeur fixe ${BLUE_CENTER_VALUE}`}
                  value={BLUE_CENTER_VALUE}
                />
              );
            }
            return (
              <ValueCell
                key={id}
                id={`${prefix}${id}`}
                label={`Joueur ${playerId}, bleu case ${n}`}
                value={board.values[id]}
                {...cellProps(id)}
              />
            );
          })}
        </div>
      </section>

      {/* Piste marron */}
      <section className="zone zone-brown" aria-label={`Joueur ${playerId} piste marron`}>
        <h3 className="zone-title">Piste marron</h3>
        <div className="track">
          {BROWN_NUMBERS.map((num, i) => {
            const n = i + 1;
            const id = `brown-cell-${n}`;
            return (
              <CheckboxCell
                key={id}
                id={`${prefix}${id}`}
                label={`Joueur ${playerId}, marron case ${n}, nombre ${num}`}
                number={num}
                checked={!!board.checks[id]}
                inaccessible={!!board.brownDisabled[id]}
                {...cellProps(id)}
              />
            );
          })}
        </div>
      </section>

      {/* Piste rose */}
      <section className="zone zone-pink" aria-label={`Joueur ${playerId} piste rose`}>
        <h3 className="zone-title">Piste rose</h3>
        <div className="track">
          {range(12).map((n) => {
            const id = `pink-cell-${n}`;
            return (
              <ValueCell
                key={id}
                id={`${prefix}${id}`}
                label={`Joueur ${playerId}, rose case ${n}`}
                value={board.values[id]}
                {...cellProps(id)}
              />
            );
          })}
        </div>
      </section>

      {/* Compteurs de bonus (désactivés) */}
      <section
        className="zone zone-bonus is-disabled"
        aria-label={`Joueur ${playerId} compteurs de bonus (désactivés)`}
      >
        <h3 className="zone-title">Compteurs</h3>
        {BONUS_LABELS.map((bar) => (
          <div className="bonus-bar" key={bar}>
            <span className="bonus-label">Compteur {bar}</span>
            <div className="bonus-cells">
              {range(7).map((pos) => {
                const id = `bonus-${bar}-cell-${pos}`;
                return (
                  <CheckboxCell
                    key={id}
                    id={`${prefix}${id}`}
                    label={`Joueur ${playerId}, compteur ${bar}, case ${pos} (désactivé)`}
                    checked={false}
                  />
                );
              })}
            </div>
          </div>
        ))}
      </section>
    </div>
  );
}

export default BoardView;
