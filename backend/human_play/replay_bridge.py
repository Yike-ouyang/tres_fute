"""Pont vers le format de trace de ``rl_env/replay.py``.

Le mode ``replay`` et les parties humaines enregistrées partagent exactement le
même format JSON (mêmes clés racine), afin que l'onglet **Replay** du frontend
les charge de façon identique via ``GET /replays``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rl_env_2.actions import ACTION_VERSION_2, N_ACTIONS_2
from rl_env_2.observations import OBSERVATION_VERSION_2

from .session import HumanGameSession

RUN_NAME = "human_play"


def _runs_root() -> Path:
    # backend/human_play/replay_bridge.py -> <repo>/agent/runs
    return Path(__file__).resolve().parents[2] / "agent" / "runs"


def default_replays_dir(runs_root: Path | None = None) -> Path:
    """Répertoire découvert par ``GET /replays`` (``runs/*/replays/index.json``)."""
    root = Path(runs_root) if runs_root else _runs_root()
    return root / RUN_NAME / "replays"


def _result(scores: dict[str, Any]) -> str:
    if scores["agent"] > scores["adversary"]:
        return "win"
    if scores["agent"] < scores["adversary"]:
        return "loss"
    return "draw"


def build_trace(session: HumanGameSession, *, run_name: str = RUN_NAME) -> dict[str, Any]:
    """Trace au format ``rl_env/replay.py`` (mêmes clés racine)."""
    final = session.final_scores()
    scores = {"agent": final["agent"], "adversary": final["adversary"]}
    return {
        "run": run_name,
        "checkpoint": session.checkpoint,
        "seed": session.engine.seed,
        "agent_player": session.human_player,
        "rules_version": session.engine.rules_version,
        "observation_version": OBSERVATION_VERSION_2,
        "action_version": ACTION_VERSION_2,
        "n_actions": N_ACTIONS_2,
        "initial_state": session.trace_initial,
        "frames": session.trace,
        "final_scores": scores,
        "result": _result(scores),
        "agent_decisions": session.human_decisions,
        "created": datetime.now(timezone.utc).isoformat(),
    }


def _update_manifest(out_dir: Path, entry: dict[str, Any]) -> None:
    manifest_path = out_dir / "index.json"
    manifest: dict[str, Any] = {"replays": []}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = {"replays": []}
    manifest["replays"] = [r for r in manifest.get("replays", []) if r.get("id") != entry["id"]]
    manifest["replays"].append(entry)
    manifest["replays"].sort(key=lambda r: str(r.get("id", "")))
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def save_trace(
    session: HumanGameSession,
    path: str | Path | None = None,
    runs_root: Path | None = None,
) -> dict[str, Any]:
    """Écrit la trace + met à jour ``index.json`` ; renvoie ``{replay_id, file, trace}``.

    ``path`` peut être un répertoire (défaut : ``agent/runs/human_play/replays``)
    ou un fichier ``*.json``.
    """
    target = Path(path) if path else default_replays_dir(runs_root)
    if target.suffix == ".json":
        out_dir = target.parent
        file_name = target.name
    else:
        out_dir = target
        file_name = ""
    out_dir.mkdir(parents=True, exist_ok=True)

    trace = build_trace(session)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    replay_id = f"{RUN_NAME}_seed{trace['seed']}_p{trace['agent_player']}_{stamp}"
    if not file_name:
        file_name = f"{replay_id}.json"

    (out_dir / file_name).write_text(
        json.dumps(trace, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    _update_manifest(
        out_dir,
        {
            "id": replay_id,
            "run": trace["run"],
            "checkpoint": trace["checkpoint"],
            "seed": trace["seed"],
            "agent_player": trace["agent_player"],
            "file": file_name,
            "agent_decisions": trace["agent_decisions"],
            "frames": len(trace["frames"]),
            "final_scores": trace["final_scores"],
            "result": trace["result"],
        },
    )
    return {"replay_id": replay_id, "file": str(out_dir / file_name), "trace": trace}


__all__ = ["build_trace", "default_replays_dir", "save_trace", "RUN_NAME"]
