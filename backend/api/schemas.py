"""Pydantic request models. These are not the engine's internal types."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CreateGameBody(BaseModel):
    seed: int | None = None


class ActionBody(BaseModel):
    command_id: str = Field(min_length=1)
    expected_version: int
    action: dict[str, Any]


class ResetBody(BaseModel):
    command_id: str = Field(min_length=1)
    expected_version: int
    seed: int | None = None


class AdvanceBody(BaseModel):
    n: int = Field(ge=1, le=6)
    command_id: str = Field(min_length=1)
    expected_version: int
