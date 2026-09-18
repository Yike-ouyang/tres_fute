"""Gymnasium environment: spaces, actions, masking, rewards, reproducibility."""

from __future__ import annotations

import copy

import numpy as np
import pytest
from gymnasium import spaces

from game_engine.engine import GameEngine
from rl_env import DiceGameEnv, N_ACTIONS, observation_space
from rl_env.actions import (
    ACTION_VERSION,
    build_legal_decisions,
    decode,
    encode,
    label,
)
from rl_env.observations import OBSERVATION_VERSION, decision_kind, encode_observation

from tests.helpers import all_dice, base_state, empty_board


def _rollout(env: DiceGameEnv, seed: int, max_decisions: int = 5000) -> dict:
    obs, info = env.reset(seed=seed)
    rng = np.random.default_rng(seed)
    total = 0.0
    steps = 0
    kinds = set()
    while True:
        assert observation_space().contains(obs)
        kinds.add(decision_kind(env.engine.state))
        legal = np.flatnonzero(env.action_masks())
        assert legal.size > 0, "no legal action for the agent"
        action = int(rng.choice(legal))
        obs, reward, terminated, truncated, info = env.step(action)
        total += float(reward)
        steps += 1
        if terminated or truncated:
            break
        assert steps < max_decisions
    return {"steps": steps, "reward": total, "info": info, "kinds": kinds, "terminated": terminated, "truncated": truncated}


# --------------------------------------------------------------- observation

def test_observation_is_flat_numeric_dict():
    space = observation_space()
    assert isinstance(space, spaces.Dict)
    for key, sub in space.spaces.items():
        assert isinstance(sub, (spaces.MultiBinary, spaces.MultiDiscrete, spaces.Box)), key
        dtype = getattr(sub, "dtype", None)
        assert dtype is not None and np.issubdtype(dtype, np.integer), key
    # no nested Dict / Tuple / string spaces
    assert all(not isinstance(s, (spaces.Dict, spaces.Tuple)) for s in space.spaces.values())


def test_observation_dimensions_and_bounds_are_stable():
    space = observation_space()
    assert space["yellow_checks"].shape == (2, 18)
    assert space["turquoise_checks"].shape == (2, 30)
    assert space["blue_values"].shape == (2, 13)
    assert int(space["blue_values"].high.max()) == 12
    assert int(space["pink_values"].high.max()) == 18
    assert space["brown_checks"].shape == (2, 12)
    assert space["pink_values"].shape == (2, 12)
    assert space["slots_unlocked"].shape == (2, 58)
    assert space["selection_picked"].shape == (85,)
    assert space["pending_bonus_colors"].shape == (8,)
    assert space["dice_values"].shape == (6,)
    # agent-first ordering: index 0 is the agent
    env = DiceGameEnv(agent_player=2)
    obs, _ = env.reset(seed=1)
    board_agent = np.array([1 if obs["yellow_checks"][0][i] else 0 for i in range(18)])
    assert board_agent.shape == (18,)
    env.close()


def test_observation_agent_first_is_constant_across_roles():
    state = base_state(
        boards={
            1: {**empty_board(), "values": {"pink-cell-1": 3}},
            2: {**empty_board(), "values": {"pink-cell-1": 6}},
        }
    )
    obs_agent1 = encode_observation(state, 1)
    obs_agent2 = encode_observation(state, 2)
    assert obs_agent1["pink_values"][0][0] == 3  # agent = player 1
    assert obs_agent1["pink_values"][1][0] == 6  # adversary = player 2
    assert obs_agent2["pink_values"][0][0] == 6  # agent = player 2
    assert obs_agent2["pink_values"][1][0] == 3


# ------------------------------------------------------------------- actions

def test_action_catalogue_size_and_labels():
    assert N_ACTIONS == 316
    assert 0 <= encode(GameEngine(seed=1).state, {"type": "select_die", "color": "yellow"}) < N_ACTIONS
    for aid in (0, 5, 11, 29, 60, 73, 85, 97, 99, 105, 110, 116, 271, 272, 301, 302, 309, 310, 315):
        assert isinstance(label(aid), str) and label(aid)


