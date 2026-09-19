"""Observation preprocessing for :mod:`rl_env_2` (mirrors ``rl_env.wrappers``)."""

from __future__ import annotations

import numpy as np
import gymnasium as gym

from .actions import N_ACTIONS_2


class FixedBoxScaling2(gym.ObservationWrapper):
    """Raw-space validation + fixed linear scaling; mask delegated to the engine."""

    def __init__(self, env: gym.Env) -> None:
        super().__init__(env)
        if not isinstance(env.observation_space, gym.spaces.Dict):
            raise TypeError("a flat Dict observation space is expected")
        self.raw_space = env.observation_space
        spaces: dict[str, gym.Space] = {}
        self.scales: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for key, space in self.raw_space.spaces.items():
            if isinstance(space, gym.spaces.Box):
                low, high = space.low.astype(np.float32), space.high.astype(np.float32)
                if not (np.isfinite(low).all() and np.isfinite(high).all()):
                    raise ValueError(f"non-finite bounds for {key}")
                self.scales[key] = (low, np.where(high > low, high - low, 1.0))
                spaces[key] = gym.spaces.Box(0.0, 1.0, shape=space.shape, dtype=np.float32)
            else:
                spaces[key] = space
        self.observation_space = gym.spaces.Dict(spaces)

    def observation(self, observation):  # type: ignore[override]
        if not self.raw_space.contains(observation):
            bad = [
                key
                for key, space in self.raw_space.spaces.items()
                if key not in observation or not space.contains(observation[key])
            ]
            raise ValueError(f"observation outside its declared space: {bad}.")
        return {
            key: (
                (np.asarray(value, dtype=np.float32) - self.scales[key][0]) / self.scales[key][1]
                if key in self.scales
                else value
            )
            for key, value in observation.items()
        }

    def action_masks(self) -> np.ndarray:
        mask = np.asarray(self.env.unwrapped.action_masks(), dtype=bool)
        if mask.shape != (N_ACTIONS_2,) or not mask.any():
            raise RuntimeError("mask missing, wrongly sized or empty in a decision state")
        return mask
