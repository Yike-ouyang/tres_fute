"""Checkpoint opponent (rl_env v1 policy) acting inside rl_env_2."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("sb3_contrib")
pytest.importorskip("torch")

from rl_env_2 import DiceGameEnv2
from rl_env_2.opponents import DEFAULT_CHECKPOINT, CheckpointPolicy, make_opponent_2


def _has_checkpoint() -> bool:
    return Path(DEFAULT_CHECKPOINT).exists()


def test_missing_checkpoint_raises_clear_error(tmp_path):
    missing = tmp_path / "nope.zip"
    with pytest.raises(FileNotFoundError) as exc:
        CheckpointPolicy(missing)
    assert "introuvable" in str(exc.value)


def test_incompatible_metadata_raises(monkeypatch):
    class Dummy:
        class action_space:  # noqa: N801
            n = 999

        dice_training_metadata = {"action_version": "x", "observation_version": "y", "n_actions": 999}

    with pytest.raises(ValueError) as exc:
        CheckpointPolicy._check_metadata(Dummy())
    assert "attendu" in str(exc.value) and "chargé" in str(exc.value)


@pytest.mark.skipif(not _has_checkpoint(), reason="essai_01 checkpoint not available")
def test_checkpoint_plays_legal_moves_over_100_games():
    policy = CheckpointPolicy()
    assert policy.name == "checkpoint"
    env = DiceGameEnv2(agent_player=1, opponent="checkpoint")
    rng = np.random.default_rng(0)
    opponent_actions = 0
    for seed in range(100):
        env.reset(seed=seed)
        for _ in range(5000):
            mask = env.action_masks()
            if not mask.any():
                break
            obs, _r, term, trunc, info = env.step(int(rng.choice(np.flatnonzero(mask))))
            opponent_actions += info["opponent_actions"]
            if term or trunc:
                break
    env.close()
    assert opponent_actions > 100  # the checkpoint really acted


@pytest.mark.skipif(not _has_checkpoint(), reason="essai_01 checkpoint not available")
def test_factory_returns_checkpoint(monkeypatch):
    monkeypatch.setattr("rl_env_2.opponents.CheckpointPolicy", CheckpointPolicy)
    policy = make_opponent_2("checkpoint")
    assert isinstance(policy, CheckpointPolicy)