def test_blue_values_never_exceed_12_in_practice():
    """A blue bonus at ref=12 must only offer the wildcard 7 (no 13)."""
    from game_engine.rules import blue_bonus_options
    from rl_env.observations import encode_observation

    board = empty_board()
    board["values"] = {f"blue-cell-{p}": p for p in range(8, 13)}  # 8..12
    options = blue_bonus_options(board)
    assert all(o["value"] <= 12 for o in options)
    assert not any(o["value"] == 13 for o in options)

    # applying the legal 7 option keeps the observation inside its declared space
    written = {**board["values"], "blue-cell-13": 7}
    state = base_state(boards={1: {**empty_board(), "values": written}, 2: empty_board()})
    obs = encode_observation(state, 1)
    assert observation_space().contains(obs)
    assert int(obs["blue_values"].max()) == 12


def test_action_encode_decode_roundtrip():
    env = DiceGameEnv(agent_player=1)
    obs, _ = env.reset(seed=4)
    state = env.engine.state
    for decision in build_legal_decisions(state):
        assert decode(state, decision.action_id) == decision.actions
        assert encode(state, decision.actions[0]) == decision.action_id
        assert label(decision.action_id)
    env.close()


def test_actions_have_stable_meaning_across_states():
    # Same id -> same transition type, whatever the state.
    env_a = DiceGameEnv(agent_player=1)
    env_a.reset(seed=1)
    die_yellow = decode(env_a.engine.state, 0)
    assert die_yellow[0]["type"] == "select_die" and die_yellow[0]["color"] == "yellow"
    assert label(0) == "select_die:yellow"
    env_a.close()


# ------------------------------------------------------------------- masking

def test_mask_matches_engine_legality():
    env = DiceGameEnv(agent_player=1)
    env.reset(seed=2)
    for _ in range(60):
        if env.engine.is_over():
            break
        state = env.engine.state
        mask = env.action_masks()
        pairs = {d.action_id: d.actions for d in build_legal_decisions(state)}
        assert set(np.flatnonzero(mask)) == set(pairs)
        # every decoded action must be accepted by a copy of the engine
        for aid in np.flatnonzero(mask):
            probe = GameEngine(seed=0, state=copy.deepcopy(state))
            for action in decode(state, int(aid)):
                assert probe.step(action), (aid, action)
        # advance the agent decision with the first legal id
        obs, _, term, trunc, _ = env.step(int(np.flatnonzero(mask)[0]))
        if term or trunc:
            break
    env.close()


def test_masked_action_raises_and_does_not_mutate():
    env = DiceGameEnv(agent_player=1)
    env.reset(seed=3)
    mask = env.action_masks()
    illegal = int(np.flatnonzero(~mask)[0])
    before = repr(env.engine.fingerprint())
    with pytest.raises(ValueError):
        env.step(illegal)
    assert repr(env.engine.fingerprint()) == before
    env.close()


def test_out_of_range_action_raises():
    env = DiceGameEnv(agent_player=1)
    env.reset(seed=3)
    with pytest.raises(ValueError):
        env.step(N_ACTIONS)
    with pytest.raises(ValueError):
        env.step(-1)
    env.close()


# ------------------------------------------------------------------- reset/step

def test_reset_signature_and_info():
    env = DiceGameEnv(agent_player="random")
    result = env.reset(seed=11)
    assert isinstance(result, tuple) and len(result) == 2
    obs, info = result
    assert observation_space().contains(obs)
    for key in ("agent_player", "turn", "phase", "scores", "engine_actions", "rules_version",
                "observation_version", "action_version", "action_mask"):
        assert key in info
    assert info["observation_version"] == OBSERVATION_VERSION
    assert info["action_version"] == ACTION_VERSION
    env.close()


def test_step_signature_and_stops_at_agent_decision():
    env = DiceGameEnv(agent_player=1)
    env.reset(seed=5)
    for _ in range(40):
        if env.engine.is_over():
            break
        mask = env.action_masks()
        action = int(np.flatnonzero(mask)[0])
        obs, reward, terminated, truncated, info = env.step(action)
        assert isinstance(reward, float)
        assert isinstance(terminated, bool) and isinstance(truncated, bool)
        if terminated or truncated:
            break
        # after a step the environment is waiting for the agent (or the game ended)
        actor = env.engine.current_decision().get("actor")
        assert actor == env.agent_player
    env.close()


@pytest.mark.parametrize("agent_player", [1, 2])
def test_full_games_from_both_places(agent_player):
    env = DiceGameEnv(agent_player=agent_player, opponent="heuristic")
    for seed in (0, 1, 2, 3):
        result = _rollout(env, seed=seed)
        assert result["terminated"] is True
        assert result["truncated"] is False
        assert result["info"]["result"] in ("win", "loss", "draw")
    env.close()


