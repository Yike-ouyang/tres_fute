import { DIE_COLOR_OPTIONS } from "../boardData";
import type { BonusEffect } from "../game/types";

interface BonusSlotProps {
  effect: BonusEffect;
  unlocked: boolean;
  /** Optional short position hint shown as the slot's tooltip / label. */
  title?: string;
  /** Prefixed DOM id (p1-/p2-) for stable fox/bonus identification. */
  id?: string;
}

const DIE_BG: Record<string, string> = {
  ...Object.fromEntries(DIE_COLOR_OPTIONS.map((o) => [o.value, o.background])),
  black: "#20242c",
};
const DIE_FG: Record<string, string> = {
  ...Object.fromEntries(DIE_COLOR_OPTIONS.map((o) => [o.value, o.text])),
  black: "#ffffff",
};

function effectContent(effect: BonusEffect) {
  switch (effect.kind) {
    case "none":
      return { glyph: "–", style: undefined, label: "aucun bonus" };
    case "cumulative": {
      const glyph =
        effect.bonus === "relance" ? "↻" : effect.bonus === "joker" ? "J" : "+1";
      const label =
        effect.bonus === "relance"
          ? "relance"
          : effect.bonus === "joker"
          ? "joker"
          : "+1";
      return { glyph, style: undefined, label };
    }
    case "die":
      return {
        glyph: "▪",
        style: { background: DIE_BG[effect.color], color: DIE_FG[effect.color] },
        label: `dé ${effect.color}`,
      };
    case "fox":
      return { glyph: "🦊", style: undefined, label: "renard" };
  }
}

/** A single inline bonus slot: shows its effect and whether it has been unlocked. */
function BonusSlot({ effect, unlocked, title, id }: BonusSlotProps) {
  const { glyph, style, label } = effectContent(effect);
  const className = [
    "bonus-slot",
    `bonus-slot-${effect.kind}`,
    effect.kind === "die" ? `bonus-slot-die-${effect.color}` : "",
    unlocked ? "is-unlocked" : "",
    effect.kind === "none" ? "is-empty" : "",
    effect.kind === "fox" && !unlocked ? "is-locked-fox" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <span
      id={id}
      className={className}
      style={style}
      title={`${title ? title + " — " : ""}${label}${unlocked ? " (débloqué)" : ""}`}
      aria-label={`${title ? title + ", " : ""}bonus ${label}${unlocked ? ", débloqué" : ""}`}
    >
      <span className="bonus-slot-glyph">{glyph}</span>
      {unlocked && (
        <span className="bonus-slot-check" aria-hidden="true">
          ✓
        </span>
      )}
    </span>
  );
}

export default BonusSlot;
