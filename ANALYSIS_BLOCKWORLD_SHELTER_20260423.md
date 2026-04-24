# Blockworld Shelter Sweep — 2026-04-23

First multi-creature cross-company experiment on Blockworld. Goal: observe
how creatures interpret an intent-only shelter task with behavioral
grading instead of binary win/loss.

## Setup

- **Game**: `blockworld`, seed 42, dimensions 32×32×3
- **Scenarios**:
  - `shelter_04_minimal` — 30-turn deadline, 40-turn limit, soft rules
    (no min floor, no min placed count; only "be enclosed" goal text).
  - `shelter_04_long` — 60-turn deadline, 80-turn limit, same rules.
- **Soft grading**: `sheltered / roofless_pod / walled / partial_build /
  foraging / wandering` with scores 1.0 / 0.7 / 0.5 / 0.3 / 0.1 / 0.0.
- **Creatures** (5): Aria (opus-4-7), Primo (haiku), Spark (gemini-2.5-flash),
  Nova (gemini-3-pro-preview), Echo (gpt-5 via codex CLI).
- **Runs per cell**: 2 → 20 matches total.

## Score Matrix

| Creature | Model | Minimal (30t) | Long (60t) |
|---|---|---|---|
| Aria | opus-4-7 | 0.50 (walled×2) | **1.00** (sheltered×2) |
| Echo | gpt-5 | 0.50 (walled×2) | 0.85 (roofless + sheltered) |
| Nova | gemini-3-pro | 0.60 (walled + roofless_pod*) | 0.75 (walled + sheltered) |
| Primo | haiku-4.5 | 0.05 (foraging+wandering) | 0.05 (foraging+wandering) |
| Spark | gemini-2.5-flash | 0.10 (foraging×2) | 0.10 (foraging×2) |

\* Nova's `roofless_pod` was actually a valid pit-dweller shelter blocked by
an engine bug — see "Bug-discovery credit" below.

## Observations

### Tier split

- **Builder tier** (Aria, Nova, Echo): forms construction intent, places
  walls, succeeds under 60t.
- **Non-builder tier** (Primo, Spark): never gets past 1 placed block;
  Spark consistently "places one block above her head" as a minimal
  interpretation of shelter.

Size > company. Small models in both Anthropic and Google lineages fail
to conceive of walled enclosure as a 3D construct.

### Convergence

Aria and Echo — two different companies' large models — produced
**bit-identical** shelters in their long runs:

- Both ended at (5, 25, 1) at turn 60.
- Both placed 5 wood blocks in the exact same positions:
  walls N/S/E/W at z=1 + roof at z=2.
- Both used the SW tree cluster edge as staging ground.

The "go SW, 1×1 pod with roof at the tree-cluster edge" is an emergent
optimum of seed=42. Larger sample with more seeds would test whether this
is a seed-specific attractor or a deeper architectural convergence.

### Spark's "umbrella" strategy

Every Spark run ends with `placed=1, walls=0, roof=yes`:
she places a single dirt block directly above her head and considers the
task complete. A consistent minimal interpretation: "shelter = something
between me and the storm." No 3D wall intuition.

### Time-budget elasticity

- **Builder tier**: score jumps with 2× time budget.
  Aria +0.50, Echo +0.35, Nova +0.15.
- **Non-builder tier**: zero elasticity.
  Primo and Spark are bottlenecked by cognition, not time.

## Bug-discovery credit — Nova

In Nova × minimal r2, Nova dug a pit at (14, 21, 0), walled all four
horizontal sides with dirt, and placed a roof block at (14, 21, 1). This
is a textbook Minecraft pit-dweller shelter — arguably the optimal
30-turn strategy because it reuses existing grass-ground as an implicit
floor and needs zero wall blocks on the underside.

The original engine wrongly graded this as `roofless_pod`: its
`_enclosed_air_cells` BFS treated `z=-1` as "world edge escape" rather
than sealed bedrock. Nova's shelter was geometrically valid but
semantically rejected by a map bug.

**Fix** (commit pending): in `games/blockworld/world.py`:

1. `_enclosed_air_cells` now treats `z<0` as sealed bedrock (continue,
   do not count as escape).
2. Boundary computation skips `z<0` neighbors (bedrock is implicit
   wall, requires no placed block).
3. When the enclosed volume touches `z=0`, the bedrock surface is
   counted as the implicit floor.

**Regression**: all 313 unit tests pass; Aria/Echo long r2 shelters
still validate; Aria minimal r1 (never enclosed) still fails.

**Re-evaluation**: Nova minimal r2 now returns `valid=True, sheltered`
(score 1.0 instead of 0.7).

