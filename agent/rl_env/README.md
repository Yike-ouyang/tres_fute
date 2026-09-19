# `rl_env` — Gymnasium environment for Très Futé

This package exposes the **complete two-player game** as a Gymnasium
environment. It calls the Python engine directly: no HTTP, no FastAPI store, no
browser. Rules stay in `game_engine/`; `rl_env/` only adapts them into
observations, a discrete action catalogue, rewards and masking.

---

## 1. Role and data flow

```
        agent (external learning algorithm)
              │  action id (int)
              ▼
  rl_env.DiceGameEnv ──reset/step──► game_engine.GameEngine
        │                                  │  state, legal_actions()
        │  observation (numeric Dict)      │  game_reducer state transitions
        │  reward (rl_env.rewards)         │  compute_score
        │  action mask (rl_env.actions)    ▼
        └──────────────◄──────── fixed opponent (simulation.policy.HeuristicPolicy)
```

- The **agent** owns one player (1, 2, or randomly drawn per episode) and makes
  *all* its decisions: active moves, passive moves, +1 windows, bonus
  resolutions and the pink points/bonus choice.
- The **opponent** is a fixed Python policy (`heuristic` by default, `random` for
  tests). The environment plays the opponent — and every forced/technical
  command — automatically until the agent must decide again.
- The learning algorithm lives **outside**: it reads `(obs, reward, terminated,
  truncated, info)`, updates its network, and calls `reset()`/`step()`. Gymnasium
  never saves a model; that is the job of a future training script.

The environment never re-implements a rule: it only calls `legal_actions()` and
`game_reducer()` through `GameEngine`.

---

## 2. Installation and commands

```bash
cd <repo>                                # repository root (shared venv)
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt  # includes gymnasium + numpy
```

Optional (only for the MaskablePPO integration test / training):

```bash
pip install sb3-contrib stable-baselines3
```

Run the existing test suite (engine, API, simulation and RL environment):

```bash
# tests from backend/ (shared venv activated)
cd backend
pytest
# or only the RL environment
pytest tests/test_rl_env.py
```

Run demonstration episodes (no training, no FastAPI):

```bash
cd agent
python rl_env/run_episode.py --episodes 3 --seed 7 --agent-player random --opponent heuristic --render
python rl_env/run_episode.py --episodes 1 --agent-player 2 --opponent random --show-decisions
```

Options: `--agent-player {1,2,random}`, `--opponent {heuristic,random}`,
`--reward-mode {score_delta,terminal_score}`, `--reward-scale`, `--max-steps`,
`--show-decisions`, `--render`.

> The demonstration agent samples **uniformly among the unmasked ids**. This is
> *not* uniform over strategies or complete moves: a decision made of several
> engine commands is a single id, so it is not equivalent to sampling atomic
> engine actions.

---

## 3. Minimal example

```python
import numpy as np
from rl_env import DiceGameEnv

env = DiceGameEnv(agent_player="random", opponent="heuristic", reward_mode="score_delta")
obs, info = env.reset(seed=0)

mask = env.action_masks()          # bool[N_ACTIONS], True = legal now
action = int(np.flatnonzero(mask)[0])
obs, reward, terminated, truncated, info = env.step(action)

while not (terminated or truncated):
    mask = env.action_masks()
    action = int(np.flatnonzero(mask)[0])   # pick any legal id
    obs, reward, terminated, truncated, info = env.step(action)

print(info["final_scores"], info["result"])
env.close()
```

With MaskablePPO:

```python
from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from rl_env import DiceGameEnv

env = ActionMasker(DiceGameEnv(agent_player="random"), lambda e: e.action_masks())
model = MaskablePPO("MultiInputPolicy", env, n_steps=256)
model.learn(total_timesteps=100_000)
```

---

## 4. Observations

`observation_space()` returns a **flat** `gymnasium.spaces.Dict` of fixed-shape
integer arrays. **Axis 0 of every two-player array is the agent, axis 1 is the
adversary**, regardless of who is active/passive. `OBSERVATION_VERSION = "1.0"`.

