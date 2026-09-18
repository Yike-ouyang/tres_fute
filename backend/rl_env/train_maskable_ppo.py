#!/usr/bin/env python3
"""Entraîner MaskablePPO sur le DiceGameEnv complet, sans HTTP.

Installation (dans le venv du backend):
    python -m pip install sb3-contrib stable-baselines3 gymnasium numpy torch
    # Optionnel pour --tensorboard : python -m pip install tensorboard

Placer ce fichier dans backend/rl_env/train_maskable_ppo.py, puis depuis backend:
    python rl_env/train_maskable_ppo.py --total-timesteps 1000000
    python rl_env/train_maskable_ppo.py --total-timesteps 1024 --n-envs 1 \
        --n-steps 128 --batch-size 64 --eval-episodes 4 --eval-every 1024
    python rl_env/train_maskable_ppo.py --resume runs/ppo_XXX/latest.zip \
        --total-timesteps 500000 --seed 43

--total-timesteps = transitions agent supplémentaires (arrondies au rollout).
PPO: gamma=1, score_delta/100, MLP 256x256, adversaire heuristique par défaut.
Ce sont des valeurs de départ à comparer, pas des hyperparamètres optimisés.

Les Box sont ramenés à [0, 1] par leurs bornes fixes, sans clipping. Les catégories
codées en Box restent scalaires; un encodage one-hot pourra être comparé ensuite.
Pas de VecNormalize : aucune statistique mobile supplémentaire à sauvegarder.

Évaluation déterministe masquée sur un ensemble fixe de graines, équilibrée P1/P2.
best_model.zip maximise le score final moyen personnel, et non le taux de victoire.
Ces graines servent à sélectionner le modèle: prévoir un autre ensemble de test.

Reprise: poids, optimiseur et compteurs SB3 restaurés; nouvelles parties et nouveau
rollout. Pas de reprise bit à bit des RNG, parties ou collecte interrompue. Les
hyperparamètres PPO du checkpoint sont conservés; les flags PPO ne les remplacent
pas. Les métadonnées intégrées vérifient règles/actions/observations/prétraitement.

L'environnement réel et le moteur doivent être présents dans le projet. Le README
mentionne pink_values <= 12: vérifier la borne réelle (un 6 x 3 peut valoir 18).
Ce script n'altère jamais les règles ni les observations hors bornes.
"""

from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--total-timesteps', type=int, default=1_000_000)
    p.add_argument('--n-envs', type=int, default=4, help='DummyVecEnv: instances séquentielles, pas de multiprocessing')
    p.add_argument('--n-steps', type=int, default=256, help='Transitions par environnement et rollout')
    p.add_argument('--batch-size', type=int, default=256)
    p.add_argument('--n-epochs', type=int, default=10)
    p.add_argument('--learning-rate', type=float, default=3e-4)
    p.add_argument('--gamma', type=float, default=1.0)
    p.add_argument('--gae-lambda', type=float, default=0.95)
    p.add_argument('--ent-coef', type=float, default=0.01)
    p.add_argument('--target-kl', type=float, default=0.03)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--agent-player', choices=['1', '2', 'random'], default='random')
    p.add_argument('--opponent', choices=['heuristic', 'random'], default='heuristic')
    p.add_argument('--reward-mode', choices=['score_delta', 'terminal_score'], default='score_delta')
    p.add_argument('--reward-scale', type=float, default=100.0)
    p.add_argument('--device', default='cpu', help='cpu recommandé pour ce premier MLP; cuda possible')
    p.add_argument('--torch-threads', type=int, default=1)
    p.add_argument('--eval-every', type=int, default=25_000, help='Transitions; exécuté entre les rollouts')
    p.add_argument('--eval-episodes', type=int, default=40, help='Nombre pair: moitié P1, moitié P2')
    p.add_argument('--eval-seed', type=int, default=1_000_000)
    p.add_argument('--checkpoint-every', type=int, default=50_000)
    p.add_argument('--keep-checkpoints', type=int, default=3)
    p.add_argument('--episode-guard', type=int, default=10_000, help='Garde de diagnostic, lève une erreur au lieu de tronquer')
    p.add_argument('--tensorboard', action='store_true')
    p.add_argument('--output-dir', type=Path, default=None, help='Nouveau dossier vide; un run existant ne sera pas écrasé')
    p.add_argument('--resume', type=Path, default=None, help='Checkpoint de confiance produit par ce script')
    a = p.parse_args(argv)
    for key in ('total_timesteps', 'n_envs', 'n_steps', 'batch_size', 'n_epochs',
                'torch_threads', 'eval_every', 'eval_episodes', 'checkpoint_every',
                'keep_checkpoints', 'episode_guard'):
        if getattr(a, key) <= 0:
            p.error(f'--{key.replace("_", "-")} doit être strictement positif')
    if a.eval_episodes % 2:
        p.error('--eval-episodes doit être pair pour équilibrer les places')
    if a.seed < 0 or a.eval_seed < 0:
        p.error('Les graines doivent être positives ou nulles')
    for key in ('reward_scale', 'learning_rate', 'target_kl'):
        if not math.isfinite(getattr(a, key)) or getattr(a, key) <= 0:
            p.error(f'{key} doit être fini et strictement positif')
    if not 0 < a.gamma <= 1 or not 0 <= a.gae_lambda <= 1 or not math.isfinite(a.ent_coef) or a.ent_coef < 0:
        p.error('gamma dans ]0,1], gae-lambda dans [0,1], ent-coef fini >= 0')
    if not a.resume and (a.batch_size < 2 or a.n_envs * a.n_steps % a.batch_size):
        p.error('batch-size >= 2 et doit diviser n-envs * n-steps')
    return a


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding='utf-8')