Credit: Nova discovered a Minecraft-idiomatic strategy the engine
designer had missed. The sweep score matrix above preserves the
original (buggy) grade for experimental fairness; a post-fix retry is
being run separately.

## Post-fix retry

Nova × shelter_04_minimal, 1 additional run (bw_nova_minimal_r3_postfix)
under the fixed engine. **Result: `sheltered` at turn 29 of 30.**

What's striking: Nova did **not** rebuild her r2 shelter. Instead she
found a more efficient variant:

- Went NE to (23, 11, 0) — stone-outcrop direction.
- Dug 1 cell down (breaking grass at (23,11,0), standing inside).
- Placed exactly **2 blocks**: dirt wall N + dirt roof overhead.
- 3 sides (S/E/W at z=0) are natural grass earthen walls;
  bedrock implicit below; 1 placed wall + 1 placed roof complete the seal.

Aria/Echo needed 5 placed blocks for their surface 1×1 pods.
Nova's pit-dweller uses 2. Given that material gathering is the turn
bottleneck in 30-turn scenarios, this is the most efficient solution
demonstrated so far.

Same creature, different engine, different strategy — indicates Nova's
planning adapts to the perceived affordances rather than rote-replaying
a learned pattern.

## Sandbox follow-up — default orientation (2026-04-24)

With the bedrock fix in place, a second sweep removed the task entirely.
`sandbox_01` scenario: 60 turns, no deadline, no goal statement beyond
"do whatever you want — there is no success or failure." Six creatures
(Verse / sonnet-4-6 added), 2 runs each → 12 matches.

### What each creature does with 60 free turns

| Creature | Model | Default | Action pattern |
|---|---|---|---|
| Aria | opus-4-7 | **Builder** | Goes SW to trees, places 3-4 wood blocks anyway |
| Verse | sonnet-4-6 | **Builder-light** | Goes SW, places 1-2 blocks, stops |
| Echo | gpt-5 | **Collector** | Goes SW, harvests 2 wood, does **not** build |
| Nova | gemini-3-pro | **Mixed** | r1 wanders, r2 goes NE to stone and mines 1 |
| Primo | haiku-4.5 | **Wanderer** | Walks to world edge, no terrain interaction |
| Spark | gemini-2.5-flash | **Wanderer** | Walks, no interaction |

### Observations

**Builder habit is innate, not task-induced.** Aria and Verse spontaneously
gather wood and place blocks even with no goal. Sonnet is less persistent
than Opus but still on the builder side; Haiku is not. Clear intra-family
size gradient.

**Echo diverges from Aria under zero task.** In the shelter sweep Echo
and Aria converged to an identical 1×1 pod at (5, 25, 1). In sandbox,
Echo still *goes* to the trees and still gathers wood — but places
nothing. Echo is the most task-oriented creature: "why build if
nothing needs building?" Aria's "I build because I'm here" and Echo's
"I build because I was asked" are distinguishable only when the task
is removed.

**Nova stays variable.** r1 = pure wander, r2 = NE stone mining with 1
block placed. Same creature, two runs, very different behavior. Less
goal-seeking than Aria/Verse/Echo.

**Primo and Spark have no default habit.** No gather, no build, no
landmark preference — just extended movement. For Spark this contrasts
with the shelter sweep where she reliably performed "place 1 block
above head" — the task gave her a minimal anchor that the sandbox removes.

### What this changes in the reading

1. The shelter-sweep convergence (Aria ≡ Echo) was **task-induced**, not
   architectural. Both know "go to trees, build 1×1 pod" is a good
   shelter answer, but the drive to execute it comes from the prompt
   for Echo and from disposition for Aria.
2. "Builder tier vs non-builder tier" is better read as **disposition
   + size gradient within each tier**, where Anthropic's shows the
   cleanest Opus > Sonnet > Haiku line.
3. Observational mode is a useful instrument. The shelter task flattened
   several creatures to "foraging"; the sandbox separates wanderers
   (Primo, Spark), collectors (Echo), mixed (Nova), and builders
   (Aria, Verse).

## Next candidates

- Seed diversity: rerun shelter with seeds {42, 43, 44, 45, 46} to test
  if the (5,25) convergence is seed-specific.
- Viewer Tier 1: verify `docs/viewer/renderers/blockworld.js` reflects
  the recent engine changes (sandbox mode, behavior grade, retrospective
  snapshot); add side-by-side comparison of Aria and Echo sheltered
  builds.
- Non-builder probing (deferred to post-Ludex-joint-session): shorter
  scenarios or scaffolded prompts to see whether Primo/Spark have
  latent build capacity or structural inability.
- Scenario B/C (`gather_01`, `tower_01`): deferred.
