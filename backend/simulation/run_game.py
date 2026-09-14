"""Play complete games against the engine with no HTTP and no browser."""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

# Allow `python simulation/run_game.py` from backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from game_engine.engine import GameEngine
from simulation.policy import run_autoplay


def main() -> None:
    parser = argparse.ArgumentParser(description="Autoplay Très Futé without FastAPI.")
    parser.add_argument("--seeds", default="1,2,3", help="Comma-separated engine seeds")
    parser.add_argument("--policy-seed", type=int, default=99, help="RNG seed for the autoplay policy")
    parser.add_argument("--turns", type=int, default=6, help="Global turns to play (6 = full game)")
    args = parser.parse_args()
    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    results = []
    for seed in seeds:
        engine = GameEngine(seed=seed)
        policy_rng = random.Random(args.policy_seed + seed)
        summary = run_autoplay(engine, args.turns, policy_rng)
        row = {
            "seed": seed,
            "over": summary["over"],
            "stopped": summary["stopped"],
            "completed": summary["completed"],
            "scores": summary["scores"],
        }
        results.append(row)
        s1, s2 = summary["scores"][1]["total"], summary["scores"][2]["total"]
        print(f"seed={seed} over={summary['over']} P1={s1} P2={s2} ({summary['stopped']})")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
