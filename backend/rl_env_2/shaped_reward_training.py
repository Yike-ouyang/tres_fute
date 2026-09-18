import marimo

__generated_with = "0.24.2"
app = marimo.App(width="full")


@app.cell
def _(mo):
    mo.md("""
    # Entraînement shaped-reward — Δ(min_zone), PBRS, variance

    Trois variantes alternatives de reward, chacune repartant du **meilleur
    modèle du run `solo_score_delta`**.

    | Run | Terme ajouté à `Δ(score)/100` |
    |-----|-------------------------------|
    | `min_zone` | `α · Δ(min_zone_agent)` |
    | `pbrs`     | `γ · Φ(s') − Φ(s)` avec `Φ(s) = φ · fox_count · min_zone` |
    | `variance` | `−β · Δ(var(zones_agent))` |

    **L'entraînement n'est pas lancé automatiquement** : il démarre quand tu
    cliques sur le bouton, dans **trois sous-processus détachés en parallèle**
    (un par variante, `2 M` pas chacun à partir du même checkpoint) :

    - pas de timeout de cellule, kernel marimo réactif,
    - survit à la fermeture du navigateur ou au redémarrage de marimo,
    - les cellules de monitoring relisent les fichiers à la demande.
    """)
    return


@app.cell
def _():
    import os
    import sys
    import json
    import time
    import textwrap
    import signal
    import subprocess
    from pathlib import Path
    from datetime import datetime, timezone
    import marimo as mo

    return Path, datetime, json, mo, subprocess, sys, textwrap, timezone


@app.cell
def _(Path, sys):
    here = Path.cwd().resolve()
    backend = here
    while backend.name != "backend" and backend.parent != backend:
        backend = backend.parent
    if backend.name != "backend":
        if (here / "rl_env_2").exists():
            backend = here
        else:
            raise RuntimeError(f"Impossible de trouver backend/ depuis {here}")
    sys.path.insert(0, str(backend))
    return (backend,)


