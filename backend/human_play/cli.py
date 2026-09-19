"""CLI des trois modes de jeu : ``play``, ``vs-ai``, ``replay``.

Exemples::

    python -m human_play.cli play
    python -m human_play.cli vs-ai --agent-player 1 --checkpoint agent/runs/.../best_model.zip
    python -m human_play.cli replay --run agent/runs/essai_01 --seed 1000000

Options communes : ``--checkpoint``, ``--agent-player {1,2}``, ``--seed``,
``--save <path>``, ``--render {text,json}``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .session import HumanGameSession
from .replay_bridge import build_trace, save_trace

_DICE_COLORS = ("yellow", "turquoise", "darkblue", "brown", "pink", "white")


def _render_text(session: HumanGameSession) -> None:
    state = session.engine.state
    scores = session.final_scores()
    phase = state["phase"]
    actor = state.get("phase", {}).get("player")
    print("-" * 68)
    print(
        f"Tour {state['global_turn']} | phase={phase['kind']} | "
        f"scores {scores['scores_full']['1']['total']} (P1) - "
        f"{scores['scores_full']['2']['total']} (P2)"
    )
    dice = " ".join(
        f"{c}:{state['dice'][c]['value']}" for c in _DICE_COLORS if state["dice"][c]["location"] != "discarded"
    )
    if dice:
        print(f"Dés      : {dice}")
    if state.get("message"):
        print(f"Message  : {state['message']}")


def _print_actions(actions: list[dict[str, Any]]) -> None:
    for i, action in enumerate(actions, start=1):
        extra = " (choix)" if action.get("factorised_step1") else ""
        print(f"  [{i:>3}] {action['label']}{extra}")


def _prompt_action(session: HumanGameSession) -> int | None:
    actions = session.legal_actions()
    if not actions:
        return None
    _print_actions(actions)
    while True:
        try:
            raw = input("Action (numéro, q=quitter) : ").strip()
        except EOFError:
            return None
        if raw.lower() in ("q", "quit", "exit"):
            return None
        if not raw.isdigit():
            print("Entrée invalide.")
            continue
        idx = int(raw)
        if 1 <= idx <= len(actions):
            return int(actions[idx - 1]["id"])
        print("Numéro hors bornes.")


def _run_session(session: HumanGameSession, *, render: str) -> None:
    guard = 0
    while not session.is_over():
        if render == "json":
            print(json.dumps(session.state_json(), ensure_ascii=False))
        else:
            _render_text(session)
            if session.opponent_kind == "ai" and session._last_ai:
                last = session._last_ai[-1]
                if last.get("kind") == "move":
                    print(f"IA joue  : {last.get('label', '?')} ({last.get('id', '?')})")
        action_id = _prompt_action(session)
        if action_id is None:
            print("Partie interrompue.")
            return
        session.step(action_id)
        guard += 1
        if guard > 2000:
            print("Garde atteinte, arrêt.")
            return
    if render == "json":
        print(json.dumps(session.state_json(), ensure_ascii=False))
    else:
        _render_text(session)
        scores = session.final_scores()
        print(f"\nFin de partie : vous {scores['agent']} - adversaire {scores['adversary']}")
        print(f"Résultat : {build_trace(session)['result']}")


def cmd_play(args: argparse.Namespace) -> None:
    session = HumanGameSession(
        agent_player=1, opponent_kind="human", seed=args.seed, trace=True
    )
    _run_session(session, render=args.render)
    _maybe_save(session, args)


def cmd_vs_ai(args: argparse.Namespace) -> None:
    agent_player = args.agent_player
    if agent_player is None:
        raw = input("Votre siège (1 ou 2) : ").strip()
        agent_player = int(raw) if raw in ("1", "2") else 1
    session = HumanGameSession(
        agent_player=agent_player,
        opponent_kind="ai",
        checkpoint=args.checkpoint,
        seed=args.seed,
        trace=True,
    )
    _run_session(session, render=args.render)
    _maybe_save(session, args)


def _maybe_save(session: HumanGameSession, args: argparse.Namespace) -> None:
    path = args.save
    if path is None:
        answer = input("Enregistrer la trace ? (chemin ou vide) : ").strip()
        path = answer or None
    if path:
        result = save_trace(session, path)
        print(f"Replay enregistré : {result['replay_id']} -> {result['file']}")


def cmd_replay(args: argparse.Namespace) -> None:
    from rl_env.replay import reconstruct

    run = Path(args.run).resolve()
    if not (run / "config.json").exists():
        raise SystemExit(f"run invalide (config.json manquant) : {run}")
    trace = reconstruct(run, args.checkpoint, args.seed, args.agent_player or 1)
    frames = trace["frames"]
    index = 0
    while True:
        _render_frame(trace, index)
        try:
            key = input("[n]ext / [p]rev / [q]uit : ").strip().lower()
        except EOFError:
            return
        if key in ("q", "quit"):
            return
        if key == "n" and index < len(frames):
            index += 1
        elif key == "p" and index > 0:
            index -= 1


def _render_frame(trace: dict[str, Any], index: int) -> None:
    state = trace["initial_state"] if index == 0 else trace["frames"][index - 1]["state"]
    scores = state["boards"]
    print("-" * 68)
    print(f"Frame {index}/{len(trace['frames'])} | tour {state['globalTurn']} | phase {state['phase']['kind']}")
    if index > 0:
        frame = trace["frames"][index - 1]
        print(f"Dernière action : {frame.get('rl', {}).get('label') if frame.get('rl') else frame['action']}")
    print(f"État : {json.dumps(scores)[:120]}…")


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--checkpoint", default=None)
    p.add_argument("--agent-player", type=int, choices=(1, 2), default=None)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--save", default=None, help="Répertoire ou fichier .json")
    p.add_argument("--render", choices=("text", "json"), default="text")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Très Futé — parties humaines.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_play = sub.add_parser("play", help="humain vs humain (hot-seat)")
    _add_common(p_play)
    p_play.set_defaults(func=cmd_play)

    p_ai = sub.add_parser("vs-ai", help="humain vs meilleur modèle")
    _add_common(p_ai)
    p_ai.set_defaults(func=cmd_vs_ai)

    p_replay = sub.add_parser("replay", help="relire une partie")
    p_replay.add_argument("--run", required=True)
    p_replay.add_argument("--checkpoint", default="best_model.zip")
    p_replay.add_argument("--seed", type=int, default=1000000)
    p_replay.add_argument("--agent-player", type=int, choices=(1, 2), default=1)
    p_replay.set_defaults(func=cmd_replay)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
