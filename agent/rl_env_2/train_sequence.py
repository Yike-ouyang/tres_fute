"""Sequential MaskablePPO training on :mod:`rl_env_2` (four cumulative rewards).

Runs are chained: each resumes the previous ``best_model.zip`` with
``reset_num_timesteps=False`` so TensorBoard curves share the same step axis.
Evaluation is done on fixed, disjoint seeds against a fixed opponent (the
``essai_01`` checkpoint by default) and the best model is kept by **win rate**.

Example::

    python rl_env_2/train_sequence.py --timesteps 200000 --n-envs 4
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

_AGENT_DIR = Path(__file__).resolve().parents[1]   # agent/ (contains rl_env / rl_env_2)
_BACKEND_DIR = _AGENT_DIR.parent / "backend"       # backend/ (game_engine, simulation)
for _root in (_AGENT_DIR, _BACKEND_DIR):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

from game_engine.types import RULES_VERSION  # noqa: E402
from rl_env_2 import ACTION_VERSION_2, N_ACTIONS_2, OBSERVATION_VERSION_2, DiceGameEnv2  # noqa: E402
from rl_env_2.observations import zones_completed  # noqa: E402
from rl_env_2.opponents import DEFAULT_CHECKPOINT  # noqa: E402
from rl_env_2.rewards import describe  # noqa: E402
from rl_env_2.wrappers import FixedBoxScaling2  # noqa: E402

RUNS = (
    ("run1_score_delta", "score_delta_normalized"),
    ("run2_fox", "fox"),
    ("run3_zone", "zone"),
    ("run4_terminal", "terminal"),
)

TRAIN_SEED_BASE = 42  # training env seeds use small disjoint values
EVAL_SEED_BASE = 1_000_000  # evaluation seeds are all >= 1e6 (disjoint from training)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--timesteps", type=int, default=1_000_000, help="Agent transitions per run")
    p.add_argument("--n-envs", type=int, default=4)
    p.add_argument("--n-steps", type=int, default=2048)
    p.add_argument("--batch-size", type=int, default=128)
    p.add_argument("--n-epochs", type=int, default=10)
    p.add_argument("--learning-rate", type=float, default=3e-4)
    p.add_argument("--ent-coef", type=float, default=0.01)
    p.add_argument("--gamma", type=float, default=0.999)
    p.add_argument("--seed", type=int, default=TRAIN_SEED_BASE)
    p.add_argument("--eval-seed", type=int, default=EVAL_SEED_BASE)
    p.add_argument("--eval-episodes", type=int, default=200, help="Even: half P1, half P2")
    p.add_argument("--eval-every", type=int, default=50_000)
    p.add_argument("--checkpoint-every", type=int, default=200_000)
    p.add_argument("--train-opponent", default="heuristic", choices=["heuristic", "random", "checkpoint"])
    p.add_argument("--eval-opponent", default="checkpoint", choices=["heuristic", "random", "checkpoint"])
    p.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    p.add_argument("--device", default="cpu")
    p.add_argument("--torch-threads", type=int, default=1)
    p.add_argument("--output-dir", type=Path, default=None)
    p.add_argument("--resume", action="store_true", help="Skip runs whose best_model.zip already exists")
    p.add_argument("--tensorboard", action="store_true", default=True)
    p.add_argument("--no-tensorboard", dest="tensorboard", action="store_false")
    p.add_argument("--tensorboard-port", type=int, default=6006)
    return p.parse_args(argv)


def _make_train_env(agent_player, reward_mode, seed, args):
    def _init():
        from sb3_contrib.common.wrappers import ActionMasker

        base = DiceGameEnv2(
            agent_player=agent_player,
            opponent=args.train_opponent,
            reward_mode=reward_mode,
            gamma=args.gamma,
            opponent_kwargs={"checkpoint": args.checkpoint, "device": args.device}
            if args.train_opponent == "checkpoint"
            else None,
        )
        scaled = FixedBoxScaling2(base)
        base._seed_source = random.Random(seed)  # reproducible autoresets
        return ActionMasker(scaled, lambda e: e.action_masks())

    return _init


def _make_eval_env(agent_player, reward_mode, opponent, args):
    base = DiceGameEnv2(
        agent_player=agent_player,
        opponent=opponent,
        reward_mode=reward_mode,
        gamma=args.gamma,
        opponent_kwargs={"checkpoint": args.checkpoint, "device": args.device} if opponent == "checkpoint" else None,
    )
    return FixedBoxScaling2(base)


def _save(model, path: Path) -> None:
    tmp = path.with_name(path.stem + ".tmp.zip")
    model.save(str(tmp))
    os.replace(tmp, path)


def evaluate_model(model, reward_mode: str, eval_seeds: list[tuple[int, int]], opponent: str, args) -> dict[str, Any]:
    """Deterministic evaluation on ``(seed, seat)`` pairs. Returns a metrics dict."""
    envs = {1: _make_eval_env(1, reward_mode, opponent, args), 2: _make_eval_env(2, reward_mode, opponent, args)}
    rows = []
    try:
        for seed, player in eval_seeds:
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
                    "seed": seed,
                    "player": player,
                    "score": scores["agent"],
                    "opponent": scores["adversary"],
                    "fox": int(info["scores_full"][str(player)]["fox_count"]),
                    "min_zone": int(min(env.unwrapped.engine.scores()[player][z] for z in ("yellow", "turquoise", "blue", "brown", "pink"))),
                    "win": int(scores["agent"] > scores["adversary"]),
                    "draw": int(scores["agent"] == scores["adversary"]),
                    "loss": int(scores["agent"] < scores["adversary"]),
                    "zones_completed": zones_completed(board),
                }
            )
    finally:
        for env in envs.values():
            env.close()
    n = len(rows)
    return {
        "episodes": n,
        "win_rate": sum(r["win"] for r in rows) / n,
        "draw_rate": sum(r["draw"] for r in rows) / n,
        "loss_rate": sum(r["loss"] for r in rows) / n,
        "mean_score_agent": float(np.mean([r["score"] for r in rows])),
        "mean_score_opponent": float(np.mean([r["opponent"] for r in rows])),
        "mean_fox_agent": float(np.mean([r["fox"] for r in rows])),
        "mean_min_zone_agent": float(np.mean([r["min_zone"] for r in rows])),
        "mean_zones_completed": float(np.mean([r["zones_completed"] for r in rows])),
    }


def _eval_seeds(base: int, episodes: int) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    for i in range(episodes):
        pairs.append((base + i // 2, 1 + i % 2))
    return pairs


def train_run(index: int, name: str, reward_mode: str, seq_dir: Path, args, start_path: Path | None = None) -> Path:
    from stable_baselines3.common.callbacks import BaseCallback
    from stable_baselines3.common.logger import configure
    from stable_baselines3.common.vec_env import DummyVecEnv
    from sb3_contrib import MaskablePPO

    run_dir = seq_dir / name
    run_dir.mkdir(parents=True, exist_ok=True)
    best_path = run_dir / "best_model.zip"
    if args.resume and best_path.exists():
        print(f"[{name}] best_model.zip exists -> skipped (--resume)")
        return best_path

    seeds = [args.seed + index * 1000 + i for i in range(args.n_envs)]
    train_env = DummyVecEnv([_make_train_env("random", reward_mode, s, args) for s in seeds])
    eval_seeds = _eval_seeds(args.eval_seed, args.eval_episodes)

    if start_path is None:
        model = MaskablePPO(
            "MultiInputPolicy",
            train_env,
            learning_rate=args.learning_rate,
            n_steps=args.n_steps,
            batch_size=args.batch_size,
            n_epochs=args.n_epochs,
            gamma=args.gamma,
            gae_lambda=0.95,
            ent_coef=args.ent_coef,
            clip_range=0.2,
            vf_coef=0.5,
            max_grad_norm=0.5,
            target_kl=0.03,
            policy_kwargs={"net_arch": {"pi": [256, 256], "vf": [256, 256]}},
            seed=args.seed + index,
            device=args.device,
            verbose=1,
        )
        target = args.timesteps
        reset = True
    else:
        model = MaskablePPO.load(str(start_path), env=train_env, device=args.device)
        target = model.num_timesteps + args.timesteps
        reset = False
    model.set_random_seed(args.seed + index)
    formats = ["stdout", "csv"] + (["tensorboard"] if args.tensorboard else [])
    model.set_logger(configure(str(run_dir), formats))

    metrics = evaluate_model(model, reward_mode, eval_seeds, args.eval_opponent, args)
    print(f"[{name}] initial eval: win={metrics['win_rate']:.2%} score={metrics['mean_score_agent']:.1f}")
    # Establish the first best model so every run has a best_model.zip + metrics.
    _save(model, best_path)
    (run_dir / "best_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    class EvalCallback(BaseCallback):
        def __init__(self):
            super().__init__()
            self.last_eval = model.num_timesteps
            self.last_ckpt = model.num_timesteps
            self.best_win = metrics["win_rate"]
            self.best_score = metrics["mean_score_agent"]

        def _step_suffix(self):
            return f"step_{self.num_timesteps:09d}"

        def _maybe_checkpoint(self):
            if self.num_timesteps - self.last_ckpt >= args.checkpoint_every:
                _save(self.model, run_dir / f"checkpoint_{self._step_suffix()}.zip")
                _save(self.model, run_dir / "last_model.zip")
                self.last_ckpt = self.num_timesteps

        def _on_step(self) -> bool:
            self._maybe_checkpoint()
            if self.num_timesteps - self.last_eval >= args.eval_every:
                self.evaluate()
            return True

        def _on_rollout_end(self) -> None:
            buf = getattr(self.model, "ep_info_buffer", None)
            if buf:
                self.logger.record("train/reward_mean", float(np.mean([e["r"] for e in buf])))
                self.logger.record("train/ep_len_mean", float(np.mean([e["l"] for e in buf])))
            vals = self.logger.name_to_value
            for src, dst in (
                ("train/entropy_loss", "train/entropy_loss"),
                ("train/value_loss", "train/value_loss"),
                ("train/policy_gradient_loss", "train/policy_loss"),
            ):
                if src in vals:
                    self.logger.record(dst, vals[src])

        def evaluate(self):
            m = evaluate_model(self.model, reward_mode, eval_seeds, args.eval_opponent, args)
            for key, value in m.items():
                if key != "episodes":
                    self.logger.record("eval/" + key, value)
            self.logger.record("eval/mean_score_agent", m["mean_score_agent"])
            self.logger.dump(self.num_timesteps)
            self.last_eval = self.num_timesteps
            improved = (m["win_rate"], m["mean_score_agent"]) > (self.best_win, self.best_score)
            if improved:
                self.best_win, self.best_score = m["win_rate"], m["mean_score_agent"]
                _save(self.model, best_path)
                (run_dir / "best_metrics.json").write_text(json.dumps(m, indent=2), encoding="utf-8")
            print(
                f"[{name}] step {self.num_timesteps}: win={m['win_rate']:.2%} "
                f"score={m['mean_score_agent']:.1f} fox={m['mean_fox_agent']:.2f}",
                flush=True,
            )

        def _on_training_end(self) -> None:
            self.evaluate()
            _save(self.model, run_dir / "last_model.zip")
            if not best_path.exists():
                _save(self.model, best_path)

    print(f"[{name}] training to {target} timesteps (reward: {describe(reward_mode)})", flush=True)
    model.learn(total_timesteps=target, callback=EvalCallback(), reset_num_timesteps=reset, use_masking=True)
    _save(model, run_dir / "last_model.zip")
    if not best_path.exists():
        _save(model, best_path)

    metadata = {
        "run": name,
        "reward_mode": reward_mode,
        "reward_formula": describe(reward_mode),
        "timesteps_this_run": args.timesteps,
        "num_timesteps_end": model.num_timesteps,
        "rules_version": RULES_VERSION,
        "observation_version": OBSERVATION_VERSION_2,
        "action_version": ACTION_VERSION_2,
        "n_actions": N_ACTIONS_2,
        "gamma": args.gamma,
        "hyperparameters": {
            "n_envs": args.n_envs,
            "n_steps": args.n_steps,
            "batch_size": args.batch_size,
            "n_epochs": args.n_epochs,
            "learning_rate": args.learning_rate,
            "ent_coef": args.ent_coef,
            "net_arch": [256, 256],
        },
        "train_opponent": args.train_opponent,
        "eval_opponent": args.eval_opponent,
        "checkpoint_used_as_opponent": str(args.checkpoint),
        "train_seeds": seeds,
        "eval_seeds": {"base": args.eval_seed, "episodes": args.eval_episodes},
        "created": datetime.now(timezone.utc).isoformat(),
    }
    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    train_env.close()
    return best_path


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    import torch

    torch.set_num_threads(args.torch_threads)

    seq_dir = args.output_dir or Path("runs") / ("sequence_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"))
    seq_dir.mkdir(parents=True, exist_ok=True)
    (seq_dir / "sequence_config.json").write_text(
        json.dumps({**vars(args), "output_dir": str(seq_dir), "checkpoint": str(args.checkpoint)}, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"Sequence dir: {seq_dir.resolve()}")

    start_path = None
    for index, (name, reward_mode) in enumerate(RUNS, start=1):
        start_path = train_run(index, name, reward_mode, seq_dir, args, start_path=start_path)

    report = Path(__file__).with_name("report.py")
    if report.exists():
        subprocess.run(
            [
                sys.executable,
                str(report),
                "--sequence",
                str(seq_dir),
                "--eval-seed",
                str(args.eval_seed),
                "--eval-episodes",
                str(args.eval_episodes),
                "--checkpoint",
                str(args.checkpoint),
                "--device",
                args.device,
            ],
            check=False,
        )

    if args.tensorboard:
        print(f"TensorBoard: tensorboard --logdir {seq_dir.resolve()}")
        try:
            subprocess.Popen(
                ["tensorboard", "--logdir", str(seq_dir), "--port", str(args.tensorboard_port)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            print(f"TensorBoard lancé : http://localhost:{args.tensorboard_port}")
        except FileNotFoundError:
            print("tensorboard introuvable ; lancer la commande manuellement.")


if __name__ == "__main__":
    main()
