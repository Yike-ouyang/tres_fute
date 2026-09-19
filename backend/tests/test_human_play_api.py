"""Tests API des sessions humaines : partie complète, sauvegarde, reload."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from api.app import app
from human_play.opponent import AIPolicy

from rl_env_2.actions import N_ACTIONS_2


class _FirstLegalModel:
    class action_space:  # noqa: N801
        n = N_ACTIONS_2

    def predict(self, obs, deterministic=True, action_masks=None):  # noqa: ANN001
        return int(np.flatnonzero(action_masks)[0]), None


def _stub_policy(checkpoint="<stub>", device="cpu") -> AIPolicy:
    return AIPolicy(checkpoint, model=_FirstLegalModel())


def _client() -> TestClient:
    return TestClient(app)


def _play_full_game(client: TestClient, session_id: str, guard: int = 2000) -> dict:
    state = client.get(f"/human_play/sessions/{session_id}").json()
    steps = 0
    while not state["is_over"]:
        actions = client.get(f"/human_play/sessions/{session_id}/legal_actions").json()["actions"]
        assert actions, "aucune action légale"
        response = client.post(
            f"/human_play/sessions/{session_id}/step", json={"action_id": actions[0]["id"]}
        )
        assert response.status_code == 200, response.text
        state = response.json()
        steps += 1
        assert steps < guard
    return state


def test_human_human_full_game_and_save(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRES_FUTE_RUNS_DIR", str(tmp_path))
    client = _client()

    created = client.post("/human_play/sessions", json={"agent_player": 1, "opponent": "human", "seed": 4})
    assert created.status_code == 200, created.text
    session_id = created.json()["session_id"]
    assert "state" in created.json()

    state = _play_full_game(client, session_id)
    assert state["is_over"] is True

    saved = client.post(
        f"/human_play/sessions/{session_id}/save",
        json={"path": str(tmp_path / "human_play" / "replays")},
    )
    assert saved.status_code == 200, saved.text
    replay_id = saved.json()["replay_id"]

    listed = client.get("/replays").json()["replays"]
    assert any(entry["id"] == replay_id for entry in listed)

    loaded = client.get(f"/replays/{replay_id}")
    assert loaded.status_code == 200, loaded.text
    trace = loaded.json()
    assert trace["final_scores"] is not None
    assert trace["frames"]

    assert client.delete(f"/human_play/sessions/{session_id}").status_code == 200
    assert client.get(f"/human_play/sessions/{session_id}").status_code == 404


def test_human_ai_full_game(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("human_play.session.AIPolicy", _stub_policy)
    client = _client()
    created = client.post(
        "/human_play/sessions",
        json={"agent_player": 2, "opponent": "ai", "checkpoint": "<stub>", "seed": 6},
    )
    assert created.status_code == 200, created.text
    session_id = created.json()["session_id"]
    state = _play_full_game(client, session_id)
    assert state["is_over"] is True
    assert state["opponent"] == "ai"


def test_illegal_action_and_unknown_session() -> None:
    client = _client()
    assert client.get("/human_play/sessions/nope").status_code == 404
    created = client.post("/human_play/sessions", json={"agent_player": 1, "opponent": "human", "seed": 1})
    session_id = created.json()["session_id"]
    bad = client.post(f"/human_play/sessions/{session_id}/step", json={"action_id": 999999})
    assert bad.status_code == 400


def test_models_route_lists_checkpoints() -> None:
    client = _client()
    response = client.get("/human_play/models")
    assert response.status_code == 200
    models = response.json()["models"]
    assert isinstance(models, list) and models
    for entry in models:
        assert {"path", "relpath", "run", "file", "mtime", "catalogue", "is_default"} <= set(entry)
        assert entry["catalogue"] in ("v1", "v2")
    assert sum(1 for m in models if m["is_default"]) <= 1


def test_cancel_via_step() -> None:
    client = _client()
    created = client.post("/human_play/sessions", json={"agent_player": 1, "opponent": "human", "seed": 1})
    session_id = created.json()["session_id"]
    state = created.json()["state"]
    for _ in range(20):
        if state["state"]["selection"] is not None:
            break
        actions = client.get(f"/human_play/sessions/{session_id}/legal_actions").json()["actions"]
        die = next((a for a in actions if a["category"] == "select_die"), None)
        assert die is not None, "aucun dé sélectionnable"
        state = client.post(
            f"/human_play/sessions/{session_id}/step", json={"action_id": die["id"]}
        ).json()
    assert state["state"]["selection"] is not None
    cancelled = client.post(f"/human_play/sessions/{session_id}/step", json={"cancel": True})
    assert cancelled.status_code == 200
    assert cancelled.json()["state"]["selection"] is None
