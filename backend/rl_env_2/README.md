# `rl_env_2` — simplified observations, pruned/factorised actions, sequence training

A second Gymnasium environment for Très Futé, built **on top of** `game_engine/`
and `rl_env/` (which are not modified). It keeps the same full two-player game
and opponent flow but reduces the observation and the action catalogue, exposes
`gamma`, and adds a checkpoint opponent plus a sequential training script.

```
        agent (MaskablePPO)
              │  action id (int, 0..148)
              ▼
  rl_env_2.DiceGameEnv2 ──reset/step──► game_engine.GameEngine
        │  observation 2.0 (Dict)              │ legal_actions() / game_reducer
        │  reward (SequenceReward)             │ compute_score
        │  mask (actions 2.0)                  ▼
        └──────────────◄──────── opponent: heuristic | random | checkpoint (essai_01)
```

* `OBSERVATION_VERSION_2 = "2.0"`, `ACTION_VERSION_2 = "2.0"`, `N_ACTIONS_2 = 149`.
* `DEFAULT_GAMMA = 0.999`.

---

## 1. Differences with `rl_env`

| Aspect | `rl_env` | `rl_env_2` |
| --- | --- | --- |
| Observation | 51 keys, axis 0 = agent / axis 1 = adversary | 53 keys, agent board 1-D + 5 adversary scalars |
| Adversary board | full board | `opp_score_total`, `opp_fox_count`, `opp_min_zone`, `opp_max_zone`, `opp_zones_completed` |
| Agent zones | absent | `agent_min_zone`, `agent_max_zone`, `agent_zones_completed` |
| Redundant fields | present | removed (`selection_legal/picked`, `chosen_colors/values`, `slot_colors/values`, `pending_bonus_colors/owner`) |
| Actions | 316 | 149 (blue bonus and turquoise bonus factorised; dead ids removed) |
| Gamma | not exposed (1.0 default in `rl_env`) | exposed, default **0.999** |
| Opponent | heuristic / random | heuristic / random / **checkpoint** (`rl_env` v1 policy) |
| Reward | `score_delta` / `terminal_score` | 4-term sequence (score, fox, zone, terminal) |
| Training | `train_maskable_ppo.py` | `train_sequence.py` (4 chained runs) |

---

## 2. Observation 2.0

Flat `gymnasium.spaces.Dict`, all agent-centric. `OBSERVATION_VERSION_2 = "2.0"`.

Agent board (1-D): `yellow_checks(18)`, `turquoise_checks(30)`,
`blue_values(13)` (0 = empty, ≤12), `brown_checks(12)`, `brown_last_checked(1)`,
`brown_disabled(12)`, `pink_values(12)` (≤18), `slots_unlocked(58)`,
`bonuses(6)`, `chosen_count(1)`, `slot_filled(3)`.

