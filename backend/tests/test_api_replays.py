"""Replay API: manifest listing, single trace, 404 and path-traversal safety."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import app


def _client() -> TestClient:
    return TestClient(app)


def _make_runs_root(tmp_path: Path) -> Path:
    runs = tmp_path / "runs"
    replays = runs / "runA" / "replays"
    replays.mkdir(parents=True)
    (replays / "trace.json").write_text(json.dumps({"seed": 1, "frames": [{"index": 0}]}), encoding="utf-8")
    (replays / "index.json").write_text(
        json.dumps(
            {
                "replays": [
                    {
                        "id": "runA__best_model_seed1_p1",
                        "run": "runA",
                        "checkpoint": "best_model.zip",
                        "seed": 1,
                        "agent_player": 1,
                        "file": "trace.json",
                        "agent_decisions": 1,
                        "frames": 1,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return runs


def test_list_and_get_replay(tmp_path, monkeypatch):
    runs = _make_runs_root(tmp_path)
    monkeypatch.setenv("TRES_FUTE_RUNS_DIR", str(runs))
    client = _client()

    listed = client.get("/replays")
    assert listed.status_code == 200
    ids = [r["id"] for r in listed.json()["replays"]]
    assert ids == ["runA__best_model_seed1_p1"]

    got = client.get("/replays/runA__best_model_seed1_p1")
    assert got.status_code == 200
    assert got.json()["seed"] == 1


def test_unknown_replay_is_404(tmp_path, monkeypatch):
    runs = _make_runs_root(tmp_path)
    monkeypatch.setenv("TRES_FUTE_RUNS_DIR", str(runs))
    client = _client()
    assert client.get("/replays/does_not_exist").status_code == 404


def test_path_traversal_is_rejected(tmp_path, monkeypatch):
    runs = _make_runs_root(tmp_path)
    monkeypatch.setenv("TRES_FUTE_RUNS_DIR", str(runs))
    client = _client()
    for bad in ["..%2F..%2Fetc%2Fpasswd", "..%2Findex", "a%2Fb"]:
        assert client.get(f"/replays/{bad}").status_code == 404


def test_empty_runs_dir_lists_nothing(tmp_path, monkeypatch):
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("TRES_FUTE_RUNS_DIR", str(empty))
    client = _client()
    assert client.get("/replays").json() == {"replays": []}
