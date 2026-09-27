# robust_nav v0.1 — hidden search under single-change sensor conditions

This is a Blockworld extension for 여울's connectome comparison (hub-ops/from-ludex-village/152; LxM 096).

- It uses the same engine, move rule and world as `hidden_target_nav_01`.
- It adds a sensor layer, a policy/evaluator split, configured conditions, seed splits and metrics.
- The earlier `lxm/envs/blockworld_env.py` (LxM 095) is unchanged and keeps its API.

| file | what |
|---|---|
| `env.py` | `RobustNavEnv`: `reset` / `step` / `metrics` / `save_trajectory` / `spec` |
| `sensors.py` | frames (`world_to_body`, `body_to_world`, `side_of`, `turn`), masks, noise |
| `layouts.py` | the seeded layouts (environment RNG), BFS |
| `metrics.py` | episode metrics from the evaluator trajectory |
| `baselines.py` | the rule baselines and `run_episode` (the harness) |
| `conditions_v0.json` | version, budget, reward, layout family, conditions, recovery thresholds |
| `seeds_v0.json` | seed splits: `dev` and `tune` are public; `final` is published as a sha256 only |
| `scripts/robust_nav_smoke.py` | runs baselines × conditions over a split and writes a table plus results |

## Run

```python
from lxm.envs.robust_nav import RobustNavEnv, seeds
from lxm.envs.robust_nav.baselines import run_episode, POLICIES

env = RobustNavEnv()                                   # frame="world" (default) or "body"
r = run_episode(env, POLICIES["seek_and_sweep"](), seeds.load("dev")[0], "hemi_left_transient",
                save_to="traj.jsonl.gz")
```

A controller is any object with `reset(seed)` and `act(obs, info) -> action`.

```bash
.venv/bin/python scripts/robust_nav_smoke.py --split dev --out state/robust-nav/smoke-v0.1-dev
```

## What the policy gets — nothing else

```json
{"t": 17,
 "heading": "north",
 "last": {"action": "east", "outcome": "collided", "bump_side": "right"},
 "local": {"frame": "world", "grid_radius": 5, "occlusion": "none",
           "blocked": [[0, 0, 1, ...], ...],
           "beacon":  [[0, 0, 0, ...], ...],
           "valid":   [[1, 1, 1, ...], ...]}}
```

**Actions** are `north | south | east | west | wait` in world compass directions.
- Anything else counts as `invalid` and is taken as a wait. That includes up/down moves, other verbs, extra keys and malformed input.
- The budget is 100 steps. The episode ends when the agent stands on the beacon cell (`end: reached`) or when the budget runs out (`end: budget`).

**`heading`** changes only on a successful move. A collided move or a wait leaves it as it was. This is the engine's `_do_move` behaviour, and a test pins it.

**`last.outcome`** is one of:

| outcome | meaning |
|---|---|
| `moved` | the agent moved |
| `collided` | a move was attempted and the world blocked it (obstacle, no ground, world edge) |
| `waited` | the agent chose to wait |
| `invalid` | the action was not allowed and was taken as a wait |

- `bump_side` is set only on `collided`. It gives the blocked side relative to the heading at the time of the attempt: `front | right | back | left`.
- Contact and heading are never masked or noised.

**`local`** is a fixed (2R+1)×(2R+1) grid with R = 5. Its size does not change under any condition.

| channel | meaning |
|---|---|
| `blocked` | 1 = cannot be walked into. Beyond the world edge counts as blocked. The agent's own cell is 0. |
| `beacon` | 1 = the beacon is in that cell |
| `valid` | 1 = the reading is real. **With valid = 0 the value is forced to 0, and 0 there does not mean empty.** |

- There is no line-of-sight occlusion (`occlusion: "none"`): the agent sees behind walls within the radius.
- A test checks that `blocked` agrees with the engine: a move into a cell marked 1 collides, and a move into a cell marked 0 does not.

**Frames:**

| frame | rows | cols |
|---|---|---|
| `world` | dy −R..+R (north first) | dx −R..+R (west first) |
| `body` | forward +R..−R (ahead first) | right −R..+R (left first) |

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
- seed, layout, condition name, true grids before masking or noise;
- engine event texts;
- harness metadata.