| Key | Shape | dtype | Meaning |
| --- | --- | --- | --- |
| `agent_min_zone` | (1,) | int32 | min of the agent's 5 colour scores |
| `agent_max_zone` | (1,) | int32 | max of the agent's 5 colour scores |
| `agent_zones_completed` | (1,) | int8 | number of colours at their max score (0..5) |
| `score_total` | (1,) | int32 | agent total score (foxes included) |
| `fox_count` | (1,) | int8 | agent foxes unlocked |
| `opp_score_total` | (1,) | int32 | adversary total score |
| `opp_fox_count` | (1,) | int8 | adversary foxes |
| `opp_min_zone` / `opp_max_zone` | (1,) | int32 | adversary weakest / strongest colour |
| `opp_zones_completed` | (1,) | int8 | adversary completed colours |
| `turn` / `round` | (1,) | int8 | global turn (1..6) / active round (0..3) |
| `phase` | (1,) | int8 | index in `PHASE_KINDS` |
| `decision` | (1,) | int8 | index in `DECISION_KINDS` |
| `actor_is_agent` / `active_is_agent` | (1,) | int8 | whose turn / who is active |
| `dice_values` | (6,) | int8 | physical values, fixed colour order |
| `dice_locations` | (6,) | int8 | 0 available, 1 chosen, 2 discarded |
| `dice_joker_values` | (6,) | int8 | joker override, 0 = none |
| `die_selected` | (6,) | int8 | which die is selected |
| `selection_present` | (1,) | int8 | a selection is open |
| `selection_color` / `selection_acting` | (1,) | int8 | physical / acting colour index |
| `selection_value` / `selection_max_pick` / `selection_elimination` | (1,) | int8 | selection helpers |
| `joker_pending` / `joker_pending_value` | (1,) | int8 | joker overlay |
| `pink_present` … `pink_owner_is_agent` | (1,) | int8 | pink points/bonus overlay |
| `bonus_present` / `bonus_stage` / `bonus_color` / `bonus_value` / `bonus_owner_is_agent` | (1,) | int8 | bonus resolution overlay |
| `pending_bonus_count` | (1,) | int8 | queued bonus dice (≤8) |
| `bonus_blue_cell` | (1,) | int8 | chosen cell during the factorised blue bonus (0 = none) |
| `bonus_turquoise_row` | (1,) | int8 | chosen row during the factorised turquoise bonus (0 = none) |

**Zone thresholds** (a zone is *completed* at its table maximum):
yellow 126, turquoise 105, blue 68, brown 90, pink 129. They are derived in
`observations.ZONE_THRESHOLDS` from the score tables (pink cell 1 is forced to
`ceil(value/2)`, max 3; cells 2..12 max `value × multiplier`).

The two `bonus_*` intermediary fields keep the factorised decisions Markovian:
the engine state does not record the chosen cell/row until the second step.

---

## 3. Action catalogue 2.0

`action_space = Discrete(149)`, `ACTION_VERSION_2 = "2.0"`. Ids are semantic and
stable; they are never "the index of the current legal list".

| Section | Ids | Count | Decodes to |
| --- | --- | --- | --- |
| `SELECT_DIE` | 0–5 | 6 | `select_die` |
| `WHITE_COLOR` | 6–10 | 5 | `choose_white_color` |
| `DEST_YELLOW` | 11–28 | 18 | `pick_cell` yellow (+ confirm); also yellow bonus placement |
| `DEST_TURQUOISE` | 29–59 | 31 | non-empty row subsets (column fixed by the die) |
| `DEST_BLUE` | 60–71 | 12 | `pick_cell` blue `1..6, 8..13` (+ confirm) |
| `DEST_BROWN` | 72–83 | 12 | `pick_cell` brown (+ confirm) |
| `PINK_OPTION` | 84–85 | 2 | `choose_pink_option` points / bonus |
| `JOKER_VALUE` | 86–91 | 6 | `set_joker_value` |
| `BONUS_COLOR` | 92–96 | 5 | `choose_bonus_color` (black bonus) |
| `BONUS_VALUE` | 97–102 | 6 | `choose_bonus_value` |
| `BLUE_BONUS_CELL` | 103–114 | 12 | step 1: chosen cell (no engine call) |
| `BLUE_BONUS_VALUE` | 115–126 | 12 | step 2: `place_bonus_blue(cell, value)` |
| `TURQUOISE_BONUS_ROW` | 127–131 | 5 | step 1: chosen row (no engine call) |
| `TURQUOISE_BONUS_COL` | 132–137 | 6 | step 2: `pick_cell` + `confirm_move` |
| `UTILITY` | 138–142 | 5 | `use_relance`, `start_joker`, `begin_plus1`, `skip_plus1`, `end_active_early` |
| `FILL_SLOT` | 143–148 | 6 | `fill_slot_dummy` |

Factorised decisions are chained by the environment: a step-1 id stores the cell
(or row) and returns immediately (reward 0); the next `action_masks()` only
contains the legal values (or columns) for that choice.