Cell index conventions:

- yellow: index `(r-1)*6 + (c-1)` for `yellow-r{r}-c{c}`, `r` 1..3, `c` 1..6;
- turquoise: index `(r-1)*6 + (c-1)`, `r` 1..5, `c` 1..6;
- blue: index `p-1` for `blue-cell-{p}`, `p` 1..13 (centre `blue-cell-7` is never
  written by the rules and stays `0`);
- brown: index `n-1` for `brown-cell-{n}`, `n` 1..12;
- pink: index `n-1` for `pink-cell-{n}`, `n` 1..12.

Dice keep the engine's fixed colour order
`(yellow, turquoise, darkblue, brown, pink, white)` and are **never sorted**.

| Key | Space | dtype | Meaning / indices |
| --- | --- | --- | --- |
| `yellow_checks` | MultiBinary(2, 18) | int8 | per player, yellow cell checked |
| `turquoise_checks` | MultiBinary(2, 30) | int8 | per player, turquoise cell checked |
| `blue_values` | Box(0, 12, (2, 13)) | int16 | per player, blue cell value; `0` = empty |
| `brown_checks` | MultiBinary(2, 12) | int8 | per player, brown cell checked |
| `brown_last_checked` | Box(0, 12, (2,)) | int16 | `0` = none, else last brown position |
| `brown_disabled` | MultiBinary(2, 12) | int8 | per player, skipped brown cells |
| `pink_values` | Box(0, 12, (2, 12)) | int16 | per player, inscribed pink points; `0` = empty |
| `bonuses` | Box(0, 7, (2, 6)) | int16 | `[relance_unl, relance_used, joker_unl, joker_used, plus1_unl, plus1_used]` |
| `slots_unlocked` | MultiBinary(2, 58) | int8 | per player, bonus slots already triggered (catalog order of `bonuses.ALL_SLOTS`) |
| `chosen_count` | Box(0, 3, (2,)) | int8 | dice chosen this turn |
| `chosen_colors` | Box(0, 6, (2, 3)) | int8 | `1..6` = die colour index + 1, `0` = pad |
| `chosen_values` | Box(0, 6, (2, 3)) | int8 | chosen die values, `0` = pad |
| `slot_filled` | MultiBinary(2, 3) | int8 | active slots filled |
| `slot_colors` / `slot_values` | Box(0, 6, (2, 3)) | int8 | active slot die identity |
| `score_total` | Box(0, 10000, (2,)) | int32 | full score (foxes included, per player) |
| `fox_count` | Box(0, 6, (2,)) | int8 | foxes unlocked per player |
| `turn` | Box(0, 6, (1,)) | int8 | global turn |
| `round` | Box(0, 3, (1,)) | int8 | active round (0 outside an active sequence) |
| `phase` | Box(0, 5, (1,)) | int8 | index in `PHASE_KINDS` = `none, active, passive, plus1, fill-slots, game-over` |
| `decision` | Box(0, 18, (1,)) | int8 | index in `DECISION_KINDS` (expected decision) |
| `actor_is_agent` | MultiBinary(1) | int8 | `1` if the pending decision belongs to the agent |
| `active_is_agent` | MultiBinary(1) | int8 | `1` if the agent is the active player |
| `dice_values` | Box(1, 6, (6,)) | int8 | physical value of each die |
| `dice_locations` | Box(0, 2, (6,)) | int8 | `0` available, `1` chosen, `2` discarded |
| `dice_joker_values` | Box(0, 6, (6,)) | int8 | effective override from a joker; `0` = none |
| `die_selected` | MultiBinary(6) | int8 | which die is currently selected |
| `selection_present` | MultiBinary(1) | int8 | a selection is open |
| `selection_color` | Box(0, 6, (1,)) | int8 | physical die colour index + 1; `0` none |
| `selection_acting` | Box(0, 5, (1,)) | int8 | acting colour index + 1 (white resolved); `0` none |
| `selection_value` | Box(0, 12, (1,)) | int8 | effective value of the selection |
| `selection_max_pick` | Box(0, 5, (1,)) | int8 | max cells pickable (turquoise) |
| `selection_elimination` | Box(0, 6, (1,)) | int8 | physical value used for die elimination |
| `selection_picked` | MultiBinary(85) | int8 | picked destinations in the selection catalogue (see below) |
| `selection_legal` | MultiBinary(85) | int8 | legal destinations in the selection catalogue |
| `joker_pending` | MultiBinary(1) | int8 | a joker is being resolved |
| `joker_pending_value` | Box(0, 6, (1,)) | int8 | joker value, `0` = not chosen yet |
| `pink_present` | MultiBinary(1) | int8 | pink points/bonus dialog open |
| `pink_position` | Box(0, 12, (1,)) | int8 | pink cell position 1..12 |
| `pink_effective` | Box(0, 12, (1,)) | int8 | effective die value for the pink cell |
| `pink_multiplier` | Box(0, 3, (1,)) | int8 | pink points multiplier |
| `pink_bonus_kind` | Box(0, 3, (1,)) | int8 | `0` none, `1` cumulative, `2` die, `3` fox |
| `pink_owner_is_agent` | MultiBinary(1) | int8 | who must choose |
| `bonus_present` | MultiBinary(1) | int8 | a bonus resolution is open |
| `bonus_stage` | Box(0, 4, (1,)) | int8 | `chooseColor, chooseValue, placing, noMove` |
| `bonus_color` | Box(0, 6, (1,)) | int8 | bonus die colour index + 1 (includes black); `0` none |
| `bonus_value` | Box(0, 6, (1,)) | int8 | chosen bonus value; `0` none |
| `bonus_owner_is_agent` | MultiBinary(1) | int8 | who must resolve |
| `pending_bonus_count` | Box(0, 8, (1,)) | int8 | queued bonuses (see limitations) |
| `pending_bonus_colors` | Box(0, 6, (8,)) | int8 | queue colours, `0` = pad |
| `pending_bonus_owner_is_agent` | MultiBinary(8) | int8 | queue owners, `0` = pad |