def append_csv(path: Path, row: dict[str, Any]) -> None:
    exists = path.exists()
    with path.open('a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(row))
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    # Imports différés : --help fonctionne même avant installation des dépendances.
    try:
        import gymnasium as gym
        import numpy as np
        import torch
        from sb3_contrib import MaskablePPO
        from stable_baselines3.common.callbacks import BaseCallback
        from stable_baselines3.common.logger import configure
        from stable_baselines3.common.monitor import Monitor
        from stable_baselines3.common.vec_env import DummyVecEnv
    except ImportError as exc:
        raise SystemExit('Dépendance manquante. Installer : python -m pip install '
                         'sb3-contrib stable-baselines3 gymnasium numpy torch\n' + str(exc)) from exc

    # Accepte backend/rl_env/train_maskable_ppo.py ou backend/train_maskable_ppo.py.
    for root in (Path.cwd(), Path(__file__).resolve().parent, Path(__file__).resolve().parents[1]):
        if (root / 'rl_env' / '__init__.py').exists():
            sys.path.insert(0, str(root))
            break
    try:
        from rl_env import ACTION_VERSION, N_ACTIONS, OBSERVATION_VERSION, DiceGameEnv
        from rl_env.wrappers import FixedBoxScaling
    except ImportError as exc:
        raise SystemExit('Placer le script dans backend/rl_env/ et le lancer depuis backend.\n' + str(exc)) from exc

    torch.set_num_threads(args.torch_threads)
    if args.tensorboard:
        try:
            import tensorboard  # noqa: F401
        except ImportError as exc:
            raise SystemExit('Installer tensorboard ou retirer --tensorboard.') from exc

    def new_env(player):
        return FixedBoxScaling(DiceGameEnv(
            agent_player=player, opponent=args.opponent,
            reward_mode=args.reward_mode, reward_scale=args.reward_scale, max_steps=None,
        ))

    # Métadonnées et vérification initiale; aucune action aléatoire non masquée.
    probe = new_env(1)
    try:
        obs, initial_info = probe.reset(seed=args.seed)
        probe.action_masks()
        if probe.action_space.n != N_ACTIONS:
            raise ValueError('N_ACTIONS ne correspond pas à action_space')
        def describe(space):
            if isinstance(space, gym.spaces.Dict):
                return {k: describe(v) for k, v in space.spaces.items()}
            result = {'type': type(space).__name__, 'shape': list(space.shape), 'dtype': str(space.dtype)}
            if isinstance(space, gym.spaces.Box):
                result.update(low=space.low.tolist(), high=space.high.tolist())
            elif isinstance(space, gym.spaces.MultiDiscrete):
                result.update(nvec=space.nvec.tolist(), start=space.start.tolist())
            elif isinstance(space, gym.spaces.Discrete):
                result.update(n=int(space.n), start=int(space.start))
            return result
        compatibility = {
            'rules_version': initial_info['rules_version'],
            'action_version': ACTION_VERSION, 'observation_version': OBSERVATION_VERSION,
            'n_actions': N_ACTIONS, 'raw_observation_space': describe(probe.raw_space),
            'preprocessing': 'fixed_box_scaling_v1',
            'opponent': args.opponent, 'agent_player': args.agent_player,
            'reward_mode': args.reward_mode, 'reward_scale': args.reward_scale,
        }
    finally:
        probe.close()

    run = args.output_dir or Path('runs') / ('ppo_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f'))
    if run.exists() and any(run.iterdir()):
        raise ValueError(f'Le dossier doit être vide ou nouveau: {run}')
    run.mkdir(parents=True, exist_ok=True)
    (run / 'checkpoints').mkdir(exist_ok=True)
    train_player = args.agent_player if args.agent_player == 'random' else int(args.agent_player)
    train_env = DummyVecEnv([
        lambda i=i: Monitor(new_env(train_player), str(run / f'train_{i}.monitor.csv'))
        for i in range(args.n_envs)
    ])
    eval_envs = {}
    model = None
    try:
        eval_envs = {1: new_env(1), 2: new_env(2)}
        if args.resume:
            model = MaskablePPO.load(str(args.resume), env=train_env, device=args.device)
            old = getattr(model, 'dice_training_metadata', None)
            if old != compatibility:
                raise ValueError('Checkpoint incompatible ou sans métadonnées de ce script. '
                                 'Vérifier versions, observations, adversaire, place et récompense.')
            if model.batch_size < 2 or model.n_steps * args.n_envs % model.batch_size:
                raise ValueError('Le nombre d’environnements ne convient pas au batch du checkpoint')
            print('Reprise : hyperparamètres PPO du checkpoint conservés; nouvelles parties.')
        else:
            model = MaskablePPO(
                'MultiInputPolicy', train_env, learning_rate=args.learning_rate,
                n_steps=args.n_steps, batch_size=args.batch_size, n_epochs=args.n_epochs,
                gamma=args.gamma, gae_lambda=args.gae_lambda, ent_coef=args.ent_coef,
                clip_range=0.2, vf_coef=0.5, max_grad_norm=0.5, target_kl=args.target_kl,
                policy_kwargs={'net_arch': {'pi': [256, 256], 'vf': [256, 256]},
                               'activation_fn': torch.nn.Tanh},
                seed=args.seed, device=args.device, verbose=1,
            )
        # Reprise: nouvelle graine explicite pour le sampling et les nouveaux épisodes.
        model.set_random_seed(args.seed)
        train_env.seed(args.seed)
        model.dice_training_metadata = compatibility
        formats = ['stdout', 'csv'] + (['tensorboard'] if args.tensorboard else [])
        model.set_logger(configure(str(run / 'logs'), formats))
        effective = {name: getattr(model, name) for name in
                     ('n_steps', 'batch_size', 'n_epochs', 'gamma', 'gae_lambda', 'ent_coef', 'target_kl')}
        write_json(run / 'config.json', {
            'arguments': vars(args), 'compatibility': compatibility, 'effective_ppo': effective,
            'initial_timesteps': model.num_timesteps,
            'python': sys.version,
            'packages': {name: importlib.metadata.version(name) for name in
                         ('numpy', 'torch', 'gymnasium', 'stable-baselines3', 'sb3-contrib')},
            'notes': 'Best model = score final personnel moyen sur P1/P2, graines fixes de validation.',
        })

        def save_model(path: Path):
            temp = path.with_name(path.stem + '.tmp.zip')
            model.save(str(temp))
            os.replace(temp, path)

        class TrainingCallback(BaseCallback):
            """Évaluation maison: predict reçoit explicitement le masque à chaque pas.

            Aucun EvalCallback non masqué. Les évaluations ont lieu entre les
            rollouts pour ne pas toucher au mode train/eval pendant une mise à jour.
            """
            def __init__(self):
                super().__init__()
                self.last_eval = -1
                self.last_save = model.num_timesteps
                self.best = -math.inf
                self.lengths = np.zeros(args.n_envs, dtype=np.int64)

            def evaluate(self):
                rows = []
                for episode in range(args.eval_episodes):
                    player = 1 + episode % 2
                    seed = args.eval_seed + episode // 2
                    env = eval_envs[player]
                    obs, info = env.reset(seed=seed)
                    total_reward = 0.0
                    for steps in range(1, args.episode_guard + 1):
                        mask = env.action_masks()
                        action, _ = self.model.predict(obs, deterministic=True, action_masks=mask)
                        action = int(np.asarray(action).item())
                        if not mask[action]:
                            raise RuntimeError('La politique a proposé une action masquée')
                        obs, reward, terminated, truncated, info = env.step(action)
                        total_reward += float(reward)
                        if truncated:
                            raise RuntimeError('Évaluation tronquée: aucun score partiel ne sera classé')
                        if terminated:
                            break
                    else:
                        raise RuntimeError('Garde épisode atteinte en évaluation; vérifier le moteur')
                    score = float(info['scores']['agent'])
                    adversary = float(info['scores']['adversary'])
                    if not (math.isfinite(score) and math.isfinite(adversary)):
                        raise RuntimeError('Score non fini')
                    row = {'timesteps': self.num_timesteps, 'episode': episode, 'seed': seed,
                           'agent_player': player, 'score': score, 'adversary': adversary,
                           'reward': total_reward, 'steps': steps,
                           'win': int(score > adversary), 'draw': int(score == adversary)}
                    append_csv(run / 'evaluation_episodes.csv', row)
                    rows.append(row)
                scores = np.array([r['score'] for r in rows])
                summary = {
                    'timesteps': self.num_timesteps,
                    'mean_score': float(scores.mean()), 'std_score': float(scores.std()),
                    'mean_adversary': float(np.mean([r['adversary'] for r in rows])),
                    'win_rate': float(np.mean([r['win'] for r in rows])),
                    'draw_rate': float(np.mean([r['draw'] for r in rows])),
                    'mean_reward': float(np.mean([r['reward'] for r in rows])),
                    'mean_steps': float(np.mean([r['steps'] for r in rows])),
                    'score_p1': float(np.mean([r['score'] for r in rows if r['agent_player'] == 1])),
                    'score_p2': float(np.mean([r['score'] for r in rows if r['agent_player'] == 2])),
                }
                append_csv(run / 'evaluations.csv', summary)
                for key, value in summary.items():
                    if key != 'timesteps':
                        self.logger.record('evaluation/' + key, value)
                self.logger.dump(self.num_timesteps)
                self.last_eval = self.num_timesteps
                if summary['mean_score'] > self.best:
                    self.best = summary['mean_score']
                    save_model(run / 'best_model.zip')
                    write_json(run / 'best_evaluation.json', summary)
                print(f"Évaluation {self.num_timesteps}: score={summary['mean_score']:.2f}, "
                      f"victoires={summary['win_rate']:.1%}, meilleur={self.best:.2f}", flush=True)

            def checkpoint(self):
                save_model(run / 'latest.zip')
                save_model(run / 'checkpoints' / f'ppo_{self.num_timesteps:012d}.zip')
                checkpoints = sorted((run / 'checkpoints').glob('ppo_*.zip'))
                for old_path in checkpoints[:-args.keep_checkpoints]:
                    old_path.unlink()
                self.last_save = self.num_timesteps

            def _on_training_start(self):
                # Référence avant toute nouvelle mise à jour; même protocole que la suite.
                self.evaluate()
                self.checkpoint()

            def _on_rollout_start(self):
                if self.num_timesteps - self.last_eval >= args.eval_every:
                    self.evaluate()
                if self.num_timesteps - self.last_save >= args.checkpoint_every:
                    self.checkpoint()

            def _on_step(self):
                for i, (done, info) in enumerate(zip(self.locals['dones'], self.locals['infos'])):
                    self.lengths[i] += 1
                    if done:
                        if info.get('TimeLimit.truncated', False):
                            raise RuntimeError('Épisode d’entraînement tronqué de façon inattendue')
                        append_csv(run / 'training_episodes.csv', {
                            'timesteps': self.num_timesteps, 'env': i,
                            'player': info['agent_player'], 'score': info['scores']['agent'],
                            'adversary': info['scores']['adversary'], 'steps': int(self.lengths[i]),
                            'reward': info.get('episode', {}).get('r', ''),
                        })
                        self.lengths[i] = 0
                    elif self.lengths[i] >= args.episode_guard:
                        raise RuntimeError('Garde épisode atteinte pendant la collecte')
                return True

            def _on_training_end(self):
                if self.last_eval != self.num_timesteps:
                    self.evaluate()
                self.checkpoint()

        print(f'Run: {run.resolve()} | actions={N_ACTIONS} | PPO={effective}', flush=True)
        callback = TrainingCallback()
        try:
            model.learn(total_timesteps=args.total_timesteps, callback=callback,
                        reset_num_timesteps=not bool(args.resume), use_masking=True)
            save_model(run / 'final_model.zip')
        except KeyboardInterrupt:
            # Peut capturer une mise à jour partielle; les checkpoints réguliers restent disponibles.
            save_model(run / 'interrupted.zip')
            print('Interruption: interrupted.zip sauvegardé; reprise non identique bit à bit.')
        print(f'Fichiers disponibles dans {run.resolve()}', flush=True)
    finally:
        train_env.close()
        for env in eval_envs.values():
            env.close()


if __name__ == '__main__':
    main()
