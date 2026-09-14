import CheckboxCell from "./CheckboxCell";
import ValueCell from "./ValueCell";
import FixedCell from "./FixedCell";
import DieSlot from "./DieSlot";
import BonusSlot from "./BonusSlot";
import BonusPanel from "./BonusPanel";
import {
  BLUE_CELL_COUNT,
  BLUE_CENTER_INDEX,
  BLUE_CENTER_VALUE,
  BROWN_NUMBERS,
  DIE_LABELS,
  ROW_NUMBERS,
  TURQUOISE_ROWS,
} from "../boardData";
import { PASSIVE_YELLOW_CELLS } from "../game/rules";
import {
  PINK_MULTIPLIERS,
  isTurquoiseDark,
  slotsBySource,
  type SlotDef,
} from "../game/bonuses";
import type { PlayerBoard, PlayerId } from "../game/types";

const PASSIVE_YELLOW_SET = new Set(PASSIVE_YELLOW_CELLS);

// Position-indexed lookups so each bonus is rendered exactly at its source cell.
const TURN_BY_N = new Map(slotsBySource("turn").map((s) => [s.meta.n, s]));
const GOLD_BY_RC = new Map(
  slotsBySource("gold").map((s) => [`${s.meta.betweenRow}-${s.meta.col}`, s])
);
const TURQ_ROW_BY_ROW = new Map(slotsBySource("turqRow").map((s) => [s.meta.row, s]));
const TURQ_COL_BY_COL = new Map(slotsBySource("turqCol").map((s) => [s.meta.col, s]));
const BLUE_BY_POS = new Map(slotsBySource("blue").map((s) => [s.meta.pos, s]));
const BROWN_BY_LEFT = new Map(slotsBySource("brownGap").map((s) => [s.meta.left, s]));
const PINK_BY_N = new Map(slotsBySource("pink").map((s) => [s.meta.n, s]));

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
  /** This board's player is the active player (relance / joker owner). */
  activeOwner: boolean;
  /** A joker is pending on the active player's board. */
  jokerPending: boolean;
  /** Called with the unprefixed cell id when a legal destination is clicked. */
  onSelect: (cellId: string) => void;
  onRelance: () => void;
  onJoker: () => void;
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
  activeOwner,
  jokerPending,
  onSelect,
  onRelance,
  onJoker,
}: BoardViewProps) {
  const prefix = `p${playerId}-`;

  // Cells render with a prefixed DOM id (p1-/p2-) for uniqueness, but the game
  // logic (legal/picked) uses unprefixed ids. Strip the prefix before dispatching
  // so the clicked id matches the ids produced by the legality calculation.
  const handleSelect = (domId: string) =>
    onSelect(domId.startsWith(prefix) ? domId.slice(prefix.length) : domId);

  const cellProps = (id: string) => ({
    highlighted: interactive && legal.has(id),
    provisional: interactive && picked.has(id),
    onSelect: interactive ? handleSelect : undefined,
  });

  const unlocked = (slotId: string) => !!board.bonuses.slotsUnlocked[slotId];
  const slot = (def: SlotDef, title: string) => (
    <BonusSlot
      key={def.slotId}
      id={`${prefix}${def.slotId}`}
      effect={def.effect}
      unlocked={unlocked(def.slotId)}
      title={title}
    />
  );

  // Render either the real bonus for a position or an invisible spacer that keeps
  // the grid cell so following symbols never shift. "Aucun" positions (missing or
  // none-effect) stay empty and add no symbol that isn't in the reference tables.
  const slotOrEmpty = (def: SlotDef | undefined, title: string, key: string) =>
    def && def.effect.kind !== "none" ? (
      slot(def, title)
    ) : (
      <span key={key} className="bonus-slot-spacer" aria-hidden="true" />
    );

  return (
    <div className={`board-view${interactive ? " is-interactive" : ""}`}>
      <h2 className="board-view-title">
        Joueur {playerId} {interactive && <span className="acting-badge">à vous de jouer</span>}
      </h2>

      {/* Barre de suivi des tours : chaque bonus est directement sous son numéro */}
      <section className="zone zone-turns" aria-label={`Joueur ${playerId} tours`}>
        <h3 className="zone-title">Tours</h3>
        <div className="turn-grid">
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
          {range(6).map((n) =>
            slotOrEmpty(TURN_BY_N.get(n), `Tour ${n}`, `turn-bonus-${n}`)
          )}
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

      {/* Zone jaune : 5 rangées alternées (cases / bonus entre les lignes) */}
      <section className="zone zone-yellow" aria-label={`Joueur ${playerId} zone jaune`}>
        <h3 className="zone-title">Zone jaune</h3>
        <div className="yellow-grid">
          {/* Ligne 1 */}
          {ROW_NUMBERS.map((num, c) => {
            const col = c + 1;
            const id = `yellow-r1-c${col}`;
            return (
              <CheckboxCell
                key={id}
                id={`${prefix}${id}`}
                label={`Joueur ${playerId}, jaune ligne 1 colonne ${col}, nombre ${num}`}
                number={num}
                checked={!!board.checks[id]}
                passiveYellow={PASSIVE_YELLOW_SET.has(id)}
                {...cellProps(id)}
              />
            );
          })}
          {/* Bonus entre les lignes 1 et 2 */}
          {ROW_NUMBERS.map((_, c) => {
            const col = c + 1;
            return slotOrEmpty(
              GOLD_BY_RC.get(`1-${col}`),
              `Doré lignes 1-2, col ${col}`,
              `gold-1-${col}`
            );
          })}
          {/* Ligne 2 */}
          {ROW_NUMBERS.map((num, c) => {
            const col = c + 1;
            const id = `yellow-r2-c${col}`;
            return (
              <CheckboxCell
                key={id}
                id={`${prefix}${id}`}
                label={`Joueur ${playerId}, jaune ligne 2 colonne ${col}, nombre ${num}`}
                number={num}
                checked={!!board.checks[id]}
                passiveYellow={PASSIVE_YELLOW_SET.has(id)}
                {...cellProps(id)}
              />
            );
          })}
          {/* Bonus entre les lignes 2 et 3 */}
          {ROW_NUMBERS.map((_, c) => {
            const col = c + 1;
            return slotOrEmpty(
              GOLD_BY_RC.get(`2-${col}`),
              `Doré lignes 2-3, col ${col}`,
              `gold-2-${col}`
            );
          })}
          {/* Ligne 3 */}
          {ROW_NUMBERS.map((num, c) => {
            const col = c + 1;
            const id = `yellow-r3-c${col}`;
            return (
              <CheckboxCell
                key={id}
                id={`${prefix}${id}`}
                label={`Joueur ${playerId}, jaune ligne 3 colonne ${col}, nombre ${num}`}
                number={num}
                checked={!!board.checks[id]}
                passiveYellow={PASSIVE_YELLOW_SET.has(id)}
                {...cellProps(id)}
              />
            );
          })}
        </div>
      </section>

      {/* Zone turquoise : bonus de ligne à droite (col 7), bonus de colonne en dessous (rangée 6) */}
      <section className="zone zone-turquoise" aria-label={`Joueur ${playerId} zone turquoise`}>
        <h3 className="zone-title">Zone turquoise</h3>
        <div className="turquoise-grid">
          {range(TURQUOISE_ROWS).map((r) => (
            <div className="turquoise-grid-row-group" key={r}>
              {ROW_NUMBERS.map((num, c) => {
                const col = c + 1;
                const id = `turquoise-r${r}-c${col}`;
                return (
                  <CheckboxCell
                    key={id}
                    id={`${prefix}${id}`}
                    label={`Joueur ${playerId}, turquoise ligne ${r} colonne ${col}, nombre ${num}`}
                    number={num}
                    checked={!!board.checks[id]}
                    dark={isTurquoiseDark(r, col)}
                    {...cellProps(id)}
                  />
                );
              })}
              {slotOrEmpty(TURQ_ROW_BY_ROW.get(r), `Ligne ${r}`, `turqRow-${r}`)}
            </div>
          ))}
          <div className="turquoise-grid-row-group turquoise-col-bonuses">
            {ROW_NUMBERS.map((_, c) => {
              const col = c + 1;
              return slotOrEmpty(TURQ_COL_BY_COL.get(col), `Colonne ${col}`, `turqCol-${col}`);
            })}
            <span className="bonus-slot-spacer" aria-hidden="true" />
          </div>
        </div>
      </section>

      {/* Piste bleu foncé : bonus directement sous chaque case (centre = case 7) */}
      <section className="zone zone-blue" aria-label={`Joueur ${playerId} piste bleu foncé`}>
        <h3 className="zone-title">Piste bleu foncé</h3>
        <div className="track-scroll">
          <div className="blue-grid">
            {range(BLUE_CELL_COUNT).map((n) => {
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
            {range(BLUE_CELL_COUNT).map((n) =>
              slotOrEmpty(BLUE_BY_POS.get(n), `Case ${n}`, `blue-bonus-${n}`)
            )}
          </div>
        </div>
      </section>

      {/* Piste marron : bonus dans les intervalles entre les cases */}
      <section className="zone zone-brown" aria-label={`Joueur ${playerId} piste marron`}>
        <h3 className="zone-title">Piste marron</h3>
        <div className="track-scroll">
          <div className="brown-grid">
            {BROWN_NUMBERS.map((num, i) => {
              const n = i + 1;
              const id = `brown-cell-${n}`;
              const cell = (
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
              // Insert the between-cells bonus after every cell except the last.
              if (n === BROWN_NUMBERS.length) return cell;
              return [
                cell,
                slotOrEmpty(
                  BROWN_BY_LEFT.get(n),
                  `Entre ${n} et ${n + 1}`,
                  `brown-gap-${n}`
                ),
              ];
            })}
          </div>
        </div>
      </section>

      {/* Piste rose : multiplicateur au-dessus, bonus en dessous (inactifs en phase 1) */}
      <section className="zone zone-pink" aria-label={`Joueur ${playerId} piste rose`}>
        <h3 className="zone-title">Piste rose</h3>
        <div className="track-scroll">
          <div className="pink-grid">
            {/* Multiplicateurs */}
            {PINK_MULTIPLIERS.map((m, i) => (
              <span key={`mult-${i}`} className="pink-mult" aria-hidden={m <= 0}>
                {m > 0 ? `×${m}` : ""}
              </span>
            ))}
            {/* Cases numériques */}
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
            {/* Bonus en dessous */}
            {range(12).map((n) =>
              slotOrEmpty(PINK_BY_N.get(n), `Rose case ${n}`, `pink-bonus-${n}`)
            )}
          </div>
        </div>
      </section>

      <BonusPanel
        board={board}
        activeOwner={activeOwner}
        jokerPending={jokerPending}
        onRelance={onRelance}
        onJoker={onJoker}
      />
    </div>
  );
}

export default BoardView;
