"""Play complete episodes without training, FastAPI or a learned agent.

The demonstration agent picks **uniformly among the unmasked action ids**. This is
uniform over the discrete catalogue (not over complete moves or strategies): a
decision made of several engine commands is a single id, so it is not equivalent
to sampling atomic engine actions.

Example::

    python rl_env/run_episode.py --episodes 3 --agent-player random --opponent heuristic --render
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rl_env import ACTION_VERSION, N_ACTIONS, OBSERVATION_VERSION, DiceGameEnv
from rl_env.actions import label


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run complete DiceGameEnv episodes with a random legal agent.")
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--seed", type=int, default=None, help="Base seed (episode i uses seed + i)")
    parser.add_argument("--agent-player", default="random", choices=["1", "2", "random"])
    parser.add_argument("--opponent", default="heuristic", choices=["heuristic", "random"])
    parser.add_argument("--reward-mode", default="score_delta", choices=["score_delta", "terminal_score"])
    parser.add_argument("--reward-scale", type=float, default=1.0)
    parser.add_argument("--max-steps", type=int, default=None, help="External truncation limit")
    parser.add_argument("--show-decisions", action="store_true", help="Print every chosen action label")
    parser.add_argument("--render", action="store_true", help="Render the final state of each episode")
    return parser.parse_args(argv)


def run_episode(env: DiceGameEnv, seed: int | None, rng: np.random.Generator, show: bool) -> dict:
    obs, info = env.reset(seed=seed)
    env.action_masks()
    total_reward = 0.0
    steps = 0
    started = time.perf_counter()
    while True:
        legal = np.flatnonzero(env.action_masks())
        if legal.size == 0:
            raise RuntimeError("no legal action returned to the agent")
        action_id = int(rng.choice(legal))
        if show:
            print(f"    step {steps:>3} {label(action_id)}")
        obs, reward, terminated, truncated, info = env.step(action_id)
        total_reward += reward
        steps += 1
        if terminated or truncated:
            break
    elapsed = time.perf_counter() - started
    return {
        "steps": steps,
        "reward": total_reward,
        "elapsed": elapsed,
        "terminated": terminated,
        "truncated": truncated,
        "info": info,
    }


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    agent_player = args.agent_player if args.agent_player == "random" else int(args.agent_player)
    env = DiceGameEnv(
        agent_player=agent_player,
        opponent=args.opponent,
        reward_mode=args.reward_mode,
        reward_scale=args.reward_scale,
        max_steps=args.max_steps,
    )
    print(f"N_ACTIONS={N_ACTIONS} observation_version={OBSERVATION_VERSION} action_version={ACTION_VERSION}")
    rng = np.random.default_rng(args.seed if args.seed is not None else 0)
    for episode in range(args.episodes):
        seed = None if args.seed is None else args.seed + episode
        result = run_episode(env, seed, rng, args.show_decisions)
        info = result["info"]
        print(
            f"episode {episode}: agent=P{info['agent_player']} steps={result['steps']} "
            f"reward={result['reward']:.2f} agent={info['scores']['agent']} "
            f"adversary={info['scores']['adversary']} result={info.get('result', 'n/a')} "
            f"terminated={result['terminated']} truncated={result['truncated']} "
            f"time={result['elapsed']:.3f}s"
        )
        if args.render:
            env.render()
    env.close()


if __name__ == "__main__":
    main()
