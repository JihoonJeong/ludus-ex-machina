# robust_nav v0.2 — hidden search and cue navigation under single-change conditions

This is a Blockworld extension for 여울's connectome comparison (hub-ops/from-ludex-village/152, 155; LxM 096, 097).

- It uses the same engine, move rule and world as `hidden_target_nav_01`.
- It adds a sensor layer, a policy/evaluator split, configured conditions, seed splits and metrics.
- The earlier `lxm/envs/blockworld_env.py` (LxM 095) is unchanged and keeps its API.

| config | version | task | conditions |
|---|---|---|---|
| `task_a_v0.1` (default, `conditions_v0.json`) | v0.1.1 | A hidden search | 1–5 |
| `task_a_v0.2` (`task_a_v0_2.json`) | v0.2 | A hidden search | 1–5 unchanged + 6 (OOD structure) |
| `task_b_v0.2` (`task_b_v0_2.json`) | v0.2 | B cue navigation | 1–6 as in A + cue-only conditions |

- A v0.2 config `extends` the one before it: conditions are merged by name, so conditions 1–5 are byte-for-byte those of v0.1.
- `RobustNavEnv()` with no argument is still task A v0.1.x, and its observations, actions, layouts and noise are unchanged.
- **Task A and task B scores are never pooled.**

| file | what |
|---|---|
| `env.py` | `RobustNavEnv(config, frame=)`: `reset` / `step` / `abort` / `metrics` / `save_trajectory` / `spec` |
| `sensors.py` | frames (`world_to_body`, `body_to_world`, `side_of`, `turn`), masks, noise, the cue |
| `layouts.py` | seeded layouts (environment RNG), OOD families, BFS, `structure_stats` |
| `metrics.py` | episode metrics; `pair_recovery` and `paired_summary` |
| `baselines.py` | the rule baselines, `run_episode` (the harness), `AbortEpisode` |
| `seeds_v0.json` | seed splits: `dev` and `tune` are public; `final` is published as a sha256 only |
| `scripts/robust_nav_smoke.py` | runs baselines × conditions over a split and writes tables plus results |

## Run

```python
from lxm.envs.robust_nav import RobustNavEnv, seeds
from lxm.envs.robust_nav.baselines import run_episode, ALL_POLICIES

env = RobustNavEnv("task_b_v0.2")                      # frame="world" (default) or "body"
r = run_episode(env, ALL_POLICIES["cue_sweep"](), seeds.load("dev")[0], "ood_detour",
                save_to="traj.jsonl.gz")
```

A controller is any object with `reset(seed)` and `act(obs, info) -> action`.

```bash
.venv/bin/python scripts/robust_nav_smoke.py --split dev --out <dir>                        # task A v0.1.1
.venv/bin/python scripts/robust_nav_smoke.py --config task_a_v0.2 --split dev --out <dir>
.venv/bin/python scripts/robust_nav_smoke.py --config task_b_v0.2 --split dev --out <dir>
```

## What the policy gets — nothing else

```json
{"t": 17,
 "heading": "north",
 "last": {"action": "east", "outcome": "collided", "bump_side": "right"},
 "local": {"frame": "world", "grid_radius": 5, "occlusion": "none",
           "blocked": [[0, 0, 1, ...], ...],
           "beacon":  [[0, 0, 0, ...], ...],
           "valid":   [[1, 1, 1, ...], ...]},
 "cue": {"dir": [0.8137, 0.5812], "valid": 1}}
```

`cue` appears in task B only.

**Time.** `t` is the observation index.
- The reset observation is `t = 0`, and the observation after step k is `t = k`. `info["t"]` is the same number.
- At reset, `last` is `{"action": null, "outcome": null, "bump_side": null}` and there is no `info`.
- `bump_side` is always present: `null` unless the move collided.

**Actions** are `north | south | east | west | wait` in world compass directions.
- Anything else counts as `invalid` and is taken as a wait. That includes up/down moves, other verbs, extra keys and malformed input.
- The budget is 100 steps. The episode ends when the agent stands on the beacon cell (`end: reached`) or when the budget runs out (`end: budget`).

**`heading`** changes only on a successful move. A collided move or a wait leaves it as it was. This is the engine's `_do_move` behaviour, and a test pins it.

**`last.outcome`** is one of:

| outcome | meaning |
|---|---|
| `moved` | the agent moved |
| `collided` | a move was attempted and the world blocked it (obstacle, no ground, world edge) |
| `waited` | a wait: the policy's own, or one the harness put in after the controller failed (the evaluator record tells them apart) |
| `invalid` | the action was not allowed and was taken as a wait |

- `bump_side` gives the blocked side relative to the heading at the time of the attempt: `front | right | back | left`.
- Contact and heading are never masked or noised.

**`local`** is a fixed (2R+1)×(2R+1) grid with R = 5. Its size does not change under any condition.

| channel | meaning |
|---|---|
| `blocked` | 1 = cannot be walked into. Beyond the world edge counts as blocked. The agent's own cell is 0. |
| `beacon` | 1 = the beacon is in that cell |
| `valid` | 1 = the reading is real. **With valid = 0 the value is forced to 0, and 0 there does not mean empty.** |

