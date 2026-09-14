"""In-memory game store. One uvicorn worker; state is lost on restart."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any

from game_engine.engine import GameEngine


@dataclass
class GameRecord:
    engine: GameEngine
    version: int = 1
    events: list[dict[str, Any]] = field(default_factory=list)
    commands: dict[str, dict[str, Any]] = field(default_factory=dict)
    advancing: bool = False
    advance_completed: int = 0
    advance_quota: int = 0
    advance_message: str | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class GameStore:
    def __init__(self) -> None:
        self._games: dict[str, GameRecord] = {}

    def create(self, seed: int | None = None, engine: GameEngine | None = None) -> tuple[str, GameRecord]:
        game_id = str(uuid.uuid4())
        record = GameRecord(engine=engine or GameEngine(seed=seed))
        self._games[game_id] = record
        return game_id, record

    def get(self, game_id: str) -> GameRecord | None:
        return self._games.get(game_id)

    def put(self, game_id: str, record: GameRecord) -> None:
        self._games[game_id] = record


store = GameStore()