**Selection catalogue** (`selection_picked` / `selection_legal`, 85 bits):
`0..17` yellow cells, `18..30` blue cells, `31..42` brown cells, `43..54` pink
cells, `55..84` turquoise cells (`(r-1)*6 + (c-1)`). A `0`/`1` distinction is
kept: a written value is never confused with an empty cell.

The observation is **not** the JSON view used by React (`serialize.py`) and never
contains RNG internals or future rolls.

---

## 5. Action catalogue

`action_space = Discrete(N_ACTIONS)` with **`N_ACTIONS = 316`** and
`ACTION_VERSION = "1.1"`. Ids are semantic and stable across states, episodes
and instances: they are never "the index of the current legal-action list".

| Section | Ids | Count | Decodes to |
| --- | --- | --- | --- |
| `SELECT_DIE` | 0–5 | 6 | `select_die` for `(yellow, turquoise, darkblue, brown, pink, white)` |
| `WHITE_COLOR` | 6–10 | 5 | `choose_white_color` for the 5 acting colours |
| `DEST_YELLOW` | 11–28 | 18 | `pick_cell` yellow `(r,c)` + `confirm_move` |
| `DEST_TURQUOISE` | 29–59 | 31 | non-empty row subsets (column fixed by the die): `pick_cell`s + `confirm_move` |
| `DEST_BLUE` | 60–72 | 13 | `pick_cell` `blue-cell-1..13` + `confirm_move` |
| `DEST_BROWN` | 73–84 | 12 | `pick_cell` `brown-cell-1..12` + `confirm_move` |
| `DEST_PINK` | 85–96 | 12 | `pick_cell` `pink-cell-1..12` + `confirm_move` |
| `PINK_OPTION` | 97–98 | 2 | `choose_pink_option` points / bonus |
| `JOKER_VALUE` | 99–104 | 6 | `set_joker_value` 1..6 |
| `BONUS_COLOR` | 105–109 | 5 | `choose_bonus_color` (black bonus) |
| `BONUS_VALUE` | 110–115 | 6 | `choose_bonus_value` 1..6 |
| `BLUE_BONUS_PLACE` | 116–271 | 156 | `place_bonus_blue` `(cell 1..13) × (value 1..12)` |
| `TURQUOISE_BONUS` | 272–301 | 30 | immediate turquoise bonus cell (+ `confirm_move`) |
| `UTILITY` | 302–309 | 8 | `use_relance`, `start_joker`, `begin_plus1`, `skip_plus1`, `end_active_early`, `pass_passive`, `dismiss_impossible_bonus`, `continue` |
| `FILL_SLOT` | 310–315 | 6 | `fill_slot_dummy` per die colour |

