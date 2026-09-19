"""Routes REST des parties humaines (hot-seat, vs IA, sauvegarde replay).

Une session = un :class:`human_play.HumanGameSession` en mémoire. L'IA joue
automatiquement dans ``step`` : le frontend ne voit que les décisions humaines.
Aucun entraînement, aucun gradient : l'API reste en lecture seule côté modèle.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from human_play import HumanGameSession, list_checkpoints, save_trace

from .schemas import HumanPlayCreate, HumanPlaySave, HumanPlayStep

router = APIRouter(tags=["human_play"])

_sessions: dict[str, HumanGameSession] = {}


def _get(session_id: str) -> HumanGameSession:
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session introuvable")
    return session


@router.get("/human_play/models")
def list_models() -> dict[str, Any]:
    """Checkpoints disponibles (run / sous-dossier / fichier / date)."""
    return {"models": list_checkpoints()}


@router.post("/human_play/sessions")
def create_session(body: HumanPlayCreate) -> dict[str, Any]:
    try:
        session = HumanGameSession(
            agent_player=body.agent_player,
            opponent_kind=body.opponent,
            checkpoint=body.checkpoint,
            seed=body.seed,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session_id = str(uuid.uuid4())
    session.session_id = session_id
    _sessions[session_id] = session
    return {"session_id": session_id, "state": session.state_json()}


@router.get("/human_play/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    return _get(session_id).state_json()


@router.get("/human_play/sessions/{session_id}/legal_actions")
def get_legal_actions(session_id: str) -> dict[str, Any]:
    return {"actions": _get(session_id).legal_actions()}


@router.post("/human_play/sessions/{session_id}/step")
def post_step(session_id: str, body: HumanPlayStep) -> dict[str, Any]:
    session = _get(session_id)
    try:
        if body.cancel:
            return session.cancel()
        if body.action_id is None:
            raise HTTPException(status_code=400, detail="action_id requis (ou cancel=true)")
        return session.step(body.action_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/human_play/sessions/{session_id}")
def delete_session(session_id: str) -> dict[str, Any]:
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session introuvable")
    del _sessions[session_id]
    return {"deleted": session_id}


@router.post("/human_play/sessions/{session_id}/save")
def save_session(session_id: str, body: HumanPlaySave) -> dict[str, Any]:
    session = _get(session_id)
    try:
        result = save_trace(session, body.path)
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"écriture impossible: {exc}") from exc
    return {"replay_id": result["replay_id"], "file": result["file"]}