@app.cell
def _(backend, datetime, timezone):
    CONFIG = {
        # Env
        "timesteps_per_run": 2_000_000,
        "n_envs": 4,
        "n_steps": 2048,
        # PPO
        "batch_size": 128,
        "n_epochs": 10,
        "learning_rate": 3e-4,
        "ent_coef": 0.01,
        "gamma": 0.999,
        # Shaping weights
        "alpha": 0.05,        # min_zone
        "beta": 0.01,         # variance
        "phi_scale": 0.01,    # PBRS potential
        # Seeds / eval
        "seed": 42,
        "eval_seed": 1_000_000,
        "eval_episodes": 200,
        "eval_every": 50_000,
        "checkpoint_every": 200_000,
        # Runtime
        "device": "cpu",
        "torch_threads": 1,
    }

    POLICY_KWARGS = {"net_arch": {"pi": [256, 256], "vf": [256, 256]}}

    OUTPUT_DIR = backend / "runs" / (
        "shaped_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG, OUTPUT_DIR, POLICY_KWARGS


@app.cell
def _(backend):
    candidates = sorted(
        (backend / "runs").glob("solo_*/score_delta_solo/best_model.zip"),
        key=lambda p: p.stat().st_mtime,
    )
    if not candidates:
        raise FileNotFoundError(
            "Aucun best_model.zip sous runs/solo_*/score_delta_solo/. "
            "Lance d'abord train_solo_score_delta.py."
        )
    SOLO_BEST = candidates[-1]
    return (SOLO_BEST,)


@app.cell
def _(OUTPUT_DIR, SOLO_BEST, mo):
    mo.md(f"""
    - **Checkpoint de départ** : `{SOLO_BEST}`
    - **Dossier de sortie**   : `{OUTPUT_DIR}`
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Détail des rewards

    Toutes les variantes **incluent** la récompense de base `Δ(score)/100`
    (mode `score_delta_normalized`). On ajoute un terme de shaping à chaque pas.

    ### 1. `min_zone`
    r = Δ(score)/100 + α · Δ(min_zone_agent)
    Dense (à chaque progression de la zone la plus faible), peut être négatif.
    Pousse l'agent à équilibrer son plateau sans attendre le renard.

    ### 2. `pbrs` — potential-based reward shaping
    Φ(s) = φ · fox_count(s) · min_zone(s)
    r = Δ(score)/100 + γ · Φ(s') − Φ(s)
    Shaping théoriquement non biaisé (Ng, Harada, Russell 1999). La politique
    optimale est **inchangée** ; l'agent est seulement guidé vers les états à
    fort potentiel renard. `φ = 0.01` ramène Φ sur la même échelle que le reward
    de base (~0.01–0.1 par pas).

    ### 3. `variance`
    r = Δ(score)/100 − β · Δ(var(zones_agent))
    Pénalise la dispersion entre les 5 zones. L'agent apprend à garder un
    plateau équilibré, ce qui augmente mécaniquement `min_zone` — donc la
    valeur des renards — sans coder le renard en dur.
    """)
    return


@app.cell
def _(POLICY_KWARGS, mo):
    mo.md(f"""
    ### Politique MaskablePPO

    - `MultiInputPolicy` (Dict d'observations → logits masqués)
    - `net_arch = {POLICY_KWARGS['net_arch']}`
    - `features_extractor` : défaut SB3 (MultiInput, NatureCNN désactivé)
    - masque appliqué dans la distribution catégorielle
    """)
    return


@app.cell
def _(textwrap):
    TRAINING_SCRIPT = textwrap.dedent('''
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
        (run_dir / "run_config.json").write_text(
            json.dumps({**vars(args), "start_from": str(args.start_from),
                        "output_dir": str(args.output_dir),
                        "checkpoint": str(args.checkpoint)}, indent=2, default=str),
            encoding="utf-8",
        )
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
        # reset_num_timesteps=False : SB3 ajoute lui-même le compteur courant
        # (``total_timesteps += self.num_timesteps`` dans _setup_learn). On passe
        # donc le nombre de pas *additionnels* pour obtenir exactement
        # ``args.timesteps`` pas de plus (sinon le compteur est compté deux fois).
        model.learn(total_timesteps=args.timesteps, callback=EvalCallback(),
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
        print(f"Run dir: {args.output_dir.resolve()}", flush=True)

        for mode in modes:
            run_dir = args.output_dir / f"run_{mode}"
            print(f"\\n===== Run {mode} =====", flush=True)
            train_run(mode, run_dir, args)


    if __name__ == "__main__":
        main()
    ''').strip()
    return (TRAINING_SCRIPT,)


@app.cell
def _(TRAINING_SCRIPT, backend):
    SCRIPT_PATH = backend / "rl_env_2" / "train_shaped.py"
    SCRIPT_PATH.write_text(TRAINING_SCRIPT, encoding="utf-8")
    SCRIPT_PATH.chmod(0o755)
    return (SCRIPT_PATH,)


@app.cell
def _(SCRIPT_PATH, mo):
    mo.md(f"""
    Script écrit : `{SCRIPT_PATH}`
    """)
    return


@app.cell
def _(CONFIG, mo):
    RUN_TRAINING = mo.ui.run_button(
        label=f"Lancer l'entraînement (3 × {CONFIG['timesteps_per_run']:,} pas, en parallèle)"
    )
    mo.md(
        f"""
        ### Lancement manuel

        {RUN_TRAINING}

        Aucun entraînement ne démarre à l'ouverture du notebook : clique sur le
        bouton pour lancer les runs `min_zone`, `pbrs` et `variance` **en
        parallèle** ({CONFIG['timesteps_per_run']:,} pas chacun).
        """
    )
    return (RUN_TRAINING,)


@app.cell
def _(
    CONFIG,
    OUTPUT_DIR,
    POLICY_KWARGS,
    RUN_TRAINING,
    SCRIPT_PATH,
    SOLO_BEST,
    json,
    mo,
    subprocess,
    sys,
):
    mo.stop(not RUN_TRAINING.value, mo.md("_Entraînement non lancé._"))

    _base_cmd = [
        sys.executable, "-u", str(SCRIPT_PATH),
        "--start-from", str(SOLO_BEST),
        "--output-dir", str(OUTPUT_DIR),
        "--timesteps", str(CONFIG["timesteps_per_run"]),
        "--n-envs", str(CONFIG["n_envs"]),
        "--n-steps", str(CONFIG["n_steps"]),
        "--batch-size", str(CONFIG["batch_size"]),
        "--n-epochs", str(CONFIG["n_epochs"]),
        "--learning-rate", str(CONFIG["learning_rate"]),
        "--ent-coef", str(CONFIG["ent_coef"]),
        "--gamma", str(CONFIG["gamma"]),
        "--alpha", str(CONFIG["alpha"]),
        "--beta", str(CONFIG["beta"]),
        "--phi-scale", str(CONFIG["phi_scale"]),
        "--seed", str(CONFIG["seed"]),
        "--eval-seed", str(CONFIG["eval_seed"]),
        "--eval-episodes", str(CONFIG["eval_episodes"]),
        "--eval-every", str(CONFIG["eval_every"]),
        "--checkpoint-every", str(CONFIG["checkpoint_every"]),
        "--device", CONFIG["device"],
        "--torch-threads", str(CONFIG["torch_threads"]),
        "--policy-kwargs", json.dumps(POLICY_KWARGS),
    ]
    PROCS = {}
    LOG_PATHS = {}
    for _mode in ("min_zone", "pbrs", "variance"):
        _log_path = OUTPUT_DIR / f"training_{_mode}.log"
        LOG_PATHS[_mode] = _log_path
        _log = open(_log_path, "w")
        PROCS[_mode] = subprocess.Popen(
            _base_cmd + ["--modes", _mode],
            stdout=_log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,   # détache du groupe de processus marimo
        )
    return LOG_PATHS, PROCS


@app.cell
def _(LOG_PATHS, OUTPUT_DIR, PROCS, mo):
    _lines = []
    for _mode, _proc in PROCS.items():
        _state = "**en cours**" if _proc.poll() is None else f"**terminé** (exit={_proc.returncode})"
        _lines.append(f"- `{_mode}` : PID **{_proc.pid}** — {_state} — log `{LOG_PATHS[_mode].name}`")
    _body = "\n".join(_lines)
    mo.md(f"""
    ### Entraînement lancé (3 variantes en parallèle)

    {_body}

    - Sortie TensorBoard : `{OUTPUT_DIR}`

    Les processus tournent indépendamment de marimo. Fermer l'onglet ou
    redémarrer le serveur ne les arrête pas.
    """)
    return


@app.cell
def _(mo):
    RUN_TENSORBOARD = mo.ui.run_button(label="Lancer TensorBoard (port 6006)")
    mo.md(f"### TensorBoard\n\n{RUN_TENSORBOARD}")
    return (RUN_TENSORBOARD,)


@app.cell
def _(OUTPUT_DIR, RUN_TENSORBOARD, mo, subprocess):
    mo.stop(not RUN_TENSORBOARD.value, mo.md("_TensorBoard non lancé._"))

    TB_PORT = 6006
    try:
        TB_PROC = subprocess.Popen(
            ["tensorboard", "--logdir", str(OUTPUT_DIR),
             "--port", str(TB_PORT), "--host", "0.0.0.0"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        TB_URL = f"http://localhost:{TB_PORT}"
    except FileNotFoundError:
        TB_PROC = None
        TB_URL = "(tensorboard introuvable — pip install tensorboard)"
    return (TB_URL,)


@app.cell
def _(TB_URL, mo):
    mo.md(f"""
    ### TensorBoard\n\nOuvre **{TB_URL}** dans un navigateur.
    """)
    return


@app.cell
def _(OUTPUT_DIR, json, mo):
    def _read_metrics(mode: str):
        path = OUTPUT_DIR / f"run_{mode}" / "best_metrics.json"
        if path.exists():
            return json.loads(path.read_text())
        return None

    def _last_log_lines(mode: str, n: int = 6):
        log = OUTPUT_DIR / f"training_{mode}.log"
        if not log.exists():
            return []
        with log.open("r", errors="replace") as f:
            lines = f.readlines()
        return [line.rstrip() for line in lines[-n:]]

    rows = []
    tails = []
    for mode in ("min_zone", "pbrs", "variance"):
        m = _read_metrics(mode)
        if m:
            rows.append(
                f"| `{mode}` | {m['win_rate']:.2%} | {m['draw_rate']:.2%} | "
                f"{m['mean_score_agent']:.1f} | {m['mean_score_opponent']:.1f} | "
                f"{m['mean_fox_agent']:.2f} | {m['mean_min_zone_agent']:.1f} | "
                f"{m.get('mean_zones_completed', 0):.2f} |"
            )
        else:
            rows.append(f"| `{mode}` | — | — | — | — | — | — | — |")
        lines = _last_log_lines(mode)
        block = "\n".join(f"    {line}" for line in lines) or "    (log vide)"
        tails.append(f"**{mode}**\n```\n{block}\n```")

    table = (
        "| Run | win | draw | score | opp | fox | min_zone | zones_compl |\n"
        "|-----|-----|------|-------|-----|-----|----------|-------------|\n"
        + "\n".join(rows)
    )
    logs = "\n\n".join(tails)

    mo.md(
        f"""
        ### Métriques (dernier best connu par run)

        {table}

        ### Dernières lignes de log (par variante)

        {logs}
        """
    )
    return


if __name__ == "__main__":
    app.run()
