"""Reconstruction of exact games from a trained checkpoint (skipped if unavailable)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

RUN = Path(__file__).resolve().parents[1] / "runs" / "essai_01"
CHECKPOINT = "best_model.zip"


pytest.importorskip("sb3_contrib")
pytest.importorskip("torch")


def _require_run() -> None:
    if not (RUN / "config.json").exists() or not (RUN / CHECKPOINT).exists():
        pytest.skip(f"run/model not available: {RUN}")


def _csv_row(seed: int, player: int) -> dict[str, str] | None:
    path = RUN / "evaluation_episodes.csv"
    best_path = RUN / "best_evaluation.json"
    if not path.exists():
        return None
    best_ts = None
    if best_path.exists():
        best_ts = str(json.loads(best_path.read_text(encoding="utf-8"))["timesteps"])
    for row in csv.DictReader(path.open(encoding="utf-8")):
        if row["seed"] != str(seed) or row["agent_player"] != str(player):
            continue
        if best_ts is not None and row["timesteps"] != best_ts:
            continue
        return row
    return None


def test_summarize_observation_shape():
    from game_engine.engine import GameEngine
    from rl_env.observations import encode_observation
    from rl_env.replay import summarize_observation

    obs = encode_observation(GameEngine(seed=1).state, 1)
    summary = summarize_observation(obs, 1)
    assert summary["agent_player"] == 1
    assert set(summary["scores"]) == {"agent", "adversary"}
    assert len(summary["dice"]) == 6
    assert {"color", "value", "location", "joker_value"} <= set(summary["dice"][0])
    assert summary["phase"] in ("none", "active", "passive", "plus1", "fill-slots", "game-over")
    assert {"relance", "joker", "plus1"} == set(summary["bonuses"]["agent"])


def test_reconstruct_matches_logged_evaluation(tmp_path):
    _require_run()
    from rl_env import ACTION_VERSION, N_ACTIONS, OBSERVATION_VERSION
    from rl_env.replay import reconstruct

    trace = reconstruct(RUN, CHECKPOINT, seed=1000000, agent_player=1, out_dir=tmp_path)

    assert trace["action_version"] == ACTION_VERSION
    assert trace["observation_version"] == OBSERVATION_VERSION
    assert trace["n_actions"] == N_ACTIONS
    assert trace["initial_state"] is not None
    assert trace["frames"], "no atomic frames recorded"
    assert trace["result"] == "win"
    assert trace["final_scores"] == {"agent": 214, "adversary": 111}

    row = _csv_row(1000000, 1)
    if row is not None:
        assert trace["agent_decisions"] == int(row["steps"])
        assert trace["final_scores"]["agent"] == int(float(row["score"]))
        assert trace["final_scores"]["adversary"] == int(float(row["adversary"]))

    # agent decision frames carry the observation summary and the legal actions
    agent_frames = [f for f in trace["frames"] if f["rl"] is not None]
    assert len(agent_frames) == trace["agent_decisions"]
    first = agent_frames[0]
    assert first["observation_summary"]["agent_player"] == 1
    assert first["legal_actions"]
    assert all("state" in f and "scores" in f for f in trace["frames"])

    # a manifest + file were written
    manifest = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert manifest["replays"][0]["seed"] == 1000000
    assert (tmp_path / manifest["replays"][0]["file"]).exists()


def test_summarize_observation_is_agent_first():
    from rl_env.observations import encode_observation
    from rl_env.replay import summarize_observation

    from tests.helpers import base_state, empty_board

    state = base_state(
        boards={
            1: {**empty_board(), "values": {"pink-cell-1": 2}},
            2: {**empty_board(), "values": {"pink-cell-1": 9}},
        }
    )
    as_p1 = summarize_observation(encode_observation(state, 1), 1)
    as_p2 = summarize_observation(encode_observation(state, 2), 2)
    assert as_p1["scores"] == {"agent": 2, "adversary": 9}
    assert as_p2["scores"] == {"agent": 9, "adversary": 2}
