"""Build ``REPORT.md`` (+ PNG curves) for a ``sequence_<timestamp>`` directory.

Extracts the evaluation scalars from the per-run TensorBoard event files, compares
the four runs, evaluates the ``essai_01`` baseline (agent vs HeuristicPolicy) on
the same seeds, and writes a self-contained Markdown report.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

_AGENT_DIR = Path(__file__).resolve().parents[1]   # agent/ (contains rl_env / rl_env_2)
_BACKEND_DIR = _AGENT_DIR.parent / "backend"       # backend/ (game_engine, simulation)
for _root in (_AGENT_DIR, _BACKEND_DIR):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

RUN_ORDER = ("run1_score_delta", "run2_fox", "run3_zone", "run4_terminal")
RUN_LABELS = {
    "run1_score_delta": "Run 1 — score_delta",
    "run2_fox": "Run 2 — + fox",
    "run3_zone": "Run 3 — + zone",
    "run4_terminal": "Run 4 — + terminal",
}
SCALARS = ("eval/win_rate", "eval/mean_score_agent", "eval/mean_fox_agent")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sequence", type=Path, required=True)
    p.add_argument("--eval-seed", type=int, default=1_000_000)
    p.add_argument("--eval-episodes", type=int, default=200)
    p.add_argument("--checkpoint", type=Path, default=Path("runs/essai_01/best_model.zip"))
    p.add_argument("--baseline-opponent", default="heuristic", choices=["heuristic", "random"])
    p.add_argument("--no-baseline", action="store_true")
    p.add_argument("--device", default="cpu")
    return p.parse_args(argv)


def _read_json(path: Path) -> Any:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _progress_last(run_dir: Path) -> dict[str, str]:
    path = run_dir / "progress.csv"
    if not path.exists():
        return {}
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    for row in reversed(rows):
        if row.get("time/time_elapsed"):
            return row
    return rows[-1] if rows else {}


def _scalars(run_dir: Path) -> dict[str, tuple[list[int], list[float]]]:
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

    acc = EventAccumulator(str(run_dir))
    try:
        acc.Reload()
    except Exception:  # pragma: no cover
        return {}
    tags = set(acc.Tags().get("scalars", []))
    out: dict[str, tuple[list[int], list[float]]] = {}
    for tag in SCALARS:
        if tag in tags:
            events = acc.Scalars(tag)
            out[tag] = ([int(e.step) for e in events], [float(e.value) for e in events])
    return out


def _eval_seeds(base: int, episodes: int) -> list[tuple[int, int]]:
    return [(base + i // 2, 1 + i % 2) for i in range(episodes)]


def evaluate_baseline(checkpoint: Path, seeds: list[tuple[int, int]], opponent: str, device: str) -> dict[str, Any] | None:
    if not checkpoint.exists():
        return None
    from sb3_contrib import MaskablePPO

    from rl_env import DiceGameEnv
    from rl_env.wrappers import FixedBoxScaling

    model = MaskablePPO.load(str(checkpoint), device=device)
    envs = {
        1: FixedBoxScaling(DiceGameEnv(agent_player=1, opponent=opponent)),
        2: FixedBoxScaling(DiceGameEnv(agent_player=2, opponent=opponent)),
    }
    rows = []
    try:
        for seed, player in seeds:
            env = envs[player]
            obs, _ = env.reset(seed=seed)
            while True:
                mask = env.action_masks()
                action, _ = model.predict(obs, deterministic=True, action_masks=mask)
                obs, _r, term, trunc, info = env.step(int(np.asarray(action).item()))
                if term or trunc:
                    break
            scores = info["final_scores"]
            board = env.unwrapped.engine.state["boards"][player]
            rows.append(
                {
                    "score": scores["agent"],
                    "opponent": scores["adversary"],
                    "win": int(scores["agent"] > scores["adversary"]),
                    "draw": int(scores["agent"] == scores["adversary"]),
                    "loss": int(scores["agent"] < scores["adversary"]),
                    "fox": int(info["scores_full"][str(player)]["fox_count"]),
                }
            )
    finally:
        for env in envs.values():
            env.close()
    n = len(rows)
    return {
        "opponent": opponent,
        "episodes": n,
        "win_rate": sum(r["win"] for r in rows) / n,
        "draw_rate": sum(r["draw"] for r in rows) / n,
        "loss_rate": sum(r["loss"] for r in rows) / n,
        "mean_score_agent": float(np.mean([r["score"] for r in rows])),
        "mean_score_opponent": float(np.mean([r["opponent"] for r in rows])),
        "mean_fox_agent": float(np.mean([r["fox"] for r in rows])),
    }


def _plot(series: dict[str, dict[str, tuple[list[int], list[float]]]], tag: str, path: Path) -> bool:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if not any(tag in s for s in series.values()):
        return False
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for name, data in series.items():
        if tag in data:
            steps, values = data[tag]
            ax.plot(steps, values, marker="o", markersize=3, label=RUN_LABELS.get(name, name))
    ax.set_xlabel("timesteps (cumulés)")
    ax.set_ylabel(tag)
    ax.set_title(tag)
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return True


def build_report(args: argparse.Namespace) -> Path:
    seq = args.sequence
    table_rows = []
    series: dict[str, dict[str, tuple[list[int], list[float]]]] = {}
    for name in RUN_ORDER:
        run_dir = seq / name
        if not run_dir.exists():
            continue
        meta = _read_json(run_dir / "metadata.json") or {}
        best = _read_json(run_dir / "best_metrics.json") or {}
        progress = _progress_last(run_dir)
        series[name] = _scalars(run_dir)
        table_rows.append(
            {
                "run": name,
                "label": RUN_LABELS.get(name, name),
                "reward": meta.get("reward_formula", ""),
                "win": best.get("win_rate"),
                "draw": best.get("draw_rate"),
                "loss": best.get("loss_rate"),
                "score_agent": best.get("mean_score_agent"),
                "score_opp": best.get("mean_score_opponent"),
                "fox": best.get("mean_fox_agent"),
                "min_zone": best.get("mean_min_zone_agent"),
                "steps": progress.get("time/total_timesteps") or meta.get("num_timesteps_end"),
                "elapsed": progress.get("time/time_elapsed"),
            }
        )

    plots = {}
    for tag, fname in (
        ("eval/win_rate", "eval_win_rate.png"),
        ("eval/mean_score_agent", "eval_mean_score_agent.png"),
        ("eval/mean_fox_agent", "eval_mean_fox_agent.png"),
    ):
        plots[tag] = _plot(series, tag, seq / fname)

    baseline = None
    if not args.no_baseline:
        baseline = evaluate_baseline(
            args.checkpoint, _eval_seeds(args.eval_seed, args.eval_episodes), args.baseline_opponent, args.device
        )

    lines: list[str] = []
    lines.append("# Rapport — séquence d'entraînement `rl_env_2`\n")
    lines.append(f"Dossier : `{seq}`\n")
    lines.append(
        "Quatre runs séquentiels de MaskablePPO, chacun reprenant le `best_model.zip` du run "
        "précédent (`reset_num_timesteps=False`). Observation 2.0, actions 2.0 (149), `gamma = 0.999`.\n"
    )

    lines.append("## 1. Tableau comparatif\n")
    lines.append("| Run | win | draw | loss | score agent | score adverse | renards agent | min_zone | pas | temps (s) |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")

    def fmt(v, pct=False):
        if v is None:
            return "—"
        return f"{100 * v:.1f}%" if pct else f"{float(v):.1f}"

    for row in table_rows:
        lines.append(
            f"| {row['label']} | {fmt(row['win'], True)} | {fmt(row['draw'], True)} | {fmt(row['loss'], True)} | "
            f"{fmt(row['score_agent'])} | {fmt(row['score_opp'])} | {fmt(row['fox'])} | {fmt(row['min_zone'])} | "
            f"{row['steps'] or '—'} | {row['elapsed'] or '—'} |"
        )
    lines.append("")
    lines.append("Métriques = meilleure évaluation (modèle `best_model.zip`), 200 parties seedées, greedy, "
                 "adversaire = checkpoint `essai_01` (`.zip`).\n")
    if baseline:
        lines.append(
            f"**Baseline `essai_01` vs {baseline['opponent']}** (agent = essai_01, mêmes {baseline['episodes']} seeds) : "
            f"win {100 * baseline['win_rate']:.1f}%, draw {100 * baseline['draw_rate']:.1f}%, "
            f"loss {100 * baseline['loss_rate']:.1f}%, score agent {baseline['mean_score_agent']:.1f}.\n"
        )
        lines.append(
            "> Note : la baseline est mesurée contre `HeuristicPolicy`, alors que les runs sont évalués contre le "
            "checkpoint `essai_01` ; ce ne sont pas des adversaires identiques, à garder en tête pour la comparaison.\n"
        )

    lines.append("## 2. Courbes\n")
    for tag, ok in plots.items():
        fname = {"eval/win_rate": "eval_win_rate.png", "eval/mean_score_agent": "eval_mean_score_agent.png",
                 "eval/mean_fox_agent": "eval_mean_fox_agent.png"}[tag]
        lines.append(f"- `{tag}` : {'`' + fname + '`' if ok else 'non disponible (logs TensorBoard absents)'}")
    lines.append("")

    lines.append("## 3. Analyse par ajout de reward\n")
    for i in range(1, len(table_rows)):
        prev, cur = table_rows[i - 1], table_rows[i]
        if prev["win"] is None or cur["win"] is None:
            continue
        delta = cur["win"] - prev["win"]
        verdict = "améliore" if delta > 0.005 else "dégrade" if delta < -0.005 else "stagne"
        lines.append(
            f"- **{cur['label']}** vs précédent : win rate {100 * prev['win']:.1f}% → {100 * cur['win']:.1f}% "
            f"(Δ = {100 * delta:+.1f} pts) → **{verdict}**."
        )
        if verdict == "dégrade":
            lines.append(
                "  - Hypothèse : poids trop fort ou mal aligné (le terme peut être maximisé par un comportement "
                "local au détriment du score final). Suivi : réduire le poids (0.5 → 0.2) ou normaliser le terme."
            )
    lines.append("")

    lines.append("## 4. Recommandation\n")
    ranked = [r for r in table_rows if r["win"] is not None]
    if ranked:
        best = max(ranked, key=lambda r: (r["win"], r["score_agent"] or 0))
        lines.append(f"- **Meilleur run : {best['label']}** (win {100 * best['win']:.1f}%).")
        lines.append(
            "- Prochaine expérience : tester `gamma = 0.9995`, ou un reward `+ Δ(min_zone)` pour l'équilibre des "
            "couleurs, et réévaluer contre le même adversaire fixe."
        )
    else:
        lines.append("- Aucune évaluation exploitable trouvée.")

    report = seq / "REPORT.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    report = build_report(args)
    print(f"Report written: {report}")


if __name__ == "__main__":
    main()
