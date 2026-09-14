"""FastAPI: idempotence, versions, two games, engine ≡ API on imposed dice."""

from __future__ import annotations

import copy
import random

from fastapi.testclient import TestClient

from api.app import app, inject_engine
from api.store import store
from game_engine.engine import GameEngine
from game_engine.legal import legal_actions
from simulation.policy import restrict_active_die_select

from tests.helpers import all_dice, base_state


def _client() -> TestClient:
    store._games.clear()
    return TestClient(app)


def test_health():
    r = _client().get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_and_get_game():
    c = _client()
    created = c.post("/games", json={"seed": 11}).json()
    assert created["rulesVersion"] == "1.1"
    assert created["state"]["globalTurn"] == 1
    assert created["legalActions"]
    got = c.get(f"/games/{created['id']}").json()
    assert got["version"] == created["version"]
    assert got["seed"] == 11


def test_idempotent_command_and_stale_version():
    c = _client()
    g = c.post("/games", json={"seed": 3}).json()
    gid, ver = g["id"], g["version"]
    select = next(a for a in g["legalActions"] if a["type"] == "select_die")
    body = {"command_id": "cmd-1", "expected_version": ver, "action": select}
    r1 = c.post(f"/games/{gid}/actions", json=body).json()
    r2 = c.post(f"/games/{gid}/actions", json=body).json()
    assert r1["version"] == r2["version"]
    assert r1["state"]["selection"] == r2["state"]["selection"]
    stale = c.post(
        f"/games/{gid}/actions",
        json={"command_id": "cmd-2", "expected_version": ver, "action": {"type": "confirm_move"}},
    )
    assert stale.status_code == 409
    assert stale.json()["error"] == "stale_version"


def test_two_independent_games():
    c = _client()
    a = c.post("/games", json={"seed": 1}).json()
    b = c.post("/games", json={"seed": 2}).json()
    assert a["id"] != b["id"]
    sel = next(x for x in a["legalActions"] if x["type"] == "select_die")
    c.post(
        f"/games/{a['id']}/actions",
        json={"command_id": "a1", "expected_version": a["version"], "action": sel},
    )
    b2 = c.get(f"/games/{b['id']}").json()
    assert b2["state"]["selection"] is None


def test_engine_equals_api_imposed_dice():
    state = base_state(
        dice=all_dice({"pink": {"value": 4, "location": "available"}}),
        selection={
            "color": "pink",
            "value": 4,
            "acting_color": "pink",
            "legal": ["pink-cell-1"],
            "picked": ["pink-cell-1"],
            "max_pick": 1,
            "elimination_value": 4,
        },
    )
    direct = GameEngine(seed=0, state=copy.deepcopy(state))
    via_api = GameEngine(seed=0, state=copy.deepcopy(state))
    c = _client()
    gid = inject_engine(via_api)
    rec = store.get(gid)
    assert rec is not None
    direct.step({"type": "confirm_move"})
    r = c.post(
        f"/games/{gid}/actions",
        json={"command_id": "p", "expected_version": rec.version, "action": {"type": "confirm_move"}},
    )
    assert r.status_code == 200
    assert r.json()["state"]["boards"]["1"]["values"]["pink-cell-1"] == 2
    assert direct.state["boards"][1]["values"]["pink-cell-1"] == 2
    assert r.json()["scores"]["1"]["pink"] == 2


def test_policy_does_not_shrink_engine_legal_actions():
    eng = GameEngine(seed=1)
    acts = legal_actions(eng.state)
    selects = [a for a in acts if a["type"] == "select_die"]
    assert len(selects) >= 2
    filtered = restrict_active_die_select(eng.state, acts)
    # Engine still lists every playable die, including the physical max.
    assert selects == [a for a in legal_actions(eng.state) if a["type"] == "select_die"]
    if any(
        eng.state["dice"][a["color"]]["value"]
        < max(eng.state["dice"][c]["value"] for c in eng.state["dice"] if eng.state["dice"][c]["location"] == "available")
        for a in selects
    ):
        assert len([a for a in filtered if a["type"] == "select_die"]) < len(selects)


def test_manual_action_rejected_while_advancing():
    c = _client()
    g = c.post("/games", json={"seed": 5}).json()
    rec = store.get(g["id"])
    assert rec is not None
    rec.advancing = True
    blocked = c.post(
        f"/games/{g['id']}/actions",
        json={
            "command_id": "nope",
            "expected_version": g["version"],
            "action": {"type": "confirm_move"},
        },
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"] == "advance_in_progress"


def test_advance_completes_without_http_per_move():
    c = _client()
    g = c.post("/games", json={"seed": 5}).json()
    r = c.post(
        f"/games/{g['id']}/advance",
        json={"n": 1, "command_id": "adv", "expected_version": g["version"]},
    )
    assert r.status_code == 200
    got = c.get(f"/games/{g['id']}").json()
    assert got["advance"]["running"] is False
    assert got["advance"]["completed"] >= 1 or got["state"]["phase"]["kind"] == "game-over"
