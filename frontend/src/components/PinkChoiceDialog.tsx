import { DIE_COLOR_OPTIONS } from "../boardData";
import type { BonusEffect, PinkChoice } from "../game/types";

interface PinkChoiceDialogProps {
  choice: PinkChoice;
  onChoose: (option: "points" | "bonus") => void;
  onCancel: () => void;
}

function bonusLabel(effect: BonusEffect): string {
  switch (effect.kind) {
    case "none":
      return "Aucun bonus sur cette case";
    case "cumulative":
      return effect.bonus === "relance"
        ? "Relance"
        : effect.bonus === "joker"
        ? "Joker chiffre"
        : "+1";
    case "die": {
      const meta = DIE_COLOR_OPTIONS.find((c) => c.value === effect.color);
      return `Dé bonus ${meta ? meta.label.toLowerCase() : effect.color}`;
    }
    case "fox":
      return "Renard";
  }
}

/**
 * The points-vs-bonus choice shown for every pink inscription except the first
 * cell. Cell 1 never opens this panel: it is written as ceil(effectiveValue / 2)
 * with no multiplier choice and no bonus. Nothing is written or consumed until
 * an option is confirmed.
 */
function PinkChoiceDialog({ choice, onChoose, onCancel }: PinkChoiceDialogProps) {
  const points = choice.effectiveValue * choice.multiplier;
  const half = Math.ceil(choice.effectiveValue / 2);
  const noBonus = choice.bonusEffect.kind === "none";

  return (
    <div className="pink-choice" role="dialog" aria-label="Choix de la case rose">
      <div className="pink-choice-head">
        <strong>Case rose n° {choice.position}</strong>
        <span>
          Joueur {choice.owner} — valeur effective {choice.effectiveValue}, multiplicateur ×
          {choice.multiplier}
        </span>
        <span>Bonus de la case : {bonusLabel(choice.bonusEffect)}</span>
      </div>

      <div className="pink-choice-options">
        <button type="button" className="btn btn-primary" onClick={() => onChoose("points")}>
          Inscrire {points}, sans bonus
        </button>
        <button
          type="button"
          className="btn"
          disabled={noBonus}
          onClick={() => onChoose("bonus")}
        >
          {noBonus
            ? "Aucun bonus sur cette case"
            : `Inscrire ${half} et obtenir le bonus (${bonusLabel(choice.bonusEffect)})`}
        </button>
        <button type="button" className="btn" onClick={onCancel}>
          Annuler
        </button>
      </div>
    </div>
  );
}

export default PinkChoiceDialog;
