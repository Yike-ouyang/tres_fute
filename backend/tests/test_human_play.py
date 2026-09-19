"""Tests du module ``human_play`` : sessions humaines, trace, état JSON."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from human_play import HumanGameSession, build_trace, find_default_checkpoint, list_checkpoints
from human_play.opponent import AIPolicy

from rl_env_2.actions import N_ACTIONS_2

# Clés racine attendues (identiques à ``rl_env/replay.py``).
TRACE_ROOT_KEYS = {
    "run",
    "checkpoint",
    "seed",
    "agent_player",
    "rules_version",
    "observation_version",
    "action_version",
    "n_actions",
    "initial_state",
    "frames",
    "final_scores",
    "result",
    "agent_decisions",
    "created",
}

STATE_JSON_KEYS = {
    "session_id",
    "seed",
    "rules_version",
    "human_player",
    "opponent",
    "checkpoint",
    "is_over",
    "human_turn",
    "acting_player",
    "awaiting_value",
    "human_decisions",
    "last_ai_actions",
    "legal_actions",
    "events",
    "final_scores",
    "state",
    "legalActions",
    "scores",
    "decision",
}


class _FirstLegalModel:
    """Faux modèle : joue toujours le premier id légal (déterministe)."""

    class action_space:  # noqa: N801 - mimique l'API SB3
        n = N_ACTIONS_2

    def predict(self, obs, deterministic=True, action_masks=None):  # noqa: ANN001
        return int(np.flatnonzero(action_masks)[0]), None


def _first_legal_policy(checkpoint="<stub>", device="cpu") -> AIPolicy:
    return AIPolicy(checkpoint, model=_FirstLegalModel())


def _play_to_end(session: HumanGameSession, guard: int = 2000) -> int:
    steps = 0
    while not session.is_over():
        actions = session.legal_actions()
        assert actions, "aucune action légale"
        session.step(actions[0]["id"])
        steps += 1
        assert steps < guard, "partie trop longue"
    return steps


def test_human_human_full_game() -> None:
    session = HumanGameSession(agent_player=1, opponent_kind="human", seed=7)
    steps = _play_to_end(session)
    assert session.is_over()
    assert steps > 0
    assert session.human_decisions == steps
    assert len(session.trace) > 0
    assert session.trace_initial is not None


def test_human_ai_full_game(monkeypatch: pytest.MonkeyPatch) -> None:
    # Stub déterministe : pas besoin de checkpoint sur disque.
    monkeypatch.setattr("human_play.session.AIPolicy", _first_legal_policy)
    session = HumanGameSession(agent_player=1, opponent_kind="ai", checkpoint="<stub>", seed=11)
    _play_to_end(session)
    assert session.is_over()
    roles = {frame["role"] for frame in session.trace}
    assert "opponent" in roles  # l'IA a bien joué
    assert session.checkpoint == "<stub>"


def test_real_checkpoint_if_available() -> None:
    checkpoint = find_default_checkpoint()
    if checkpoint is None:
        pytest.skip("aucun best_model.zip v2 sous agent/runs/{solo_*,shaped_*}")
    session = HumanGameSession(agent_player=1, opponent_kind="ai", checkpoint=str(checkpoint), seed=3)
    _play_to_end(session)
    assert session.is_over()
    assert {f["role"] for f in session.trace} >= {"opponent"}


def test_all_legal_actions_accepted_at_first_decision() -> None:
    reference = HumanGameSession(agent_player=1, opponent_kind="human", seed=5)
    ids = [action["id"] for action in reference.legal_actions()]
    assert ids
    for action_id in ids:
        session = HumanGameSession(agent_player=1, opponent_kind="human", seed=5)
        session.step(action_id)  # ne doit jamais lever


def test_state_json_is_stable_and_complete() -> None:
    session = HumanGameSession(agent_player=2, opponent_kind="human", seed=9)
    payload = session.state_json()
    assert STATE_JSON_KEYS <= set(payload)
    assert payload["human_player"] == 2
    assert payload["opponent"] == "human"
    assert isinstance(payload["legal_actions"], list)
    # sérialisable JSON
    import json

    json.dumps(payload)


def test_trace_matches_replay_format() -> None:
    session = HumanGameSession(agent_player=1, opponent_kind="human", seed=13)
    _play_to_end(session)
    trace = build_trace(session)
    assert set(trace) == TRACE_ROOT_KEYS
    assert trace["final_scores"]["agent"] == session.final_scores()["agent"]
    assert isinstance(trace["frames"], list) and trace["frames"]
    assert {"index", "role", "actor", "decision_kind", "action", "state", "decision", "scores", "rl"} <= set(
        trace["frames"][0]
    )


def _reach_pick_cell(session: HumanGameSession, limit: int = 20) -> bool:
    from game_engine.legal import current_decision

    for _ in range(limit):
        if current_decision(session.engine.state).get("kind") == "pick_cell":
            return True
        die = next((a for a in session.legal_actions() if a["category"] == "select_die"), None)
        if die is None:
            return False
        session.step(die["id"])
    return False


def test_cancel_clears_open_selection() -> None:
    session = HumanGameSession(agent_player=1, opponent_kind="human", seed=1)
    assert _reach_pick_cell(session)
    assert session.engine.state["selection"] is not None
    before = session.human_decisions
    payload = session.cancel()
    assert payload["state"]["selection"] is None
    # L'annulation ne consomme aucune décision humaine supplémentaire.
    assert session.human_decisions == before


def test_opponent_name_and_no_observation_leak(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("human_play.session.AIPolicy", _first_legal_policy)
    session = HumanGameSession(agent_player=1, opponent_kind="ai", checkpoint="<stub>", seed=2)
    payload = session.state_json()
    assert payload["opponent_name"] == "<stub>"
    observation_keys = {
        "yellow_checks",
        "turquoise_checks",
        "dice_values",
        "bonus_blue_cell",
        "opp_score_total",
        "agent_zones_completed",
    }
    assert observation_keys.isdisjoint(payload)


def test_top_level_run_discovery(tmp_path: Path) -> None:
    # Runs may live directly under the base dir (agent/<run>) as well as agent/runs/<run>.
    top = tmp_path / "shaped_testrun" / "run_min_zone"
    top.mkdir(parents=True)
    (top / "best_model.zip").write_bytes(b"stub")

    models = list_checkpoints(tmp_path)
    assert any(m["path"].endswith("shaped_testrun/run_min_zone/best_model.zip") for m in models)
    assert find_default_checkpoint(tmp_path) == (top / "best_model.zip")


