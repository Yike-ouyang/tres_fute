"""``rl_env_2``: a faster-learning variant of the Très Futé Gymnasium environment.

Simplified agent-centric observations (v2.0), a pruned and factorised action
catalogue (v2.0), a ``gamma`` exposed for the trainer, and a checkpoint opponent
(the ``essai_01`` policy). Rules stay in ``game_engine``.
"""

from .actions import ACTION_VERSION_2, N_ACTIONS_2, Pending, build_legal_decisions, decode, encode, label, legal_action_mask
from .env import DEFAULT_GAMMA, DiceGameEnv2
from .observations import OBSERVATION_VERSION_2, encode_observation_2, observation_space_2, zone_scores, zones_completed
from .opponents import CheckpointPolicy, make_opponent_2
from .rewards import REWARD_MODES, SequenceReward, StepStats, describe
from .wrappers import FixedBoxScaling2

__all__ = [
    "ACTION_VERSION_2",
    "CheckpointPolicy",
    "DEFAULT_GAMMA",
    "DiceGameEnv2",
    "FixedBoxScaling2",
    "N_ACTIONS_2",
    "OBSERVATION_VERSION_2",
    "Pending",
    "REWARD_MODES",
    "SequenceReward",
    "StepStats",
    "build_legal_decisions",
    "decode",
    "describe",
    "encode",
    "encode_observation_2",
    "label",
    "legal_action_mask",
    "make_opponent_2",
    "observation_space_2",
    "zone_scores",
    "zones_completed",
]