Notes:

- **Turquoise die** (column = die value): the die checks rows 1..5; the agent
  chooses a non-empty subset of the free rows up to `max_pick`, and the adapter
  applies every `pick_cell` then `confirm_move`. This preserves the engine's
  "several checks" capability, which a single-cell action would lose.
- **Immediate turquoise bonus** checks *any* of the 30 turquoise cells, so it
  uses the 30-cell section (`TURQUOISE_BONUS`) instead of row subsets.
- Confirmation and cancellation commands are **not** exposed: `confirm_move` is
  orchestrated by the adapter, and pure UI cancels are avoided.

API: `build_legal_decisions(state)`, `decode(state, id)`, `encode(state, action)`,
`label(id)`, `legal_action_mask(state)`.

---

## 6. Masking

```python
mask = env.action_masks()   # np.ndarray bool, shape (N_ACTIONS,)
```

`True` = legal in the current decision, `False` = forbidden. The mask is derived
purely from the engine's `legal_actions()` (never from the opponent's strategy):
a legal-but-suboptimal move stays legal. When the environment returns a
non-terminal state where the agent must act, at least one id is `True` (this is
asserted while driving the engine).

`step(id)` on a masked or out-of-range id raises `ValueError` and does **not**
mutate the engine or consume randomness. There is no silent random fallback.

With MaskablePPO, use `ActionMasker` (see §3). The mask is also present in
`info["action_mask"]` for inspection.

---

## 7. Example sequence (white, pink, immediate bonus)

A white die → acting colour → destination is split into genuine choices:

1. agent picks `select_die:white` → engine opens a white selection;
2. `mask` now exposes `WHITE_COLOR` ids → agent picks `white:darkblue`;
3. `mask` exposes `DEST_BLUE` ids → agent picks a blue cell;
4. adapter applies `pick_cell` + `confirm_move`, the move resolves.

A pink move:

1. `select_die:pink` → the pink cell is unique, so the adapter auto-confirms;
2. `mask` exposes `PINK_OPTION` → agent picks `pink:bonus`; the engine inscribes
   `ceil(value/2)` and resolves the bonus (possibly enqueuing an immediate bonus
   die, which becomes the next agent decision).

An immediate turquoise bonus:

1. `bonus_present`/`bonus_stage=placing` in the observation;
2. `mask` exposes `TURQUOISE_BONUS` cells → agent picks one;
3. adapter applies `pick_cell` + `confirm_move`.

---

## 8. Opponent flow between two agent actions

Inside a single `step()` the environment:

1. validates the id against the mask and decodes it;
2. applies the agent's engine command(s);
3. applies every command with exactly one legal option (technical confirmations,
   forced passes, `continue`, …);
4. while the current decision belongs to the opponent, asks the fixed opponent
   policy for one action and applies it;
5. resolves bonuses and pending transitions as the engine demands;
6. returns as soon as the agent must decide again, or the game is over.

