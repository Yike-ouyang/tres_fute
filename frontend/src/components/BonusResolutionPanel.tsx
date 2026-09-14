import { DIE_COLOR_OPTIONS } from "../boardData";
import {
  blueBonusOptions,
  bonusBrownLegal,
  bonusYellowLegal,
} from "../game/rules";
import { ACTING_COLORS, type ActingColor, type BonusResolution, type PlayerBoard } from "../game/types";

interface BonusResolutionPanelProps {
  resolution: BonusResolution;
  /** The owner's board (for computing legal values / blue options). */
  board: PlayerBoard;
  onChooseColor: (color: ActingColor) => void;
  onChooseValue: (value: number) => void;
  onPlaceBlue: (cellId: string, value: number) => void;
  onNoMoveDone: () => void;
}

const COLOR_META = (color: ActingColor) =>
  DIE_COLOR_OPTIONS.find((c) => c.value === color)!;

const DICE_VALUES = [1, 2, 3, 4, 5, 6];

function cellPosition(cellId: string): number {
  return Number(cellId.split("-").pop());
}

/**
 * Interactive overlay for resolving one immediate colored bonus die on its
 * owner's board. Placement of yellow / brown / turquoise happens on the board
 * itself (highlighted cells + the Valider button); this panel drives the color,
 * value, dark-blue options and the no-move exit.
 */
function BonusResolutionPanel({
  resolution,
  board,
  onChooseColor,
  onChooseValue,
  onPlaceBlue,
  onNoMoveDone,
}: BonusResolutionPanelProps) {
  const br = resolution;

  const valueEnabled = (v: number): boolean => {
    if (br.color === "yellow") return bonusYellowLegal(board, v).length > 0;
    if (br.color === "brown") return bonusBrownLegal(board, v).length > 0;
    return true; // pink: any value while a cell is free
  };

  return (
    <div className="bonus-resolution" role="group" aria-label="Résolution d'un bonus immédiat">
      <span className="bonus-resolution-title">
        Bonus immédiat — Joueur {br.owner}
      </span>

      {br.stage === "chooseColor" && (
        <div className="bonus-resolution-row">
          <span className="bonus-resolution-label">Dé noir : choisissez une couleur</span>
          <div className="bonus-resolution-options">
            {ACTING_COLORS.map((color) => {
              const meta = COLOR_META(color);
              return (
                <button
                  key={color}
                  type="button"
                  className="bonus-color-option"
                  style={{ background: meta.background, color: meta.text }}
                  onClick={() => onChooseColor(color)}
                >
                  {meta.label}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {br.stage === "chooseValue" && (
        <div className="bonus-resolution-row">
          <span className="bonus-resolution-label">
            Bonus {COLOR_META(br.color as ActingColor).label} : choisissez une valeur
          </span>
          <div className="bonus-resolution-options">
            {DICE_VALUES.map((v) => (
              <button
                key={v}
                type="button"
                className="btn btn-small"
                disabled={!valueEnabled(v)}
                onClick={() => onChooseValue(v)}
              >
                {v}
              </button>
            ))}
          </div>
        </div>
      )}

      {br.stage === "placing" && br.color === "darkblue" && (
        <div className="bonus-resolution-row">
          <span className="bonus-resolution-label">
            Bonus bleu foncé : choisissez la case et la valeur
          </span>
          <div className="bonus-resolution-options">
            {blueBonusOptions(board).map((opt) => (
              <button
                key={`${opt.cellId}-${opt.value}`}
                type="button"
                className="btn btn-small"
                onClick={() => onPlaceBlue(opt.cellId, opt.value)}
              >
                Case {cellPosition(opt.cellId)} : inscrire {opt.value}
              </button>
            ))}
          </div>
        </div>
      )}

      {br.stage === "placing" && br.color !== "darkblue" && (
        <span className="bonus-resolution-label">
          {br.color === "turquoise"
            ? "Cochez la case turquoise de votre choix, puis validez."
            : "Choisissez une case surlignée, puis validez."}
        </span>
      )}

      {br.stage === "noMove" && (
        <div className="bonus-resolution-row">
          <span className="bonus-resolution-label">
            Aucun coup possible pour ce bonus : il est perdu.
          </span>
          <button type="button" className="btn btn-primary" onClick={onNoMoveDone}>
            Terminer
          </button>
        </div>
      )}
    </div>
  );
}

export default BonusResolutionPanel;
