"""Shaped-reward training for rl_env_2 (launched by the marimo notebook).

Three alternative shaping variants on top of score_delta_normalized:
  * min_zone : r += alpha * Δ(min_zone_agent)
  * pbrs     : r += gamma * Φ(s') - Φ(s), Φ = phi_scale * fox * min_zone
  * variance : r -= beta * Δ(var(zones_agent))
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from game_engine.types import RULES_VERSION
from rl_env_2 import (
    ACTION_VERSION_2, N_ACTIONS_2, OBSERVATION_VERSION_2, DiceGameEnv2,
)
from rl_env_2.observations import zones_completed
from rl_env_2.opponents import DEFAULT_CHECKPOINT
from rl_env_2.wrappers import FixedBoxScaling2

ZONES = ("yellow", "turquoise", "blue", "brown", "pink")
MODES = ("min_zone", "pbrs", "variance")


# -----------------------------------------------------------------
# Environnement avec reward shaped
# -----------------------------------------------------------------
class ShapedEnv(DiceGameEnv2):
    """DiceGameEnv2 + shaping additif sur score_delta_normalized."""

    def __init__(self, *args, shaped_mode: str, alpha: float,
                 beta: float, phi_scale: float, **kwargs):
        super().__init__(*args, reward_mode="score_delta_normalized", **kwargs)
        self.shaped_mode = shaped_mode
        self.alpha = alpha
        self.beta = beta
        self.phi_scale = phi_scale
        self._prev_min: float | None = None
        self._prev_phi: float | None = None
        self._prev_var: float | None = None

    def _read_state(self, info: dict) -> tuple[int, float, float, float]:
        player = info.get("agent_player", self.agent_player)
        if not isinstance(player, int):
            raise RuntimeError(
                f"Impossible de determiner le siège de l'agent: "
                f"info['agent_player']={info.get('agent_player')}, "
                f"self.agent_player={self.agent_player}"
            )
        scores = self.engine.scores()[player]
        zones = [scores[z] for z in ZONES]
        min_zone = float(min(zones))
        fox_count = int(info["scores_full"][str(player)]["fox_count"])
        variance = float(np.var(zones))
        phi = self.phi_scale * fox_count * min_zone
        return player, min_zone, phi, variance

    def reset(self, **kwargs):
        obs, info = super().reset(**kwargs)
        _, self._prev_min, self._prev_phi, self._prev_var = self._read_state(info)
        return obs, info

    def step(self, action):
        obs, base_reward, term, trunc, info = super().step(action)
        _, new_min, new_phi, new_var = self._read_state(info)

        if self.shaped_mode == "min_zone":
            extra = self.alpha * (new_min - self._prev_min)
        elif self.shaped_mode == "pbrs":
            extra = self.gamma * new_phi - self._prev_phi
        elif self.shaped_mode == "variance":
            extra = -self.beta * (new_var - self._prev_var)
        else:
            extra = 0.0

        reward = float(base_reward) + float(extra)

        self._prev_min = new_min
        self._prev_phi = new_phi
        self._prev_var = new_var
        if term or trunc:
            self._prev_min = self._prev_phi = self._prev_var = None

        info["shaped_extra"] = float(extra)
        info["shaped_min_zone"] = new_min
        info["shaped_phi"] = new_phi
        info["shaped_variance"] = new_var
        return obs, reward, term, trunc, info


# -----------------------------------------------------------------
# CLI
# -----------------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--timesteps", type=int, default=2_000_000)
    p.add_argument("--n-envs", type=int, default=4)
    p.add_argument("--n-steps", type=int, default=2048)
    p.add_argument("--batch-size", type=int, default=128)
    p.add_argument("--n-epochs", type=int, default=10)
    p.add_argument("--learning-rate", type=float, default=3e-4)
    p.add_argument("--ent-coef", type=float, default=0.01)
    p.add_argument("--gamma", type=float, default=0.999)
    p.add_argument("--alpha", type=float, default=0.05)
    p.add_argument("--beta", type=float, default=0.01)
    p.add_argument("--phi-scale", type=float, default=0.01)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--eval-seed", type=int, default=1_000_000)
    p.add_argument("--eval-episodes", type=int, default=200)
    p.add_argument("--eval-every", type=int, default=50_000)
    p.add_argument("--checkpoint-every", type=int, default=200_000)
    p.add_argument("--start-from", type=Path, required=True)
    p.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    p.add_argument("--device", default="cpu")
    p.add_argument("--torch-threads", type=int, default=1)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--modes", default="min_zone,pbrs,variance")
    p.add_argument("--policy-kwargs", default='{"net_arch": {"pi": [256, 256], "vf": [256, 256]}}')
    p.add_argument("--tensorboard", action="store_true", default=True)
    return p.parse_args()


# -----------------------------------------------------------------
# Fabrication des envs
# -----------------------------------------------------------------
def _make_train_env(seed: int, mode: str, args):
    def _init():
        from sb3_contrib.common.wrappers import ActionMasker

        base = ShapedEnv(
            agent_player="random",
            opponent="checkpoint",
            gamma=args.gamma,
            shaped_mode=mode,
            alpha=args.alpha,
            beta=args.beta,
            phi_scale=args.phi_scale,
            opponent_kwargs={"checkpoint": args.checkpoint, "device": args.device},
        )
        base._seed_source = random.Random(seed)
        scaled = FixedBoxScaling2(base)
        return ActionMasker(scaled, lambda e: e.action_masks())
    return _init


def _make_eval_env(mode: str, args, player: int):
    """Fixed seat: half the eval seeds are played as P1, half as P2."""
    base = ShapedEnv(
        agent_player=player,
        opponent="checkpoint",
        gamma=args.gamma,
        shaped_mode=mode,
        alpha=args.alpha,
        beta=args.beta,
        phi_scale=args.phi_scale,
        opponent_kwargs={"checkpoint": args.checkpoint, "device": args.device},
    )
    return FixedBoxScaling2(base)


# -----------------------------------------------------------------
# Evaluation
# -----------------------------------------------------------------
def _eval_seeds(base: int, episodes: int):
    return [(base + i // 2, 1 + i % 2) for i in range(episodes)]


def _save(model, path: Path) -> None:
    tmp = path.with_name(path.stem + ".tmp.zip")
    model.save(str(tmp))
    os.replace(tmp, path)


def evaluate_model(model, mode: str, eval_seeds, args) -> dict[str, Any]:
    envs = {1: _make_eval_env(mode, args, 1), 2: _make_eval_env(mode, args, 2)}
    rows: list[dict[str, Any]] = []
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
            board = env.env.engine.state["boards"][player]
            rows.append({
                "seed": seed,
                "player": player,
                "score": scores["agent"],
                "opponent": scores["adversary"],
                "fox": int(info["scores_full"][str(player)]["fox_count"]),
                "min_zone": int(min(
                    env.env.engine.scores()[player][z] for z in ZONES
                )),
                "win": int(scores["agent"] > scores["adversary"]),
                "draw": int(scores["agent"] == scores["adversary"]),
                "loss": int(scores["agent"] < scores["adversary"]),
                "zones_completed": zones_completed(board),
            })
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


# -----------------------------------------------------------------
# Boucle d'un run
# -----------------------------------------------------------------
def train_run(mode: str, run_dir: Path, args):
    from stable_baselines3.common.callbacks import BaseCallback
    from stable_baselines3.common.logger import configure
    from stable_baselines3.common.vec_env import DummyVecEnv
    from sb3_contrib import MaskablePPO

    run_dir.mkdir(parents=True, exist_ok=True)
    best_path = run_dir / "best_model.zip"
    last_path = run_dir / "last_model.zip"

    seeds = [args.seed + i for i in range(args.n_envs)]
    train_env = DummyVecEnv([_make_train_env(s, mode, args) for s in seeds])
    eval_seeds = _eval_seeds(args.eval_seed, args.eval_episodes)

    # Resume always from the provided start checkpoint (solo delta best).
    model = MaskablePPO.load(str(args.start_from), env=train_env, device=args.device)
    reset = False

    model.set_random_seed(args.seed)
    formats = ["stdout", "csv"] + (["tensorboard"] if args.tensorboard else [])
    model.set_logger(configure(str(run_dir), formats))

    metrics = evaluate_model(model, mode, eval_seeds, args)
    print(f"[{mode}] initial: win={metrics['win_rate']:.2%} score={metrics['mean_score_agent']:.1f}", flush=True)
    _save(model, best_path)
    (run_dir / "best_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    class EvalCallback(BaseCallback):
        def __init__(self):
            super().__init__()
            self.last_eval = model.num_timesteps
            self.last_ckpt = model.num_timesteps
            self.best_win = metrics["win_rate"]
            self.best_score = metrics["mean_score_agent"]

        def _maybe_ckpt(self):
            if self.num_timesteps - self.last_ckpt >= args.checkpoint_every:
                _save(self.model, run_dir / f"checkpoint_step_{self.num_timesteps:09d}.zip")
                _save(self.model, last_path)
                self.last_ckpt = self.num_timesteps

        def _on_step(self) -> bool:
            self._maybe_ckpt()
            if self.num_timesteps - self.last_eval >= args.eval_every:
                self.evaluate()
            return True

        def _on_rollout_end(self):
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
            m = evaluate_model(self.model, mode, eval_seeds, args)
            for k, v in m.items():
                if k != "episodes":
                    self.logger.record("eval/" + k, v)
            self.logger.dump(self.num_timesteps)
            self.last_eval = self.num_timesteps
            improved = (m["win_rate"], m["mean_score_agent"]) > (self.best_win, self.best_score)
            if improved:
                self.best_win, self.best_score = m["win_rate"], m["mean_score_agent"]
                _save(self.model, best_path)
                (run_dir / "best_metrics.json").write_text(json.dumps(m, indent=2), encoding="utf-8")
            print(f"[{mode}] step {self.num_timesteps}: win={m['win_rate']:.2%} "
                  f"score={m['mean_score_agent']:.1f} fox={m['mean_fox_agent']:.2f} "
                  f"minz={m['mean_min_zone_agent']:.1f}", flush=True)

        def _on_training_end(self):
            self.evaluate()
            _save(self.model, last_path)
            if not best_path.exists():
                _save(self.model, best_path)

    target = model.num_timesteps + args.timesteps
    print(f"[{mode}] training to {target} (from {args.start_from})", flush=True)
    model.learn(total_timesteps=target, callback=EvalCallback(),
                reset_num_timesteps=reset, use_masking=True)
    _save(model, last_path)

    metadata = {
        "mode": mode,
        "start_from": str(args.start_from),
        "timesteps_requested": args.timesteps,
        "num_timesteps_end": model.num_timesteps,
        "rules_version": RULES_VERSION,
        "observation_version": OBSERVATION_VERSION_2,
        "action_version": ACTION_VERSION_2,
        "n_actions": N_ACTIONS_2,
        "gamma": args.gamma,
        "alpha": args.alpha, "beta": args.beta, "phi_scale": args.phi_scale,
        "policy_kwargs": json.loads(args.policy_kwargs),
        "hyperparameters": {
            "n_envs": args.n_envs, "n_steps": args.n_steps,
            "batch_size": args.batch_size, "n_epochs": args.n_epochs,
            "learning_rate": args.learning_rate, "ent_coef": args.ent_coef,
        },
        "opponent": {"kind": "checkpoint", "path": str(args.checkpoint),
                     "used_for": ["training", "evaluation"]},
        "train_seeds": seeds,
        "eval_seeds": {"base": args.eval_seed, "episodes": args.eval_episodes},
        "created": datetime.now(timezone.utc).isoformat(),
    }
    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    train_env.close()
    return best_path


# -----------------------------------------------------------------
# Main
# -----------------------------------------------------------------
def main():
    args = parse_args()
    import torch
    torch.set_num_threads(args.torch_threads)

    if not args.start_from.exists():
        raise FileNotFoundError(f"start_from introuvable: {args.start_from}")
    if not args.checkpoint.exists():
        raise FileNotFoundError(f"checkpoint adversaire introuvable: {args.checkpoint}")

    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    for m in modes:
        if m not in MODES:
            raise ValueError(f"Mode inconnu: {m}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "run_config.json").write_text(
        json.dumps({**vars(args), "start_from": str(args.start_from),
                    "output_dir": str(args.output_dir),
                    "checkpoint": str(args.checkpoint)}, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"Run dir: {args.output_dir.resolve()}", flush=True)

    for mode in modes:
        run_dir = args.output_dir / f"run_{mode}"
        print(f"\n===== Run {mode} =====", flush=True)
        train_run(mode, run_dir, args)


if __name__ == "__main__":
    main()