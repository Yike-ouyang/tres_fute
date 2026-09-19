"""Tests CLI : les trois modes se déroulent sans erreur (input simulé)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from human_play import cli
from human_play.opponent import AIPolicy

from rl_env_2.actions import N_ACTIONS_2

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ESSAI_RUN = _REPO_ROOT / "agent" / "runs" / "essai_01"


class _FirstLegalModel:
    class action_space:  # noqa: N801
        n = N_ACTIONS_2

    def predict(self, obs, deterministic=True, action_masks=None):  # noqa: ANN001
        return int(np.flatnonzero(action_masks)[0]), None


def _stub_policy(checkpoint="<stub>", device="cpu") -> AIPolicy:
    return AIPolicy(checkpoint, model=_FirstLegalModel())


def _fake_input(prompt: str = "") -> str:
    if "Enregistrer" in prompt:
        return ""  # ne pas sauvegarder
    if "siège" in prompt:
        return "1"
    if "n]ext" in prompt or "quit" in prompt.lower():
        return "q"
    return "1"  # premier choix / numéro d'action


def test_cli_play(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", _fake_input)
    assert cli.main(["play", "--seed", "1", "--render", "text"]) == 0


def test_cli_play_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", _fake_input)
    assert cli.main(["play", "--seed", "2", "--render", "json"]) == 0


def test_cli_vs_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", _fake_input)
    monkeypatch.setattr("human_play.session.AIPolicy", _stub_policy)
    assert cli.main(["vs-ai", "--agent-player", "1", "--checkpoint", "<stub>", "--seed", "3"]) == 0


def test_cli_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    if not (_ESSAI_RUN / "config.json").exists() or not (_ESSAI_RUN / "best_model.zip").is_file():
        pytest.skip("run essai_01 indisponible")
    monkeypatch.setattr("builtins.input", _fake_input)
    assert cli.main(["replay", "--run", str(_ESSAI_RUN), "--seed", "1000000", "--agent-player", "1"]) == 0