### Removed ids

`rl_env` had 316 ids; 16 were removed and the rest renumbered:

* `DEST_PINK` (12): the pink destination is always unique, so it is
  auto-confirmed and never an agent decision;
* `blue-cell-7` (1): the fixed centre is never a destination nor a bonus cell;
* `continue`, `dismiss_impossible_bonus`, `pass_passive` (3): always the sole
  legal action, hence auto-applied by the environment.

`DEST_YELLOW` is **kept**: although a normal yellow destination is unique, the
same section is reused by the yellow bonus placement (up to 3 cells).

**1000-game analysis.** A scan of `legal_actions()` over 1000 random games found
143 ids never seen in an agent mask. Most are merely **rare** (large turquoise
row subsets, joker values, many `(cell, value)` blue-bonus pairs), not dead: they
are legal in reachable states. Only the 16 above are structurally never agent
decisions, so only those were removed (no id was removed on empirical rarity
alone).

---

## 4. Gamma

`DiceGameEnv2(gamma=...)` stores `gamma` (default `0.999`) and exposes it in
`info["gamma"]`; it is **not** passed to Gymnasium. The training script reads it
to configure `MaskablePPO`.

Half-life `ln(0.5)/ln(gamma)`:

* `gamma = 0.999` → **~693 steps**, far beyond a 50–70-decision episode, so a fox
  unlocked on turn 1 and counted on turn 6 is still credited;
* `gamma = 0.99` → ~69 steps, i.e. only about one episode: too short.

---

## 5. Checkpoint opponent

`opponents/checkpoint_policy.py` loads `runs/essai_01/best_model.zip` (an
`rl_env` v1 policy: observation 1.0, action 1.1, 316 ids) and uses **Option B**:
it reconstructs the observation 1.0 *directly from the engine state*, applies the
same fixed linear scaling as training, takes the mask and decodes the action with
`rl_env`'s catalogue, then applies the resulting engine command(s). Option A (an
observation 2.0 → 1.0 adapter) is impossible because v2 dropped the adversary
board.

The checkpoint metadata is checked against the current `rl_env` constants
(`action_version`, `observation_version`, `n_actions`); a mismatch raises an
explicit `ValueError` (expected vs loaded) and a missing file raises
`FileNotFoundError`. There is **no silent fallback** to the heuristic. The policy
exposes `act(state)` (used by the env) and `choose(state, legal_actions)`.

---

## 6. Rewards (sequence)

`rewards.SequenceReward(mode)` (scale 100):

1. `score_delta_normalized`: `Δ(score)/100`
2. `fox`: + `0.5 · Δ(fox_count) · min_zone_after`
3. `zone`: + `0.2 · Δ(zones_completed)`
4. `terminal`: + `+1` win / `0` draw / `-1` loss at the end

---

## 7. Tests

```bash
cd backend
pytest tests/test_rl_env_2_obs.py tests/test_rl_env_2_actions.py tests/test_rl_env_2_opponent.py
```

Covers observation/space conformance, 100-step stability, removed keys, the
computed features (compared with a manual `rl_env` + `score` calculation), the
two factorisations, mask↔legality replay, full encode/decode round-trip over 100
games, engine non-regression vs `rl_env`, and checkpoint legality over 100 games.

---

## 8. Sequential training

```bash
python rl_env_2/train_sequence.py --timesteps 1000000
```

Four chained runs (each resumes the previous `best_model.zip` with
`reset_num_timesteps=False`), 4 parallel `DummyVecEnv`, `ActionMasker`, evaluation
on 200 fixed, disjoint seeds against the checkpoint opponent, TensorBoard logs in
`runs/sequence_<timestamp>/runN_*/`, and a final `REPORT.md`. See
`--help` for all options (`--seeds`, `--eval-seeds`, `--checkpoint`, `--resume`).
