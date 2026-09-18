"""HTTP API around GameEngine. No rules live here — only transport, versions, and locks."""

from __future__ import annotations

import asyncio
import random
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from game_engine.engine import GameEngine
from game_engine.legal import remaining_autoplay_turns
from simulation.policy import run_autoplay

from .replays import router as replays_router
from .schemas import ActionBody, AdvanceBody, CreateGameBody, ResetBody
from .store import GameRecord, store

app = FastAPI(title="Très Futé", version="1.1")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(replays_router)


def snapshot(game_id: str, record: GameRecord) -> dict[str, Any]:
    obs = record.engine.observe()
    return {
        "id": game_id,
        "version": record.version,
        "rulesVersion": record.engine.rules_version,
        "seed": record.engine.seed,
        "events": record.events,
        "remainingTurns": remaining_autoplay_turns(record.engine.state),
        "advance": {
            "running": record.advancing,
            "completed": record.advance_completed,
            "quota": record.advance_quota,
            "message": record.advance_message,
        },
        **obs,
    }


def _conflict(game_id: str, record: GameRecord, reason: str) -> JSONResponse:
    body = snapshot(game_id, record)
    body["error"] = reason
    return JSONResponse(status_code=409, content=body)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/games")
def create_game(body: CreateGameBody = CreateGameBody()) -> dict[str, Any]:
    game_id, record = store.create(seed=body.seed)
    return snapshot(game_id, record)


@app.get("/games/{game_id}")
def get_game(game_id: str) -> dict[str, Any]:
    record = store.get(game_id)
    if not record:
        raise HTTPException(status_code=404, detail="Partie introuvable")
    return snapshot(game_id, record)


@app.post("/games/{game_id}/actions")
async def post_action(game_id: str, body: ActionBody) -> Any:
    record = store.get(game_id)
    if not record:
        raise HTTPException(status_code=404, detail="Partie introuvable")
    async with record.lock:
        if body.command_id in record.commands:
            return record.commands[body.command_id]
        if record.advancing:
            return _conflict(game_id, record, "advance_in_progress")
        if body.expected_version != record.version:
            return _conflict(game_id, record, "stale_version")
        events = record.engine.step(body.action)
        if events:
            record.version += 1
            record.events = events
        else:
            record.events = []
        payload = snapshot(game_id, record)
        record.commands[body.command_id] = payload
        return payload


@app.post("/games/{game_id}/reset")
async def reset_game(game_id: str, body: ResetBody) -> Any:
    record = store.get(game_id)
    if not record:
        raise HTTPException(status_code=404, detail="Partie introuvable")
    async with record.lock:
        if body.command_id in record.commands:
            return record.commands[body.command_id]
        if record.advancing:
            return _conflict(game_id, record, "advance_in_progress")
        if body.expected_version != record.version:
            return _conflict(game_id, record, "stale_version")
        record.engine.new_game(seed=body.seed)
        record.version += 1
        record.events = [{"type": "reset"}]
        record.advance_completed = 0
        record.advance_quota = 0
        record.advance_message = None
        payload = snapshot(game_id, record)
        record.commands[body.command_id] = payload
        return payload


async def _run_advance(game_id: str, n: int) -> None:
    record = store.get(game_id)
    if not record:
        return
    policy_rng = random.Random(record.engine.seed + 17_389)

    def progress(completed: int, quota: int) -> None:
        record.advance_completed = completed
        record.advance_quota = quota
        record.advance_message = f"Avance automatique : {completed} / {quota} tour(s)…"

    try:
        summary = await asyncio.to_thread(run_autoplay, record.engine, n, policy_rng, on_progress=progress)
        async with record.lock:
            record.version += 1
            record.advancing = False
            record.advance_completed = summary["completed"]
            record.advance_message = {
                "game-over": "Avance terminée : partie finie.",
                "quota": f"Avance terminée ({summary['completed']} tour(s)).",
                "blocage": "Avance interrompue : l’état n’a pas changé (blocage).",
                "step-cap": "Avance interrompue : trop d’étapes (protection anti-boucle).",
            }.get(summary["stopped"], summary["stopped"])
            record.events = [{"type": "advance", "summary": summary}]
    except Exception as exc:  # pragma: no cover
        async with record.lock:
            record.advancing = False
            record.advance_message = f"Avance interrompue : {exc}"


@app.post("/games/{game_id}/advance")
async def post_advance(game_id: str, body: AdvanceBody, background_tasks: BackgroundTasks) -> Any:
    record = store.get(game_id)
    if not record:
        raise HTTPException(status_code=404, detail="Partie introuvable")
    async with record.lock:
        if body.command_id in record.commands:
            return record.commands[body.command_id]
        if record.advancing:
            return _conflict(game_id, record, "advance_in_progress")
        if body.expected_version != record.version:
            return _conflict(game_id, record, "stale_version")
        remaining = record.engine.remaining_turns()
        quota = min(body.n, remaining)
        if quota <= 0:
            record.advance_message = "Aucun tour à avancer."
            payload = snapshot(game_id, record)
            record.commands[body.command_id] = payload
            return payload
        record.advancing = True
        record.advance_completed = 0
        record.advance_quota = quota
        record.advance_message = f"Avance automatique : 0 / {quota} tour(s)…"
        record.version += 1
        payload = snapshot(game_id, record)
        record.commands[body.command_id] = payload
        background_tasks.add_task(_run_advance, game_id, quota)
        return payload


def inject_engine(engine: GameEngine) -> str:
    """Test helper: register an engine with imposed dice / state."""
    game_id, _ = store.create(engine=engine)
    return game_id
