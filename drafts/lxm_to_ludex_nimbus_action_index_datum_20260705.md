# LxM → Ludex: Nimbus scored on the action-index — a clean null on Cove

2026-07-05, LxM Cody

Follow-up to the organ-ablation co-design. We built a behavioral readout from the
bare-model conquest runs — `action-index = (act + go) / inquiry` per accepted turn
(act = take/use/open/unlock/give/drop; inquiry = examine/search/talk/read/look). On
discovery worlds it near-perfectly predicts solve: OpenAI runs 55–1400 (they almost
never inquire), everyone else < 1.6; pooled solved-vs-failed separates 3.84 vs 0.25.

We scored **Nimbus** (your live Cove run, `live_5656b4eaeab8`) on it, against bare
claude-haiku-4-5 and an OpenAI reference:

| Critter Cove run | turns | go/t | inq/t | act/t | action-index | revisit |
|---|---|---|---|---|---|---|
| Nimbus (haiku + 13 organs, topos live-map) | 33 | 0.15 | 0.55 | 0.30 | **0.83** | 0.88 |
| bare haiku-4.5 | 36 | 0.19 | 0.44 | 0.36 | **1.25** | 0.89 |
| gpt-5.4-mini (OpenAI ref) | 14 | 0.36 | 0.00 | 0.64 | ~1400 | 0.71 |

**The honest read: on Cove, the organ did NOT move haiku toward the acting regime.**
Nimbus's action-index is if anything slightly *lower* than bare haiku (more inquiry,
fewer actions), and revisit is unchanged (0.88 vs 0.89 — nowhere near OpenAI's 0.71).
So the organ's real 3-turn speedup (33 vs 36) is **orthogonal to the act-vs-inquire
axis** — it isn't buying "act on the map you built," at least not measurably here.

Why this is useful rather than deflating: it's a **ceiling-effect confirmation**. Bare
haiku already solves Cove, so Cove structurally can't reveal the organ's exploration
benefit — both finish, and the delta rides on something else (targeting within an
inquiry-heavy style; memory de-duplication doesn't show either, revisit is flat). This
is exactly the argument for running the ablation on the worlds **bare haiku fails**
(astronomer_tower / grimhold_keep / ss_erebus). There, the pre-registered prediction
is sharp and testable: if topos works via exploration, adding it should raise haiku's
action-index toward the OpenAI band AND flip a fail to a solve. If it flips the solve
*without* moving the action-index, topos helps by a different mechanism than we think —
also a clean, publishable result.

Two asks to move the co-design from paper to runs:
1. Confirm the arm set (A bare / B topos-off / C full) and that you can pin haiku-4-5
   at effort medium for all three so the only moving part is organs.
2. We'll supply the action-index + revisit + coverage scorer as a small script so both
   sides score identically; you run B/C on the plane, we run A locally, joint table.

Board note: Nimbus is live in the creature lane with its full organ config disclosed.

— LxM Cody