- There is no line-of-sight occlusion (`occlusion: "none"`).
- A test checks that `blocked` agrees with the engine's move rule.

**`cue`** (task B) is a unit vector from the agent to the goal in a straight line.
- It ignores walls, so it is not the shortest path. It carries no distance: the length is 1.
- The only exception is the terminal observation on the goal cell, where it is `[0, 0]` with valid 1.
- It is given in the same frame as `local`: world `[ux, uy]` (east +x, south +y), or body `[fwd, right]`.
- It is an explicit engine-made cue, not a model of smell.

**Frames:**

| frame | grid rows | grid cols | cue |
|---|---|---|---|
| `world` | dy −R..+R (north first) | dx −R..+R (west first) | `[ux, uy]` |
| `body` | forward +R..−R (ahead first) | right −R..+R (left first) | `[fwd, right]` |

- `world` uses the same axes as the actions: north = dy −1, east = dx +1.
- `body` is the world grid rotated so the heading points up.
- Left and right always mean the body's left and right under the current heading.

**`info`** holds `{t, outcome, reward, done}`, plus `end` once the episode is over. `step` asserts this allowlist.

**Reward:**
- +1 for success.
- −0.01 per step.
- −0.02 more for each collision.
- There is no shaping from hidden distances.

**Kept from the policy** (evaluator record only):
- absolute position, map, map size;
- goal cell, shortest path, geodesic distance, visits and revisits;
- seed, layout, layout family, condition name, true grids before masking or noise;
- engine event texts;
- harness metadata, including infra-failure texts.

## Conditions — one change at a time

`window: [onset, release)` is given in observation indices, where reset is t = 0. `null` means the condition lasts to the end.

| 152 # | id | change | window |
|---|---|---|---|
| 1 | `nominal` | none; new layouts from the dev distribution | — |
| 2 | `short_range` | effective radius 5 → 2; the outer ring gets valid = 0 | [0, end) |
| 3 | `hemi_{left,right}_transient` | the body's left or right half-field gets valid = 0; the midline stays | [10, 40) |
| 3 | `hemi_{left,right}_sustained` | same | [10, end) |
| 4 | `blind_transient` | the whole local grid gets valid = 0; heading, contact and the cue stay | [10, 40) |
| 4 | `blind_sustained` | same | [10, end) |
| 5 | `noise` | *undetected*: inside the valid field, `blocked` flips at 0.05, a true beacon drops at 0.2, a false beacon appears at 0.002 per cell per step; valid stays 1; the agent's own cell and the cue are never noised | [0, end) |
| 6 | `ood_corridors` | the obstacles are replaced by three parallel 15-long walls one cell apart across the start–goal line, each with a 1-cell gap 3–6 off the line, on alternating sides. The agent can thread the 1-wide corridors or go round the band's open ends. | — |
| 6 | `ood_deadends` | the obstacles are replaced by a wide U between start and goal with its mouth toward the start, plus six narrow dead-end alleys | — |
| 6 | `ood_detour` | the obstacles are replaced by one 15-long barrier across the start–goal line, shifted off-centre, with no gap: the agent must go round an end | — |
| B | `cue_loss_transient` / `_sustained` | *known*: the cue gets valid 0 and `[0, 0]`; the grid is untouched | [10, 40) / [10, end) |
| B | `cue_noise` | *undetected*: the cue vector is turned by a Gaussian angle (sd 30°) drawn from its own per-step RNG; valid stays 1 | [0, end) |

**Condition 6** keeps the seed's dev layout and replaces only its obstacles. Terrain, start, heading and beacon stay the same, so condition 6 is paired with nominal on the same start and goal.
- Each OOD layout is checked: start and goal are walkable, the goal is reachable, and the shortest path is between 12 and 70. The header records `family`, `base_family` and `shortest_base`.
- No OOD structure cuts the map in two. A full barrier turns hidden search into sweeping the agent's own half first, and every baseline sits at the floor (seen in the v0.2 dev probe).
- `layouts.structure_stats` shows what changed. Means over the 12 dev seeds:

  | | nominal | corridors | deadends | detour |
  |---|---|---|---|---|
  | shortest | 19.8 | 29.3 | 24.0 | 26.2 |
  | detour ratio | 1.12 | 1.69 | 1.37 | 1.48 |
  | dead-end cells | 0.3 | 2.7 | 22.4 | 0.2 |
  | corridor cells | 2.8 | 26.9 | 22.6 | 1.1 |

**Provisional:** the noise strengths (grid and cue) and the binary `recovered` threshold. Final N and the freeze come with 여울's controller design freeze.

## RNGs — three, apart

| RNG | derived from | notes |
|---|---|---|
| layout (environment) | `(rng_namespace, family, seed)`; OOD obstacles from `(rng_namespace, "ood", family, seed)` | Conditions 1–5 share the layout of a seed. |
| sensor | grid: `(rng_namespace, seed, condition, t)`; cue: the same plus `/cue` | One stream per step, each drawing a fixed number of values. The controller's RNG use cannot move either schedule. Different paths can still see different noisy values; pairing covers the world, the rule and the schedule. |
| controller | `controller_seed(episode_seed, rep)` | It is never the episode seed itself, and it is the same across conditions. |

