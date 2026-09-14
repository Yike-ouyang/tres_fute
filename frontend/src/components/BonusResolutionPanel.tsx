import { DIE_COLOR_OPTIONS } from "../boardData";
import { ACTING_COLORS, type ActingColor, type BonusResolution } from "../game/types";
import type { EngineAction } from "../api/client";

interface BonusResolutionPanelProps {
  resolution: BonusResolution;
  legalActions: EngineAction[];
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

function BonusResolutionPanel({
  resolution,
  legalActions,
  onChooseColor,
  onChooseValue,
  onPlaceBlue,
  onNoMoveDone,
}: BonusResolutionPanelProps) {
  const br = resolution;
  const legalValues = new Set(
    legalActions.filter((a) => a.type === "choose_bonus_value").map((a) => a.value)
  );
  const blueOptions = legalActions.filter((a) => a.type === "place_bonus_blue");

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
                disabled={!legalValues.has(v)}
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
            {blueOptions.map((opt) => (
              <button
                key={`${opt.cell_id}-${opt.value}`}
                type="button"
                className="btn btn-small"
                onClick={() => onPlaceBlue(opt.cell_id as string, opt.value as number)}
              >
                Case {cellPosition(opt.cell_id as string)} : inscrire {opt.value}
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
