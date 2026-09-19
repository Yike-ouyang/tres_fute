"""Bibliothèque de parties humaines pour *Très Futé*.

Trois modes, exposés par :mod:`human_play.session` et l'API REST :

* ``human``  — deux joueurs humains, hot-seat sur le même écran ;
* ``ai``     — un humain contre un modèle ``MaskablePPO`` (rl_env_2, 149 actions) ;
* ``replay`` — relecture d'une trace existante (voir :mod:`human_play.replay_bridge`).

Le moteur de règles reste ``game_engine`` ; ce package ne fait qu'orchestrer.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Deux racines : backend/ (game_engine) et agent/ (rl_env, rl_env_2).
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_AGENT_DIR = _BACKEND_DIR.parent / "agent"
for _root in (_BACKEND_DIR, _AGENT_DIR):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

from .opponent import AIPolicy, find_default_checkpoint, list_checkpoints  # noqa: E402
from .replay_bridge import build_trace, default_replays_dir, save_trace  # noqa: E402
from .session import HumanGameSession  # noqa: E402

__all__ = [
    "AIPolicy",
    "HumanGameSession",
    "build_trace",
    "default_replays_dir",
    "find_default_checkpoint",
    "list_checkpoints",
    "save_trace",
]
