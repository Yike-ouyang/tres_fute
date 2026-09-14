import { computeScore, type PlayerScore } from "../game/score";
import type { PlayerBoard, PlayerId } from "../game/types";

interface ScoreTableProps {
  boards: Record<PlayerId, PlayerBoard>;
}

interface Row {
  label: string;
  p1: number | string;
  p2: number | string;
  /** Highlight this row as the final total. */
  total?: boolean;
}

function rowsFrom(s1: PlayerScore, s2: PlayerScore): Row[] {
  return [
    { label: "Jaune", p1: s1.yellow, p2: s2.yellow },
    { label: "Turquoise", p1: s1.turquoise, p2: s2.turquoise },
    { label: "Bleu foncé", p1: s1.blue, p2: s2.blue },
    { label: "Marron", p1: s1.brown, p2: s2.brown },
    { label: "Rose", p1: s1.pink, p2: s2.pink },
    { label: "Sous-total des cinq couleurs", p1: s1.colorSubtotal, p2: s2.colorSubtotal },
    { label: "Renards débloqués", p1: s1.foxCount, p2: s2.foxCount },
    { label: "Valeur d’un renard", p1: s1.foxValue, p2: s2.foxValue },
    { label: "Points des renards", p1: s1.foxPoints, p2: s2.foxPoints },
    { label: "Total final", p1: s1.total, p2: s2.total, total: true },
  ];
}

/** Comparative end-of-game scoreboard. Only rendered after the last turn is fully done. */
function ScoreTable({ boards }: ScoreTableProps) {
  const s1 = computeScore(boards[1]);
  const s2 = computeScore(boards[2]);
  const winner: PlayerId | null = s1.total === s2.total ? null : s1.total > s2.total ? 1 : 2;

  return (
    <section className="score-table" aria-label="Résultats de fin de partie">
      <h2 className="score-table-title">Résultats</h2>
      <p className="score-table-winner">
        {winner === null ? "Égalité" : `Joueur ${winner} gagne`}
      </p>
      <table>
        <thead>
          <tr>
            <th scope="col">Catégorie</th>
            <th scope="col" className={winner === 1 ? "is-winner" : ""}>
              Joueur 1
            </th>
            <th scope="col" className={winner === 2 ? "is-winner" : ""}>
              Joueur 2
            </th>
          </tr>
        </thead>
        <tbody>
          {rowsFrom(s1, s2).map((row) => (
            <tr key={row.label} className={row.total ? "is-total" : ""}>
              <th scope="row">{row.label}</th>
              <td className={winner === 1 ? "is-winner" : ""}>{row.p1}</td>
              <td className={winner === 2 ? "is-winner" : ""}>{row.p2}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export default ScoreTable;