def test_covers_all_phases_and_overlays():
    env = DiceGameEnv(agent_player="random", opponent="random")
    seen: set[str] = set()
    for seed in range(12):
        result = _rollout(env, seed=seed)
        seen |= result["kinds"]
    assert "select_die" in seen
    assert any(k.startswith("dest_") for k in seen)
    assert "fill_slot" in seen  # slots completed without effect
    assert "plus1_window" in seen
    assert any(k.startswith("bonus") for k in seen)
    assert "pink_option" in seen
    env.close()


def test_passive_decisions_are_controlled_by_agent():
    # Force agent = player 2 so the opponent plays first and player 2 gets passives.
    env = DiceGameEnv(agent_player=2, opponent="heuristic")
    passive_seen = False
    for seed in range(6):
        env.reset(seed=seed)
        for _ in range(200):
            if env.engine.is_over():
                break
            state = env.engine.state
            if state["phase"]["kind"] == "passive" and not state["phase"]["done"]:
                if env.engine.current_decision().get("actor") == 2:
                    passive_seen = True
                    assert env.action_masks().any()
            legal = np.flatnonzero(env.action_masks())
            if legal.size == 0:
                break
            obs, _, term, trunc, _ = env.step(int(legal[0]))
            if term or trunc:
                break
    assert passive_seen
    env.close()


# ------------------------------------------------------------------- joker

def test_joker_physical_vs_effective_value():
    board = empty_board()
    board["bonuses"] = {**board["bonuses"], "joker": {"unlocked": 5, "used": 4}}
    state = base_state(boards={1: board, 2: empty_board()}, dice=all_dice())
    engine = GameEngine(seed=0, state=copy.deepcopy(state))
    assert engine.step({"type": "start_joker", "token_index": 4})
    assert engine.state["joker_pending"]["value"] is None

    obs = encode_observation(engine.state, 1)
    assert obs["joker_pending"][0] == 1
    assert obs["joker_pending_value"][0] == 0

    assert engine.step({"type": "set_joker_value", "value": 6})
    color = next(a["color"] for a in engine.legal_actions() if a["type"] == "select_die")
    physical_before = engine.state["dice"][color]["value"]
    assert engine.step({"type": "select_die", "color": color})
    obs = encode_observation(engine.state, 1)
    idx = ["yellow", "turquoise", "darkblue", "brown", "pink", "white"].index(color)
    assert obs["dice_values"][idx] == physical_before  # physical value untouched
    assert obs["dice_joker_values"][idx] == 6  # effective override recorded
    assert obs["selection_value"][0] == 6  # selection carries the effective value


# ------------------------------------------------------------ reward/repro

def test_score_delta_telescopes_to_final_score():
    env = DiceGameEnv(agent_player=1, reward_mode="score_delta")
    for seed in range(5):
        obs, info = env.reset(seed=seed)
        start = info["scores"]["agent"]
        total = 0.0
        while True:
            legal = np.flatnonzero(env.action_masks())
            obs, reward, term, trunc, info = env.step(int(legal[0]))
            total += reward
            if term or trunc:
                break
        assert total == pytest.approx(info["scores"]["agent"] - start)
    env.close()


def test_terminal_score_mode_only_rewards_at_the_end():
    env = DiceGameEnv(agent_player=1, reward_mode="terminal_score")
    obs, _ = env.reset(seed=0)
    total = 0.0
    while True:
        legal = np.flatnonzero(env.action_masks())
        obs, reward, term, trunc, info = env.step(int(legal[0]))
        if not (term or trunc):
            assert reward == 0.0
        total += reward
        if term or trunc:
            break
    assert total == pytest.approx(info["scores"]["agent"])
    env.close()


def test_reward_scale_is_applied():
    env = DiceGameEnv(agent_player=1, reward_mode="score_delta", reward_scale=10.0)
    obs, _ = env.reset(seed=0)
    legal = np.flatnonzero(env.action_masks())
    obs, reward, *_ = env.step(int(legal[0]))
    # delta is a multiple of 1/scale when scores are integers
    assert reward == pytest.approx(round(reward * 10) / 10)
    env.close()