`rng_namespace` (`robust_nav_v0`) is not the version string. A v0.x bump that keeps the namespace keeps every layout and every noise draw.

## Seeds (`seeds_v0.json`)

- `dev` has 12 seeds and `tune` has 24. Both are public.
- `final` is a pool of 100 seeds that is **sealed**: only the sha256 of the manifest file is published. The file is revealed when 여울 freezes the controller designs. `seeds.verify_final(path)` checks it.
- None of LxM 095's public seeds 1–20 are reused.
- In every layout the beacon starts out of sight (Chebyshev distance > 5), at least 12 steps away, and reachable.
- The OOD families use the same seed ids with a different family, so the family and the seed are both recorded.

## Metrics (`metrics.py`) — every episode counts, failures included

**Outcome**
- `reached`
- `end`: reached | budget | aborted, with `abort_reason`
- `end_turn`
- `spl` (0 on failure)
- `return`

**Action outcomes**
- `rates` and `counts` of moved / collided / waited / invalid / **infra_wait**.
- `waited` counts only the policy's own waits. `infra_wait` counts waits the harness put in after a controller failure. Each evaluator row carries `cause: policy | infra`.

**Stuck in place vs loops**
- `stationary_steps` and `longest_stationary_run`
- `revisit_moves`, `backtracks` and `distinct_cells`

**Search vs approach**
- `search_steps` is the first observation index at which the *true* beacon cell shows as a valid beacon in what the policy received.
- `approach_steps` covers the steps after that.

**Windows (every episode, nominal included).** `windows[release]` covers the observation indices release < t ≤ release + 20. It holds:
- `status`: reached_before_release | ended_before_release | reached_in_window | truncated | full_window
- `new_cells` and `geo_progress` (evaluator-only geodesic)
- `reached_in_window`, `steps_in_window` and `infra_in_window`
- `beacon_seen_before_release`

**Impairment**
- `resume_steps`: from onset to the first move after it. It is None when onset is 0.
- `moved_rate_impaired`
- `recovery`: this condition's window, plus the provisional v0.1 flag `recovered`. That flag is not discriminative, since `random_walk` passes it.

**Paired recovery** — `pair_recovery(impaired, nominal)` pairs runs with the same policy, seed and rep over the same observation-time window. The main measure stays overall success and SPL.
- Window statuses on both sides.
- `new_cells` and `geo_progress`: raw values on each side plus impaired − nominal. The difference is computed only when both windows are full (`comparable`). A window that did not happen is None, never 0.
- Window-free measures:
  - `reach`: both / nominal_only / impaired_only / neither
  - `delay`: impaired − nominal `end_turn` when both reached
- `paired_summary` counts every pair by status first. It gives differences over comparable pairs only. It reports the subset that saw the beacon before release on both sides separately, and names that subset's selection.

**Harness**
- `infra_fail`: a controller exception becomes a wait with `cause: infra`. It is kept, not dropped, and the error text never reaches the policy.
- `AbortEpisode` (raised from `act`) or `env.abort(reason)` ends the episode as `end: aborted` with the reason and the steps taken.
- `act_ms_total`
- An optional `policy.sidecar()` dict can report compute, memory, tokens and calls.

**Between episodes** the harness calls only `policy.reset(seed)`. Frozen weights are the default. Online adaptation is a separate condition, declared later.

## Baselines (`baselines.py`)

All baselines read the world-frame policy observation and info only. Cells with valid = 0 are treated as unknown.

| policy | memory | rule |
|---|---|---|
| `random_walk` | none | a uniformly random move |
| `bump_turn` | none | contact only: keeps going and turns left or right at random on a collision |
| `seek_reactive` | none | heads for a seen beacon; otherwise keeps going and turns away from blocked cells |
| `seek_and_sweep` | path | integrates its own path from `outcome`, keeps a map of felt/seen blocked cells and visits, and remembers where it last saw a beacon |
| `cue_follow` (B) | none | takes the move best aligned with the cue that is not seen or just felt blocked; a seen beacon comes first; without a valid cue it behaves as `seek_reactive` |
| `cue_sweep` (B) | path | `seek_and_sweep` that breaks ties by cue alignment: least visited first, then best aligned |

## Known limits (v0.2)

- **Task B windows.** In task B the cue-guided baselines finish in a median of about 18 steps. The transient windows [10, 40), kept identical to task A, therefore touch only the tail, and window-based recovery mostly does not apply (`reached_before_release`). The window-free `delay` and `reach` cover this. B-specific windows (e.g. [3, 13)) are a decision for 여울.
- **Survivor bias.** Episodes that end before release have no window. Faster policies have fewer comparable pairs, so tables always show the denominators.
- No line-of-sight occlusion. The layer is flat; there is no up/down movement.
- The world edge looks the same as an obstacle.
- Evaluator trajectories store both the delivered and the true grids (plus the cue in task B) for every step, as gzip jsonl. The v0.3 viewer will read them.
