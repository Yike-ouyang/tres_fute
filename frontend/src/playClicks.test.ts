import { describe, expect, it } from "vitest";
import {
  classifySelectDice,
  findCellAction,
  findDieAction,
  findFillAction,
  findByDetail,
  findTurquoiseAction,
  findWhiteColorAction,
  formatBonusTally,
  formatOpponent,
  isUniqueDestination,
  parseDetail,
  parseTurquoise,
  turquoiseColumn,
  turquoiseLegalCells,
  turquoiseShouldPlay,
} from "./game/playClicks";
import type { HumanLegalAction } from "./api/humanPlay";

function la(
  id: number,
  category: string,
  detail: string,
  factorised_step1 = false
): HumanLegalAction {
  return { id, category, detail, label: detail, factorised_step1 };
}

describe("playClicks — clic → action v2", () => {
  it("parseDetail sépare catégorie et valeur", () => {
    expect(parseDetail("die:yellow")).toEqual({ kind: "die", value: "yellow" });
    expect(parseDetail("use_relance")).toEqual({ kind: "use_relance", value: "use_relance" });
  });

  it("trouve le dé, le remplissage et la couleur blanche", () => {
    const legal = [
      la(0, "select_die", "die:yellow"),
      la(4, "select_die", "die:pink"),
      la(144, "fill_slot", "fill:brown"),
      la(6, "white_color", "white:darkblue"),
    ];
    expect(findDieAction(legal, "pink")?.id).toBe(4);
    expect(findDieAction(legal, "white")).toBeUndefined();
    expect(findFillAction(legal, "brown")?.id).toBe(144);
    expect(findWhiteColorAction(legal, "darkblue")?.id).toBe(6);
  });

  it("dé à destination unique → un seul id (auto-complétion)", () => {
    const unique = [la(60, "dest_blue", "darkblue:blue-cell-8")];
    expect(isUniqueDestination(unique)).toBe(true);
    const multiple = [
      la(60, "dest_blue", "darkblue:blue-cell-8"),
      la(65, "dest_blue", "darkblue:blue-cell-6"),
    ];
    expect(isUniqueDestination(multiple)).toBe(false);
    expect(isUniqueDestination([la(0, "select_die", "die:yellow")])).toBe(false);
  });

  it("clic sur une case → action de destination (non turquoise)", () => {
    const legal = [
      la(72, "dest_brown", "brown:brown-cell-3"),
      la(11, "dest_yellow", "yellow:yellow-r1-c2"),
      la(80, "dest_brown", "bonus-brown:brown-cell-5"),
    ];
    expect(findCellAction(legal, "brown-cell-3")?.id).toBe(72);
    expect(findCellAction(legal, "yellow-r1-c2")?.id).toBe(11);
    expect(findCellAction(legal, "brown-cell-5")?.id).toBe(80);
    expect(findCellAction(legal, "brown-cell-9")).toBeUndefined();
  });

  it("turquoise : sous-ensembles, colonne et cellules cliquables", () => {
    const legal = [
      la(29, "dest_turquoise", "turquoise:rows1@c4"),
      la(30, "dest_turquoise", "turquoise:rows2@c4"),
      la(31, "dest_turquoise", "turquoise:rows12@c4"),
    ];
    const parsed = parseTurquoise(legal);
    expect(parsed.map((t) => t.rows)).toEqual([[1], [2], [1, 2]]);
    expect(turquoiseColumn(legal)).toBe(4);
    expect([...turquoiseLegalCells(legal)].sort()).toEqual([
      "turquoise-r1-c4",
      "turquoise-r2-c4",
    ]);
    expect(findTurquoiseAction(legal, [2, 1])?.id).toBe(31);
  });

  it("turquoise T1 : joue à maxPick ou quand l'ensemble est maximal", () => {
    const legal = [
      la(29, "dest_turquoise", "turquoise:rows1@c4"),
      la(30, "dest_turquoise", "turquoise:rows2@c4"),
      la(31, "dest_turquoise", "turquoise:rows12@c4"),
    ];
    // maxPick=2 : un seul clic ne joue pas, deux clics jouent.
    expect(turquoiseShouldPlay(legal, [1], 2)).toBe(false);
    expect(turquoiseShouldPlay(legal, [1, 2], 2)).toBe(true);
    // maxPick=3 mais aucun sur-ensemble légal de {1,2} → maximal → joue.
    expect(turquoiseShouldPlay(legal, [1, 2], 3)).toBe(true);
    // Ensemble sans action légale → jamais.
    expect(turquoiseShouldPlay(legal, [3], 2)).toBe(false);
  });

  it("utilitaires et requêtes génériques", () => {
    const legal = [
      la(138, "utility", "use_relance"),
      la(142, "utility", "end_active_early"),
      la(84, "pink_option", "pink:points"),
    ];
    expect(findByDetail(legal, "use_relance", "utility")?.id).toBe(138);
    expect(findByDetail(legal, "pink:points")?.id).toBe(84);
    expect(findByDetail(legal, "missing")).toBeUndefined();
  });

  it("formatBonusTally : dispo/total", () => {
    expect(formatBonusTally(3, 1)).toBe("2/3");
    expect(formatBonusTally(2, 2)).toBe("0/2");
    expect(formatBonusTally(0, 0)).toBe("0/0");
  });

  it("formatOpponent : run / sous-dossier (fichier)", () => {
    expect(
      formatOpponent("/x/agent/runs/shaped_20260917_203604/run_min_zone/best_model.zip")
    ).toBe("shaped_20260917_203604 / run_min_zone (best_model.zip)");
    expect(formatOpponent("/x/agent/runs/essai_01/best_model.zip")).toBe(
      "essai_01 (best_model.zip)"
    );
    expect(formatOpponent(null)).toBe("IA");
  });

  it("classifySelectDice : dé actif / écarté / placé (phase passive)", () => {
    const legal = [
      la(4, "select_die", "die:pink"),
      la(5, "select_die", "die:white"),
      la(0, "select_die", "die:yellow"),
    ];
    const targets = classifySelectDice(legal, {
      yellow: "available",
      pink: "discarded",
      white: "discarded",
      brown: "chosen",
    });
    expect(targets.available).toEqual(["yellow"]);
    expect(targets.discarded).toEqual(["pink", "white"]);
    expect(targets.chosen).toEqual([]);
  });

  it("classifySelectDice : fallback sur les dés placés", () => {
    const legal = [la(1, "select_die", "die:turquoise")];
    const targets = classifySelectDice(legal, { turquoise: "chosen" });
    expect(targets.chosen).toEqual(["turquoise"]);
    expect(targets.available).toEqual([]);
  });
});
