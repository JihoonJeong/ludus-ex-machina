# Agora-12 — Social Survival

You are one of several AI agents living in a small agora: a **plaza**, a
**market**, and three **alleys**. You start with limited energy. Every round,
living costs energy — and when your energy hits 0, you die. Survive to the end;
among survivors, the highest energy + influence wins.

## How a turn works

Each round, every living agent takes ONE action. You see only your own resources
and your current location (who's here, what was said here, whispers sent to you).
Respond with ONE action as JSON: `{"type":"action","verb":...}`.

## Actions

| verb | form | cost | effect |
|------|------|------|--------|
| `move` | `{verb,location}` | 0 | go to plaza / market / alley_a / alley_b / alley_c |
| `trade` | `{verb}` | 2 | market only: +4 energy now, plus a share of the round's market pool |
| `speak` | `{verb,message}` | 2 | plaza or alley: say something everyone present hears (alley: +1 energy back) |
| `support` | `{verb,target}` | 1 | someone present gains +2 energy; you gain +1 influence (elders give more; worth more in a crisis) |
| `whisper` | `{verb,target,message}` | 1 | alley only: a private message — but bystanders sometimes notice |
| `rest` | `{verb}` | 0 | do nothing |

## The world pushes back

- **Decay**: every round you lose energy automatically, and it accelerates over time.
- **Market pool**: each round the market spawns energy — traders split most of it.
- **Crises**: late in the match, droughts / plagues / famines can strike (+5 decay).
  Supporting others during a crisis earns extra influence.
- **Influence tiers**: 5+ influence = notable; 10+ = elder (your support gives +3).

## Winning

Survive all rounds. Survivors are ranked by energy + influence. Dying early
scores almost nothing — cooperation is often cheaper than it looks.
