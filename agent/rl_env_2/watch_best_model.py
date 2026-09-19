#!/usr/bin/env python3
"""Génère un replay JSON d'un épisode d'évaluation d'un modèle produit par
train_solo_score_delta.py (rl_env_2), pour l'onglet Replay du front.

Le modèle ne contient pas la partie : l'environnement est déterministe pour une
graine donnée, donc rejouer le checkpoint sur la même graine régénère la partie
à l'identique. Ce script conduit ``DiceGameEnv2`` avec ``trace=True`` et écrit un
JSON par épisode + un ``index.json``, au format attendu par ``GET /replays`` et
``ReplayView`` (trace minimale : états sérialisés, actions atomiques, rl).

L'adversaire est toujours le checkpoint (runs/essai_01/best_model.zip par
défaut), comme dans train_solo_score_delta.py. Les métadonnées (reward_mode,
gamma, versions, checkpoint) sont lues depuis metadata.json (fin d'entraînement)
ou run_config.json (démarrage) à côté du modèle; des valeurs par défaut sont
utilisées sinon.

Exemple::

    python rl_env_2/watch_best_model.py --model runs/solo_<ts>/score_delta_solo/best_model.zip --seed 2000000
    uvicorn api.app:app --port 8000   # puis onglet Replay du front
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_AGENT_DIR = Path(__file__).resolve().parents[1]    # agent/ (rl_env, rl_env_2, runs)
_BACKEND_DIR = _AGENT_DIR.parent / "backend"        # backend/ (game_engine, simulation)
for _root in (_AGENT_DIR, _BACKEND_DIR):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

DEFAULT_REWARD_MODE = "score_delta_normalized"
_SAFE_RE = re.compile(r"[^A-Za-z0-9_.-]")


def _find_sidecar(model_path: Path, name: str) -> Path | None:
    """Look for ``name`` next to the model, then in its parent run directory."""
    for base in (model_path.parent, model_path.parent.parent):
        candidate = base / name
        if candidate.is_file():
            return candidate
    return None


def _read_json(path: Path | None) -> dict:
    if path is None:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _checkpoint_from(meta: dict, config: dict) -> Path | None:
    """Recover the opponent checkpoint from either the solo or sequence metadata."""
    opponent = meta.get("opponent")
    if isinstance(opponent, dict) and opponent.get("path"):
        return Path(opponent["path"])
    for key in ("checkpoint_used_as_opponent", "checkpoint"):
        if meta.get(key):
            return Path(meta[key])
    if config.get("checkpoint"):
        return Path(config["checkpoint"])
    return None


def _run_root_for(model_path: Path) -> Path:
    """Racine du run : ``agent/runs`` si le modèle est dessous, sinon ``agent``."""
    model_dir = model_path.parent.resolve()
    runs_root = (_AGENT_DIR / "runs").resolve()
    try:
        model_dir.relative_to(runs_root)
        return runs_root
    except ValueError:
        return _AGENT_DIR.resolve()


def _run_label(model_path: Path) -> str:
    """Informative run label, e.g. ``solo_<ts>/score_delta_solo`` or ``shaped_<ts>/run_x``."""
    model_dir = model_path.parent.resolve()
    root = _run_root_for(model_path)
    try:
        parts = list(model_dir.relative_to(root).parts)
    except ValueError:
        return model_dir.name
    if parts and parts[0] == "runs":
        parts = parts[1:]
    return "/".join(parts) if parts else model_dir.name


def _default_out_dir(model_path: Path) -> Path:
    """The ``<run>/replays`` directory scanned by ``GET /replays``.

    A model lives under ``agent/<run>`` or ``agent/runs/<run>``; we target the
    run directory directly under the chosen root (e.g. ``agent/shaped_<ts>``).
    """
    model_dir = model_path.parent.resolve()
    root = _run_root_for(model_path)
    try:
        parts = model_dir.relative_to(root).parts
    except ValueError:
        return model_dir / "replays"
    return (root / parts[0]) / "replays" if parts else model_dir / "replays"


def _update_manifest(out_dir: Path, entry: dict) -> None:
    manifest_path = out_dir / "index.json"
    manifest: dict = {"replays": []}
    if manifest_path.exists():
        loaded = _read_json(manifest_path)
        if isinstance(loaded.get("replays"), list):
            manifest = loaded
    manifest["replays"] = [r for r in manifest["replays"] if r.get("id") != entry["id"]]
    manifest["replays"].append(entry)
    manifest["replays"].sort(
        key=lambda r: (str(r.get("run", "")), int(r.get("seed", 0)), int(r.get("agent_player", 0)))
    )
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--model', type=Path, required=True, help='Checkpoint best_model.zip à rejouer')
    parser.add_argument('--checkpoint', type=Path, default=None,
                        help='Adversaire checkpoint; par défaut déduit des métadonnées, sinon essai_01/best_model.zip')
    parser.add_argument('--device', default=None, help='cpu par défaut (comme le training)')
    parser.add_argument('--episodes', type=int, default=1)
    parser.add_argument('--seed', type=int, default=2_000_000,
                        help='Épisode i: seed+i. Par défaut différent des graines de validation.')
    parser.add_argument('--agent-player', choices=['1', '2', 'random'], default='random')
    parser.add_argument('--episode-guard', type=int, default=10_000)
    parser.add_argument('--out-dir', type=Path, default=None,
                        help='Défaut: <run>/replays (le dossier scanné par GET /replays)')
    args = parser.parse_args(argv)
    if args.episodes < 1 or args.episode_guard < 1 or args.seed < 0:
        parser.error('episodes/episode-guard doivent être positifs; seed >= 0')
    return args


def run_episode(model, env, seed: int, guard: int) -> tuple[dict, int]:
    import numpy as np

    obs, info = env.reset(seed=seed)
    n_actions = int(model.action_space.n)
    for decisions in range(1, guard + 1):
        mask = np.asarray(env.action_masks(), dtype=bool)
        if mask.shape != (n_actions,) or not mask.any():
            raise RuntimeError('Masque invalide ou vide')
        action, _ = model.predict(obs, deterministic=True, action_masks=mask)
        action = int(np.asarray(action).item())
        if not (0 <= action < n_actions and mask[action]):
            raise RuntimeError('Action prédite illégale')
        obs, _reward, terminated, truncated, info = env.step(action)
        if truncated:
            raise RuntimeError('Partie tronquée de façon inattendue')
        if terminated:
            break
    else:
        raise RuntimeError('Garde atteinte: vérifier le moteur, partie non classée.')
    return info, decisions


def main(argv=None):
    args = parse_args(argv)
    try:
        import gymnasium as gym
        import torch
        from sb3_contrib import MaskablePPO
    except ImportError as exc:
        raise SystemExit('Installer les dépendances du script d’entraînement.\n' + str(exc)) from exc
    try:
        from rl_env_2 import ACTION_VERSION_2, DEFAULT_GAMMA, N_ACTIONS_2, OBSERVATION_VERSION_2
        from rl_env_2.env import DiceGameEnv2
        from rl_env_2.opponents import DEFAULT_CHECKPOINT
        from rl_env_2.rewards import REWARD_MODES
        from rl_env_2.wrappers import FixedBoxScaling2
    except ImportError as exc:
        raise SystemExit('Lancer depuis agent/ (ou backend/), avec ce script dans rl_env_2/.\n' + str(exc)) from exc

    torch.set_num_threads(1)
    args.model = args.model.resolve()
    if not args.model.is_file():
        raise FileNotFoundError(args.model)

    # Sidecar metadata is optional: absent from an in-progress solo run.
    config = _read_json(_find_sidecar(args.model, 'run_config.json'))
    meta = _read_json(_find_sidecar(args.model, 'metadata.json'))

    reward_mode = meta.get('reward_mode') or config.get('reward_mode') or DEFAULT_REWARD_MODE
    if reward_mode not in REWARD_MODES:
        raise ValueError(f'reward_mode inconnu dans les métadonnées: {reward_mode!r} (attendu: {REWARD_MODES})')
    gamma = float(meta.get('gamma') or config.get('gamma') or DEFAULT_GAMMA)
    device = args.device or config.get('device') or 'cpu'
    # Prefer an existing checkpoint: metadata may hold a stale absolute path
    # (e.g. after moving the repo); fall back to the packaged DEFAULT_CHECKPOINT.
    checkpoint = None
    for _candidate in (args.checkpoint, _checkpoint_from(meta, config), DEFAULT_CHECKPOINT):
        if _candidate and Path(_candidate).is_file():
            checkpoint = Path(_candidate).resolve()
            break
    if checkpoint is None:
        raise FileNotFoundError(
            f'Checkpoint introuvable: {args.checkpoint or _checkpoint_from(meta, config) or DEFAULT_CHECKPOINT}. '
            'Précisez --checkpoint (aucun fallback heuristique).'
        )

    model = MaskablePPO.load(str(args.model), device=device)
    for key, current in [('action_version', ACTION_VERSION_2), ('observation_version', OBSERVATION_VERSION_2),
                         ('n_actions', N_ACTIONS_2)]:
        if key in meta and meta[key] != current:
            raise ValueError(f'Incompatibilité {key}: checkpoint={meta.get(key)}, moteur={current}')
    if int(model.action_space.n) != N_ACTIONS_2:
        raise ValueError(f'Incompatibilité n_actions: modèle={model.action_space.n}, moteur={N_ACTIONS_2}')

    player = args.agent_player if args.agent_player == 'random' else int(args.agent_player)
    base = DiceGameEnv2(agent_player=player, opponent='checkpoint', reward_mode=reward_mode, gamma=gamma,
                        max_steps=None, trace=True, opponent_kwargs={'checkpoint': checkpoint, 'device': device})
    env = FixedBoxScaling2(base)
    inner = env.env

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

    if describe(model.observation_space) != describe(env.observation_space):
        raise ValueError('L’espace d’observation 2.0 a changé depuis l’entraînement.')

    out_dir = args.out_dir or _default_out_dir(args.model)
    run_label = _run_label(args.model)
    safe_run = _SAFE_RE.sub('_', run_label)
    out_dir.mkdir(parents=True, exist_ok=True)

    written = []
    try:
        for episode in range(args.episodes):
            seed = args.seed + episode
            info, decisions = run_episode(model, env, seed, args.episode_guard)
            if meta.get('rules_version') and info['rules_version'] != meta['rules_version']:
                raise ValueError('Version des règles différente de celle du modèle.')
            agent_player = int(info['agent_player'])
            trace = {
                'run': run_label,
                'checkpoint': checkpoint.name,
                'seed': seed,
                'agent_player': agent_player,
                'rules_version': info.get('rules_version'),
                'observation_version': OBSERVATION_VERSION_2,
                'action_version': ACTION_VERSION_2,
                'n_actions': N_ACTIONS_2,
                'initial_state': inner.trace_initial,
                'frames': inner.trace,
                'final_scores': info.get('final_scores'),
                'result': info.get('result'),
                'agent_decisions': decisions,
                'created': datetime.now(timezone.utc).isoformat(),
            }
            replay_id = f'{safe_run}__{checkpoint.stem}_seed{seed}_p{agent_player}'
            file_name = f'{replay_id}.json'
            (out_dir / file_name).write_text(
                json.dumps(trace, ensure_ascii=False, separators=(',', ':')), encoding='utf-8'
            )
            _update_manifest(
                out_dir,
                {
                    'id': replay_id,
                    'run': run_label,
                    'checkpoint': checkpoint.name,
                    'seed': seed,
                    'agent_player': agent_player,
                    'file': file_name,
                    'agent_decisions': decisions,
                    'frames': len(trace['frames']),
                    'final_scores': trace['final_scores'],
                    'result': trace['result'],
                },
            )
            written.append(replay_id)
            scores = trace['final_scores'] or {}
            print(
                f'[{episode + 1}/{args.episodes}] seed={seed} P{agent_player}: '
                f'{decisions} décisions, {len(trace["frames"])} frames, '
                f'scores agent={scores.get("agent")} adversaire={scores.get("adversary")} '
                f'résultat={trace["result"]}'
            )
    finally:
        env.close()

    print(f'\n{len(written)} replay(s) écrit(s) dans {out_dir.resolve()}')
    print('Lancer l’API puis l’onglet Replay : uvicorn api.app:app --port 8000')


if __name__ == '__main__':
    main()