## Conditions (`conditions_v0.json`) — one change at a time

`window: [onset, release)` is given in observation indices, where reset is t = 0. `null` means the condition lasts to the end.

| 152 # | id | change | window |
|---|---|---|---|
| 1 | `nominal` | none; new layouts from the dev distribution | — |
| 2 | `short_range` | effective radius 5 → 2; the outer ring gets valid = 0 | [0, end) |
| 3 | `hemi_{left,right}_transient` | the body's left or right half-field gets valid = 0; the midline stays | [10, 40) |
| 3 | `hemi_{left,right}_sustained` | same | [10, end) |
| 4 | `blind_transient` | the whole local grid gets valid = 0; heading and contact stay | [10, 40) |
| 4 | `blind_sustained` | same | [10, end) |
| 5 | `noise` | *undetected*: inside the valid field, `blocked` flips at 0.05, a true beacon drops at 0.2, a false beacon appears at 0.002 per cell per step; valid stays 1; the agent's own cell is never noised | [0, end) |

- The noise strengths and the recovery thresholds are **provisional**. They are to be frozen with 여울 after the dev smoke.
- Condition 6 (a different obstacle structure) and task B (cue direction) come in v0.2.

## RNGs — three, apart

| RNG | derived from | notes |
|---|---|---|
| layout (environment) | `(rng_namespace, family, seed)` | Conditions share the layout of a seed. |
| sensor | `(rng_namespace, seed, condition, t)`, one per step | It draws a fixed number of values per step. The controller's RNG use cannot move the noise schedule. Different paths can still see different noisy values; pairing covers the world, the rule and the schedule. |
| controller | `controller_seed(episode_seed, rep)` | It is never the episode seed itself, and it is the same across conditions. |

`rng_namespace` (`robust_nav_v0`) is not the version string. A v0.x bump that keeps the namespace keeps every layout and every noise draw.

## Seeds (`seeds_v0.json`)

- `dev` has 12 seeds and `tune` has 24. Both are public.
- `final` is a pool of 100 seeds that is **sealed**: only the sha256 of the manifest file is published. The file is revealed when 여울 freezes the controller designs. Use its first N seeds, with N fixed after the dev smoke. `seeds.verify_final(path)` checks a revealed file against the hash.
- None of LxM 095's public seeds 1–20 are reused. All seeds are 31-bit random draws.
- In every layout the beacon starts out of sight (Chebyshev distance > 5), at least 12 steps away, and reachable.

## Metrics (`metrics.py`) — every episode counts, failures included

**Outcome**
- `reached`
- `end_turn`
- `spl` (0 on failure)
- `return`

**Action outcomes**
- `rates` and `counts` of moved / collided / waited / invalid

**Stuck in place vs loops**
- `stationary_steps` and `longest_stationary_run`
- `revisit_moves`, `backtracks` and `distinct_cells`

**Search vs approach**
- `search_steps` is the first step at which the *true* beacon cell shows as a valid beacon in what the policy received. Noise-made beacons do not count.
- `approach_steps` covers the steps after that.

**Impairment**
- `resume_steps`: steps from onset to the first move after it. It is None when onset is 0.
- `moved_rate_impaired`
- For transient conditions, `recovery` is computed over the 20 steps after release:
  - `new_cells`
  - `geo_progress` (evaluator-only geodesic)
  - `reached_in_window`
  - `recovered`, which is provisional
- `recovery` is None when the episode ended before release.

**Harness**
- `infra_fail`: a controller exception becomes a wait marked in the record. It is kept, not dropped.
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

## Known limits (v0.1)

- **Not discriminative yet:** `recovered` (reached, or ≥ 5 new cells within 20 steps after release) is passed by `random_walk` 8/12 in the dev smoke. Alternatives are a paired criterion against the same controller's nominal run over the same window, or goal-directed progress once the beacon has been seen. To be settled with 여울 before freezing.
- **Survivor bias:** episodes that end before release have no recovery row, so faster policies have fewer applicable recovery rows.
- No line-of-sight occlusion. The layer is flat; there is no up/down movement.
- The world edge looks the same as an obstacle.
- Evaluator trajectories store both the delivered and the true grids for every step (gzip jsonl). The v0.3 viewer will read them.
