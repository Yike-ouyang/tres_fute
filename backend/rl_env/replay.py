"""Reconstruct the exact game played by a trained MaskablePPO checkpoint.

The model file does not contain the game: the environment is deterministic given
the eval seed, so replaying the checkpoint on the same seed regenerates the exact
match (same scores, same decisions). This module drives the environment with a
``trace`` hook and writes one JSON file per episode, plus an ``index.json``
manifest, for the frontend replay viewer.

Example::

    python rl_env/replay.py --run runs/essai_01 --checkpoint best_model.zip \\
        --seed 1000000 --agent-player 1
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rl_env import ACTION_VERSION, N_ACTIONS, OBSERVATION_VERSION, DiceGameEnv  # noqa: E402
from rl_env.actions import label  # noqa: E402
from rl_env.observations import encode_observation  # noqa: E402

_HERE = Path(__file__).resolve().parent
_DEFAULT_RUN = _HERE.parent / "runs" / "essai_01"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Reconstruct exact episodes from a checkpoint.")
    p.add_argument("--run", type=Path, default=_DEFAULT_RUN, help="Run directory (contains config.json)")
    p.add_argument("--checkpoint", default="best_model.zip")
    p.add_argument("--seed", type=int, default=None, help="Eval seed (default: first of the best block)")
    p.add_argument("--agent-player", type=int, choices=(1, 2), default=None)
    p.add_argument("--episode", type=int, default=None, help="Index in the best-block eval CSV")
    p.add_argument("--all-best-block", action="store_true", help="Generate all episodes of the best evaluation")
    p.add_argument("--out-dir", type=Path, default=None, help="Defaults to <run>/replays")
    p.add_argument("--device", default="cpu")
    return p.parse_args(argv)


def _module_constants():
    # Imported lazily so --help works even without sb3/torch installed.
    from rl_env.observations import (
        ALL_DIE_COLORS,
        BONUS_DIE_COLORS,
        DECISION_KINDS,
        PHASE_KINDS,
        PINK_BONUS_KINDS,
    )

    return ALL_DIE_COLORS, BONUS_DIE_COLORS, DECISION_KINDS, PHASE_KINDS, PINK_BONUS_KINDS


_LOCATIONS = ("available", "chosen", "discarded")


def summarize_observation(obs: dict[str, np.ndarray], agent: int) -> dict[str, Any]:
    """Human-readable summary of the numeric observation the agent received."""
    all_colors, bonus_colors, decision_kinds, phase_kinds, _ = _module_constants()
    players = ("agent", "adversary")

    dice = []
    for i, color in enumerate(all_colors):
        joker = int(obs["dice_joker_values"][i])
        dice.append(
            {
                "color": color,
                "value": int(obs["dice_values"][i]),
                "location": _LOCATIONS[int(obs["dice_locations"][i])],
                "joker_value": joker or None,
            }
        )
    selected = [all_colors[i] for i in range(len(all_colors)) if obs["die_selected"][i]]
    selection = None
    if int(obs["selection_present"][0]):
        selection = {
            "color": all_colors[int(obs["selection_color"][0]) - 1] if int(obs["selection_color"][0]) else None,
            "acting_color": (
                ("yellow", "turquoise", "darkblue", "brown", "pink")[int(obs["selection_acting"][0]) - 1]
                if int(obs["selection_acting"][0])
                else None
            ),
            "value": int(obs["selection_value"][0]),
            "max_pick": int(obs["selection_max_pick"][0]),
            "picked_cells": int(obs["selection_picked"].sum()),
            "legal_cells": int(obs["selection_legal"].sum()),
        }
    pending = []
    for i in range(int(obs["pending_bonus_count"][0])):
        pending.append(
            {
                "owner": "agent" if obs["pending_bonus_owner_is_agent"][i] else "adversary",
                "color": bonus_colors[int(obs["pending_bonus_colors"][i]) - 1],
            }
        )
    return {
        "agent_player": agent,
        "scores": {players[i]: int(obs["score_total"][i]) for i in range(2)},
        "fox_count": {players[i]: int(obs["fox_count"][i]) for i in range(2)},
        "turn": int(obs["turn"][0]),
        "round": int(obs["round"][0]),
        "phase": phase_kinds[int(obs["phase"][0])],
        "decision": decision_kinds[int(obs["decision"][0])],
        "actor": "agent" if int(obs["actor_is_agent"][0]) else "adversary",
        "active_is_agent": bool(int(obs["active_is_agent"][0])),
        "dice": dice,
        "selected_die": selected[0] if selected else None,
        "selection": selection,
        "bonuses": {
            "agent": {b: tally_bonus(obs, 0, b) for b in ("relance", "joker", "plus1")},
            "adversary": {b: tally_bonus(obs, 1, b) for b in ("relance", "joker", "plus1")},
        },
        "pending_bonuses": pending,
        "joker_pending": bool(int(obs["joker_pending"][0])),
    }


_BONUS_FIELD = {
    ("relance", "unlocked"): 0,
    ("relance", "used"): 1,
    ("joker", "unlocked"): 2,
    ("joker", "used"): 3,
    ("plus1", "unlocked"): 4,
    ("plus1", "used"): 5,
}


def tally_bonus(obs: dict[str, np.ndarray], player_index: int, bonus: str) -> dict[str, int]:
    row = obs["bonuses"][player_index]
    return {
        "unlocked": int(row[_BONUS_FIELD[(bonus, "unlocked")]]),
        "used": int(row[_BONUS_FIELD[(bonus, "used")]]),
    }


def _load_runner():
    try:
        from sb3_contrib import MaskablePPO
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("sb3-contrib is required for replay: pip install sb3-contrib stable-baselines3") from exc
    return MaskablePPO


def _check_compatibility(model: Any, run: Path) -> dict[str, Any]:
    meta = getattr(model, "dice_training_metadata", None)
    if not meta:
        raise SystemExit("checkpoint has no dice_training_metadata; regenerate it with train_maskable_ppo.py")
    expected = {
        "action_version": ACTION_VERSION,
        "observation_version": OBSERVATION_VERSION,
        "n_actions": N_ACTIONS,
    }
    for key, value in expected.items():
        if meta.get(key) != value:
            raise SystemExit(f"checkpoint incompatible: {key}={meta.get(key)!r} != current {value!r}")
    return meta


def _run_episode(model: Any, run: Path, config: dict[str, Any], seed: int, agent_player: int) -> dict[str, Any]:
    from rl_env.wrappers import FixedBoxScaling

    args = config.get("arguments", {})
    env = FixedBoxScaling(
        DiceGameEnv(
            agent_player=agent_player,
            opponent=args.get("opponent", "heuristic"),
            reward_mode=args.get("reward_mode", "score_delta"),
            reward_scale=float(args.get("reward_scale", 100.0)),
            max_steps=None,
            trace=True,
        )
    )
    inner = env.env
    try:
        obs, _ = env.reset(seed=seed)
        decisions = 0
        while True:
            mask = env.action_masks()
            legal_labels = [{"id": int(i), "label": label(int(i))} for i in np.flatnonzero(mask)]
            summary = summarize_observation(encode_observation(inner.engine.state, agent_player), agent_player)
            mark = len(inner.trace)
            action, _ = model.predict(obs, deterministic=True, action_masks=mask)
            obs, _reward, terminated, truncated, info = env.step(int(np.asarray(action).item()))
            decisions += 1
            if mark < len(inner.trace):
                inner.trace[mark]["observation_summary"] = summary
                inner.trace[mark]["legal_actions"] = legal_labels
            if terminated or truncated:
                break
        initial_state = inner.trace_initial
    finally:
        env.close()

    trace = {
        "run": run.name,
        "checkpoint": str(Path(config.get("__checkpoint__", ""))),
        "seed": seed,
        "agent_player": agent_player,
        "rules_version": config.get("compatibility", {}).get("rules_version"),
        "observation_version": OBSERVATION_VERSION,
        "action_version": ACTION_VERSION,
        "n_actions": N_ACTIONS,
        "initial_state": initial_state,
        "frames": inner.trace,
        "final_scores": info.get("final_scores"),
        "result": info.get("result"),
        "agent_decisions": decisions,
        "created": datetime.now(timezone.utc).isoformat(),
    }
    return trace


def _best_block_rows(run: Path) -> list[dict[str, str]]:
    best_path = run / "best_evaluation.json"
    episodes_path = run / "evaluation_episodes.csv"
    if not episodes_path.exists():
        return []
    best_ts = None
    if best_path.exists():
        best_ts = str(json.loads(best_path.read_text(encoding="utf-8"))["timesteps"])
    rows = list(csv.DictReader(episodes_path.open(encoding="utf-8")))
    if best_ts is not None:
        rows = [r for r in rows if r["timesteps"] == best_ts]
    return rows


def _update_manifest(out_dir: Path, entry: dict[str, Any]) -> None:
    manifest_path = out_dir / "index.json"
    manifest: dict[str, Any] = {"replays": []}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["replays"] = [r for r in manifest.get("replays", []) if r["id"] != entry["id"]]
    manifest["replays"].append(entry)
    manifest["replays"].sort(key=lambda r: (r["run"], r["seed"], r["agent_player"]))
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def reconstruct(run: Path, checkpoint: str, seed: int, agent_player: int, out_dir: Path | None = None) -> dict[str, Any]:
    MaskablePPO = _load_runner()
    model_path = run / checkpoint
    if not model_path.exists():
        raise SystemExit(f"checkpoint not found: {model_path}")
    config = json.loads((run / "config.json").read_text(encoding="utf-8"))
    config["__checkpoint__"] = model_path
    model = MaskablePPO.load(str(model_path), device="cpu")
    _check_compatibility(model, run)

    trace = _run_episode(model, run, config, seed, agent_player)

    out = out_dir or (run / "replays")
    out.mkdir(parents=True, exist_ok=True)
    replay_id = f"{run.name}__{Path(checkpoint).stem}_seed{seed}_p{agent_player}"
    file_name = f"{replay_id}.json"
    (out / file_name).write_text(json.dumps(trace, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    _update_manifest(
        out,
        {
            "id": replay_id,
            "run": run.name,
            "checkpoint": checkpoint,
            "seed": seed,
            "agent_player": agent_player,
            "file": file_name,
            "agent_decisions": trace["agent_decisions"],
            "frames": len(trace["frames"]),
            "final_scores": trace["final_scores"],
            "result": trace["result"],
        },
    )
    return trace


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    run = args.run.resolve()
    if not (run / "config.json").exists():
        raise SystemExit(f"not a run directory (missing config.json): {run}")

    targets: list[tuple[int, int]] = []
    if args.all_best_block:
        for row in _best_block_rows(run):
            targets.append((int(row["seed"]), int(row["agent_player"])))
    elif args.episode is not None:
        rows = _best_block_rows(run)
        if not rows:
            raise SystemExit("no best-block evaluation rows found")
        row = rows[args.episode % len(rows)]
        targets.append((int(row["seed"]), int(row["agent_player"])))
    else:
        seed = args.seed if args.seed is not None else 1000000
        player = args.agent_player if args.agent_player is not None else 1
        targets.append((seed, player))

    for seed, player in targets:
        trace = reconstruct(run, args.checkpoint, seed, player, out_dir=args.out_dir)
        print(
            f"seed={seed} P{player}: {trace['agent_decisions']} decisions, {len(trace['frames'])} frames, "
            f"scores={trace['final_scores']} result={trace['result']}"
        )
    print(f"Wrote {len(targets)} replay(s) to {(args.out_dir or run / 'replays')}")


if __name__ == "__main__":
    main()
