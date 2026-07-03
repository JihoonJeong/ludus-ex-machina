# Three Kingdoms: Red Cliffs — Solo Strategy

Winter, 208 AD. Cao Cao marches south with an overwhelming host. You lead the
Sun-Liu cause: hold the line, seal the alliance, and find the one moment when
one hundred and fifty thousand men can burn.

**Defeat Cao Cao's fleet at Red Cliffs within 20 turns.**

## How a turn works

One action per turn, as JSON: `{"type":"action","verb":...}`. The world is fully
deterministic — the same plan always plays out the same way.

## Actions

| verb | effect |
|------|--------|
| `develop` | +300 gold, +800 food |
| `conscript` | +1,500 troops (costs 500 gold + 1,000 food) |
| `train` | +15 morale (max 100) |
| `fortify` | +1 camp fortification (max 3) |
| `envoy` | +15 alliance with Sun Quan |
| `gift` | -400 gold, +25 alliance |
| `scout` | Cao's strength & formation; from turn 10, Zhuge Liang reads the wind |
| `fire_ships` | prepare fire ships (requires the alliance sealed at 60+) |
| `attack` | `{"tactic":"fire"}` or `{"tactic":"assault"}` — strike at Red Cliffs |
| `wait` | hold position |

## What you're up against

- Cao Cao's armada reaches Red Cliffs mid-campaign and keeps growing; late in
  the campaign his ships are **chained together** — a formation that burns.
- If you stall, he **assaults your camp** — repeatedly, harder each time.
  Fortification and morale blunt the damage; too few troops and you fall.
- The **southeast wind** rises for only a brief window, then dies. A fire
  attack into the north wind burns your own line. A head-on assault is 중과부적.

## Winning

Fire, at the right moment, with enough force: alliance sealed → fire ships
prepared → the wind at your back → the chained fleet alight. Grades reward a
sealed alliance and a preserved army.
