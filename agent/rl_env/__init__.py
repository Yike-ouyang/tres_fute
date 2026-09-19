"""Gymnasium environment for the full two-player Très Futé game."""

from .actions import ACTION_VERSION, N_ACTIONS, build_legal_decisions, decode, encode, legal_action_mask
from .env import DiceGameEnv
from .observations import OBSERVATION_VERSION, decision_kind, encode_observation, observation_space
from .opponents import HeuristicOpponent, RandomOpponent, make_opponent
from .rewards import DEFAULT_REWARD_SCALE, RewardCalculator

__all__ = [
    "ACTION_VERSION",
    "N_ACTIONS",
    "DEFAULT_REWARD_SCALE",
    "DiceGameEnv",
    "HeuristicOpponent",
    "OBSERVATION_VERSION",
    "RandomOpponent",
    "RewardCalculator",
    "build_legal_decisions",
    "decision_kind",
    "decode",
    "encode",
    "encode_observation",
    "legal_action_mask",
    "make_opponent",
    "observation_space",
]