So one `step()` can encompass a full opponent turn, but it stops as soon as an
agent passive decision or an agent bonus resolution appears (a bonus requiring
the agent's choice hands control back).

---

## 9. Rewards

`rl_env/rewards.py`, configured by `reward_mode` and `reward_scale` (> 0, default
1.0):

- `score_delta` (default): `(score_after - score_before) / scale`, computed over
  the whole transition (automatic consequences and opponent actions included).
  No second terminal reward.
- `terminal_score`: `0` before the game truly ends, then `score_final / scale`.

The full score is used, foxes included; there is no artificial bonus for
bonuses, legal moves or speed.

With `gamma = 1`, the sum of the deltas from the first observation returned by
`reset()` equals `score_final - score_at_first_observation`. Automatic progress
that happens **before** that first observation (turn-1 grant, dice roll,
opponent opening moves) is outside the telescoping window; `info["scores"]` at
`reset()` is the reference. A `gamma < 1` discount is applied by the learning
algorithm outside the environment and its meaning depends on the decision
decomposition.

An external interruption (`truncated`, §11) is never treated as a win or a
naturally finished game.

---

## 10. Seeds and reproducibility

`reset(seed=...)` derives three independent streams from the seed:

- the dice RNG (`GameEngine`),
- the opponent policy RNG,
- the agent-seat draw (when `agent_player="random"`).

Two instances reset with the same seed and configuration, fed the same actions,
produce identical trajectories. When `seed=None`, an internal persistent source
draws a fresh seed (successive resets differ — never a constant). The seed used
is in `info["seed"]`.

---

## 11. `terminated` and `truncated`

- `terminated=True` **only** after the real end of the game, all mandatory
  resolutions included (turn 6 passive completed → `game-over`).
- `truncated=True` **only** for an external limit explicitly configured
  (`max_steps`, in agent decisions). The default is `None` (never truncated).
- An internal loop or engine inconsistency raises a diagnosable `RuntimeError`
  (never a fake game over). Calling `step()` after the end raises until
  `reset()` is called.

---

## 12. `info`

Every return provides: `seed`, `agent_player`, `turn`, `round`, `phase`,
`decision`, `scores` (agent/adversary), `scores_full` (absolute players 1/2),
`engine_actions` and `opponent_actions` (counts since the previous return),
`steps`, `rules_version`, `observation_version`, `action_version`,
`action_mask`. At the end: `final_scores` and `result` (`win`/`loss`/`draw`).
No growing history is copied into `info`; detailed traces are opt-in.

---

## 13. Tests, throughput, debugging

`tests/test_rl_env.py` covers observation/space conformance and stability,
action encode/decode, mask↔legality consistency (with engine replay),
all phases and overlays, agent-decision stopping, both seats, bonus chains and
passives, physical vs effective value with a joker, reproducibility and instance
independence, no mutation on invalid actions, `score_delta` telescoping,
`terminal_score`, `reward_scale`, complete games, and the
`terminated`/`truncated` distinction.

Throughput: a full random-agent game takes ~50–70 agent decisions and runs in a
few tens of milliseconds (~500–1500 agent decisions/second on a laptop). Set
`log_engine_actions=False` (the default) so the engine does not accumulate one
dict per applied action. Use `--render` / `--show-decisions` for debugging, or
`env.render()` for a one-line summary.

`gymnasium.utils.env_checker.check_env` **samples `action_space` uniformly and
ignores `action_masks()`**, so on the raw environment it feeds a masked id and
our contract raises `ValueError` (intended: illegal actions are never silently
accepted). The test suite shows how to run the checker through a *test-only*
adapter that maps invalid samples to the first legal id, keeping the real
environment strict.

---

## 14. Current limitations and encoding decisions

- **Turquoise** uses row subsets (31 ids) for the die, and a 30-cell section for
  the immediate bonus (any cell). Both preserve every engine-permitted choice.
- **Multi-check continuation**: after a first turquoise pick the engine offers
  `confirm_move`, but its reducer still accepts further `pick_cell`. The adapter
  emits those continuations to honour "take the maximum allowed checks",
  staying inside the selection's legal cells.
- **Pending bonus queue** is capped at 8 (`PENDING_BONUS_CAP`); the measured
  maximum is 2. If the cap were ever exceeded, the encoder raises instead of
  silently truncating.
- **Blue bonus placement** enumerates `(cell 1..13) × (value 1..12)` = 156 ids.
  A blue sum is at most 12, so the regulation stepped value is dropped above it
  (at `ref = 12` the right branch only accepts the wildcard `7`). Only legal pairs
  are ever unmasked.
- **`flatten` of the observation** is a flat `Dict`; two-player fields use a
  leading axis (agent first), which keeps the point of view constant when roles
  swap.
- **Single-option decisions** are auto-applied by the environment and never
  shown to the agent; this is intentional and documented (coherent behaviour
  rather than removing every single-option decision).
- The `random` opponent samples **atomic legal commands** uniformly, not
  strategies or complete moves.

No blocking inconsistency was found in the engine: all phases, overlays, bonus
chains, filled-slot completions and the two-player flow are reachable and
handled.

---

## 15. Compatibility precautions

- **Observation version** (`OBSERVATION_VERSION`) and **action version**
  (`ACTION_VERSION`) are exposed in `info` and returned by the constants. Any
  change to array shapes, index conventions, id ranges, `N_ACTIONS` or the
  reward definition must bump the corresponding version.
- **Rules changes** (`game_engine`, `RULES_VERSION`) may alter legal moves or
  bonus content. Re-run `pytest tests/test_rl_env.py` after any engine change;
  the mask↔legality test replays every decoded action against the engine and
  will fail if the catalogue no longer covers a decision.
- A change to `N_ACTIONS` invalidates trained models: retrain or remap.
- The engine's `GameEngine(log_actions=...)` flag is the minimal, documented
  switch used to disable its action journal during training.

## 16. Replay viewer (exact games from a checkpoint)

A checkpoint does not store a game, but the environment is deterministic given
the eval seed, so an episode can be regenerated **exactly**:

```bash
cd agent
python rl_env/replay.py --run runs/essai_01 --checkpoint best_model.zip \
    --seed 1000000 --agent-player 1          # or --episode N / --all-best-block
```

`rl_env/replay.py` loads the checkpoint, replays it deterministically with masks
on the logged eval seed, verifies the checkpoint metadata (`action_version`,
`observation_version`, `n_actions`), and writes:

- `<run>/replays/<id>.json` — one JSON trace: `initial_state`, then one **atomic**
  frame per engine action (`role` = `agent` / `opponent` / `auto`, `actor`,
  `decision_kind`, `action`, `state`, `scores`, `message`); agent-decision frames
  also carry `rl` (action id + label), `legal_actions` (labels) and
  `observation_summary` (readable summary of the numeric observation).
- `<run>/replays/index.json` — manifest.

The frontend fetches these through the read-only API (no ML dependency in the
API process):

| Route | Role |
| --- | --- |
| `GET /replays` | list available replays (all run manifests) |
| `GET /replays/{id}` | full trace for one replay |

Set `TRES_FUTE_RUNS_DIR` to override the scanned directory. In the web UI, the
**Replay** tab shows both boards and the shared dice, with ◀/▶ arrows (and
`←`/`→`), a slider and "décision précédente/suivante" jumps, plus the action and
observation-summary panels.

Replays are tied to the rules/observation/action versions of the code that
produced the checkpoint; regenerate them after any such change.

### Démonstration rapide

```bash
# depuis la racine du dépôt, venv partagé activé
python agent/rl_env/replay.py --seed 1000000 --agent-player 1
(cd backend && uvicorn api.app:app --reload &)
cd frontend && npm run dev      # onglet « Replay »
```