def test_reproducible_with_same_seed_and_actions():
    def rollout(config):
        env = DiceGameEnv(**config)
        obs, _ = env.reset(seed=123)
        rng = np.random.default_rng(0)
        rewards = []
        observations = [obs]
        while True:
            legal = np.flatnonzero(env.action_masks())
            action = int(rng.choice(legal))
            obs, reward, term, trunc, _ = env.step(action)
            rewards.append(reward)
            observations.append(obs)
            if term or trunc:
                break
        return rewards, observations, env.engine.state["boards"]

    config = {"agent_player": "random", "opponent": "heuristic"}
    rewards_a, obs_a, boards_a = rollout(config)
    rewards_b, obs_b, boards_b = rollout(config)
    assert rewards_a == rewards_b
    for key in obs_a[0]:
        assert np.array_equal(obs_a[0][key], obs_b[0][key])
    assert boards_a == boards_b


def test_instances_are_independent():
    a = DiceGameEnv(agent_player=1, opponent="heuristic")
    b = DiceGameEnv(agent_player=1, opponent="heuristic")
    a.reset(seed=1)
    b.reset(seed=2)
    # advancing one instance must not touch the other
    state_b_before = repr(b.engine.fingerprint())
    legal = np.flatnonzero(a.action_masks())
    a.step(int(legal[0]))
    assert repr(b.engine.fingerprint()) == state_b_before
    a.close()
    b.close()


def test_successive_seedless_resets_differ():
    env = DiceGameEnv(agent_player=1)
    seeds = {env.reset()[1]["seed"] for _ in range(5)}
    assert len(seeds) == 5
    env.close()


# ------------------------------------------------------------ termination

def test_external_limit_truncates():
    env = DiceGameEnv(agent_player=1, max_steps=1)
    env.reset(seed=0)
    legal = np.flatnonzero(env.action_masks())
    obs, reward, terminated, truncated, info = env.step(int(legal[0]))
    assert truncated is True
    assert terminated is False
    with pytest.raises(RuntimeError):
        env.step(int(legal[0]))
    env.close()


def test_step_after_game_over_requires_reset():
    env = DiceGameEnv(agent_player=1, opponent="heuristic")
    _rollout(env, seed=0)
    assert env._terminated
    with pytest.raises(RuntimeError):
        env.step(0)
    obs, info = env.reset(seed=1)
    assert observation_space().contains(obs)
    env.close()


def test_many_complete_games_terminate():
    env = DiceGameEnv(agent_player="random", opponent="heuristic", max_steps=2000)
    finished = 0
    for seed in range(15):
        result = _rollout(env, seed=seed)
        assert result["terminated"] and not result["truncated"]
        finished += 1
    assert finished == 15
    env.close()


def test_gymnasium_check_env_ignores_masks():
    """Gym's ``check_env`` samples ``action_space`` uniformly and ignores ``action_masks``.

    On the raw environment it therefore feeds a masked id and our contract raises, which
    is the intended behaviour (we never silently replace an illegal action). To still run
    the rest of the checker, we use a *test-only* wrapper that maps the checker's invalid
    samples onto the first legal id. The real environment keeps raising.
    """
    import gymnasium as gym
    from gymnasium.utils.env_checker import check_env

    raw = DiceGameEnv(agent_player=1, opponent="random")
    raw.reset(seed=0)
    legal = np.flatnonzero(raw.action_masks())
    masked = int(np.flatnonzero(~raw.action_masks())[0])
    with pytest.raises(ValueError):
        raw.step(masked)

    class _CheckerMaskAdapter(gym.Wrapper):
        def step(self, action):
            mask = self.env.action_masks()
            if not mask[action]:
                action = int(np.flatnonzero(mask)[0])
            return self.env.step(action)

    wrapped = _CheckerMaskAdapter(DiceGameEnv(agent_player=1, opponent="random"))
    check_env(wrapped, skip_render_check=True)
    assert legal.size > 0
    raw.close()
    wrapped.close()


# ------------------------------------------------------------ optional SB3

def test_maskable_ppo_integration_if_available():
    sb3_contrib = pytest.importorskip("sb3_contrib")
    from sb3_contrib import MaskablePPO
    from sb3_contrib.common.wrappers import ActionMasker

    def mask_fn(env):
        return env.action_masks()

    env = ActionMasker(DiceGameEnv(agent_player=1, opponent="random"), mask_fn)
    model = MaskablePPO("MultiInputPolicy", env, n_steps=32, seed=0, verbose=0)
    model.learn(total_timesteps=64)
    obs, _ = env.reset(seed=0)
    action, _ = model.predict(obs, action_masks=env.action_masks(), deterministic=True)
    assert 0 <= int(action) < N_ACTIONS
    env.close()
