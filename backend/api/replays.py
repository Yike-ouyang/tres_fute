"""Read-only replay service: serves JSON traces produced by ``rl_env/replay.py``.

No ML dependency here: traces are pre-generated files under ``<runs>/<run>/replays``.
The id must look like a safe filename and exist in a scanned manifest, so there is
no path traversal.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["replays"])

_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def _runs_root() -> Path:
    override = os.environ.get("TRES_FUTE_RUNS_DIR")
    if override:
        return Path(override)
    # backend/api/replays.py -> backend/runs
    return Path(__file__).resolve().parents[1] / "runs"


def _scan() -> dict[str, dict[str, Any]]:
    root = _runs_root()
    found: dict[str, dict[str, Any]] = {}
    if not root.exists():
        return found
    for manifest_path in sorted(root.glob("*/replays/index.json")):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for entry in manifest.get("replays", []):
            replay_id = entry.get("id")
            file_name = entry.get("file")
            if not replay_id or not file_name or not _ID_RE.match(str(replay_id)):
                continue
            found[str(replay_id)] = {"entry": entry, "path": manifest_path.parent / str(file_name)}
    return found


@router.get("/replays")
def list_replays() -> dict[str, Any]:
    """List available replays (from every run manifest)."""
    return {"replays": [value["entry"] for value in _scan().values()]}


@router.get("/replays/{replay_id}")
def get_replay(replay_id: str) -> Any:
    """Return one full replay trace."""
    if not _ID_RE.match(replay_id):
        raise HTTPException(status_code=404, detail="Replay introuvable")
    found = _scan().get(replay_id)
    if not found:
        raise HTTPException(status_code=404, detail="Replay introuvable")
    path: Path = found["path"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Fichier de replay introuvable")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail="Replay corrompu") from exc
