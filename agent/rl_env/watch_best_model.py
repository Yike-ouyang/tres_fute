#!/usr/bin/env python3
"""Observer un modèle produit par train_maskable_ppo.py, sans entraînement.

Placer dans agent/rl_env/, puis lancer depuis agent/:
 python rl_env/watch_best_model.py --model sequence_20260916_211727/run1_score_delta/best_model.zip --pause

Affichage textuel des décisions et appel à env.render(). Ce script ne connecte
pas la partie à React. Un step peut contenir plusieurs actions automatiques et
adverses : seules les décisions rendues à l'agent sont affichées individuellement.
Le prétraitement fixed_box_scaling_v1 et le masque sont appliqués comme au training.
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--episodes', type=int, default=1)
    parser.add_argument('--seed', type=int, default=2_000_000,
                        help='Épisode i: seed+i. Par défaut différent des graines de validation.')
    parser.add_argument('--agent-player', choices=['1', '2', 'random'], default='random')
    parser.add_argument('--opponent', choices=['heuristic', 'random'], default=None,
                        help='Par défaut, adversaire indiqué dans le checkpoint')
    parser.add_argument('--pause', action='store_true', help='Entrée avant chaque décision de l’agent')
    parser.add_argument('--delay', type=float, default=0.3, help='Pause en secondes si --pause absent')
    parser.add_argument('--quiet', action='store_true', help='Scores finaux uniquement')
    parser.add_argument('--episode-guard', type=int, default=10_000)
    args = parser.parse_args(argv)
    if args.episodes < 1 or args.episode_guard < 1 or args.seed < 0:
        parser.error('episodes/episode-guard doivent être positifs; seed >= 0')
    if not math.isfinite(args.delay) or args.delay < 0:
        parser.error('delay doit être fini et >= 0')
    return args


def main(argv=None):
    args = parse_args(argv)
    try:
        import gymnasium as gym
        import numpy as np
        import torch
        from sb3_contrib import MaskablePPO
    except ImportError as exc:
        raise SystemExit('Installer les dépendances du script d’entraînement.\n' + str(exc)) from exc
    _agent_dir = Path(__file__).resolve().parents[1]
    _backend_dir = _agent_dir.parent / "backend"
    for _root in (_agent_dir, _backend_dir):
        if str(_root) not in sys.path:
            sys.path.insert(0, str(_root))
    try:
        from rl_env import DiceGameEnv, ACTION_VERSION, OBSERVATION_VERSION, N_ACTIONS
        from rl_env.actions import label
    except ImportError as exc:
        raise SystemExit('Lancer depuis agent/, avec ce script dans rl_env/.\n' + str(exc)) from exc

    torch.set_num_threads(1)
    if not args.model.is_file():
        raise FileNotFoundError(args.model)
    model = MaskablePPO.load(str(args.model), device='cpu')
    meta = getattr(model, 'dice_training_metadata', None)
    if not isinstance(meta, dict) or meta.get('preprocessing') != 'fixed_box_scaling_v1':
        raise ValueError('Checkpoint attendu: produit par le train_maskable_ppo.py fourni, avec ses métadonnées.')
    for key, current in [('action_version', ACTION_VERSION), ('observation_version', OBSERVATION_VERSION),
                         ('n_actions', N_ACTIONS)]:
        if meta.get(key) != current:
            raise ValueError(f'Incompatibilité {key}: checkpoint={meta.get(key)}, moteur={current}')
    player = args.agent_player if args.agent_player == 'random' else int(args.agent_player)
    env = DiceGameEnv(agent_player=player, opponent=args.opponent or meta['opponent'],
                      reward_mode=meta['reward_mode'], reward_scale=meta['reward_scale'], max_steps=None)

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

    def preprocess(obs):
        if not env.observation_space.contains(obs):
            bad = [k for k, s in env.observation_space.spaces.items() if k not in obs or not s.contains(obs[k])]
            raise ValueError(f'Observation hors bornes: {bad}; corriger l’encodeur sans clipping.')
        result = {}
        for key, space in env.observation_space.spaces.items():
            value = obs[key]
            if isinstance(space, gym.spaces.Box):
                low, high = space.low.astype(np.float32), space.high.astype(np.float32)
                span = np.where(high > low, high - low, 1.0)
                value = (np.asarray(value, dtype=np.float32) - low) / span
            result[key] = value
        return result

    def render():
        result = env.render()
        if isinstance(result, str) and result:
            print(result)

    scores = []
    wins = draws = 0
    try:
        if describe(env.observation_space) != meta['raw_observation_space']:
            raise ValueError('Les formes, types ou bornes des observations ont changé depuis l’entraînement.')
        for episode in range(args.episodes):
            obs, info = env.reset(seed=args.seed + episode)
            if info['rules_version'] != meta['rules_version']:
                raise ValueError('Version des règles différente de celle du modèle.')
            if not args.quiet:
                print(f"\nPartie {episode+1} — graine {args.seed+episode} — agent P{info['agent_player']}")
                render()
            total_reward = 0.0
            for step in range(1, args.episode_guard + 1):
                mask = np.asarray(env.action_masks(), dtype=bool)
                if mask.shape != (N_ACTIONS,) or not mask.any():
                    raise RuntimeError('Masque invalide ou vide')
                action, _ = model.predict(preprocess(obs), deterministic=True, action_masks=mask)
                action = int(np.asarray(action).item())
                if not (0 <= action < N_ACTIONS and mask[action]):
                    raise RuntimeError('Action prédite illégale')
                if not args.quiet:
                    print(f"[{step}] Tour {info.get('turn')} / manche {info.get('round')} / "
                          f"{info.get('phase')} → {label(action)}", flush=True)
                    if args.pause:
                        input('Entrée pour exécuter cette décision (Ctrl+C pour arrêter) : ')
                    elif args.delay:
                        time.sleep(args.delay)
                obs, reward, terminated, truncated, info = env.step(action)
                total_reward += float(reward)
                if not args.quiet:
                    render()
                    print(f"  Scores: agent={info['scores']['agent']} / adversaire={info['scores']['adversary']}")
                if truncated:
                    raise RuntimeError('Partie tronquée de façon inattendue')
                if terminated:
                    break
            else:
                raise RuntimeError('Garde atteinte: vérifier le moteur, partie non classée.')
            score, other = float(info['scores']['agent']), float(info['scores']['adversary'])
            scores.append(score)
            wins += score > other
            draws += score == other
            print(f"Partie {episode+1}: P{info['agent_player']} score={score:g}, adversaire={other:g}, "
                  f"résultat={info.get('result', 'n/a')}, décisions={step}, reward={total_reward:.3f}")
        print(f'\nMoyenne={np.mean(scores):.2f}, écart-type={np.std(scores):.2f}, '
              f'victoires={wins}/{len(scores)}, égalités={draws}/{len(scores)}')
    except KeyboardInterrupt:
        print('\nLecture arrêtée.')
    finally:
        env.close()


if __name__ == '__main__':
    main()
