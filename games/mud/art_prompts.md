# MUD room art — generation prompts ("The Astronomer's Tower")

The MUD viewer renderer (`viewer/static/renderers/mud.js`) shows a per-room
background behind the room panel. The renderer loads optimized **webp**:

    viewer/static/assets/mud/<scenario_id>/<room_id>.webp
    docs/viewer/assets/mud/<scenario_id>/<room_id>.webp   # mirror for GitHub Pages

For `astronomer_tower` the room_ids are: **study, landing, library, alchemy,
observatory**. No image present → the renderer falls back to a 16-bit gradient,
so art is fully optional/incremental. The renderer overlays a dark gradient
(`rgba(8,9,16,.62 → .86)`) for text legibility, so images can be dark and
atmospheric.

## Shared style spec — prepend to EVERY prompt (keeps the set cohesive)

> 16-bit SNES-era pixel-art adventure-game background, painterly pixel art with
> subtle dithering; moody candlelit dark-fantasy; cohesive palette of deep
> indigo + parchment + warm gold highlights; first-person "standing in the
> doorway" view of the room; atmospheric depth; NO characters, NO text, NO UI,
> NO border; landscape ~16:10. Same art style, palette and lighting across all
> five rooms.

## Per-room prompts (append to the style spec)

- **study.png** — An astronomer's tower study at night: a cracked glass dome
  overhead leaking a shaft of moonlight, a brass orrery (clockwork planets) on a
  cluttered oak desk, a faded star-chart pinned to the stone wall, dust motes
  drifting in the moonbeam, a spiral stair descending in the corner.
- **landing.png** — A cramped circular stone landing where a spiral staircase
  turns; cold draft, three dark arched doorways leading off in different
  directions, worn stone steps, a single guttering wall torch.
- **library.png** — A cramped astronomy library: sagging wooden shelves crammed
  with ancient astronomical tomes, a large ornate celestial globe on a brass
  cradle at the centre (surface pocked with tiny craters), warm candlelight,
  scattered scrolls.
- **alchemy.png** — An alchemy laboratory: bubbling glass retorts and alembics,
  a faint sulphurous green haze, a small locked iron cabinet, a glossy black
  raven perched and watching with a beady eye, cluttered shelves of bottles.
- **observatory.png** — A grand observatory atop the tower: a huge brass
  telescope aimed at a sky of impossible swirling stars through an open roof, a
  velvet plinth at the centre holding a glowing orb of trapped starlight
  radiating soft light, a sense of awe and wonder.

---

# Grimhold Keep — room art (world #2, fantasy dungeon)

Rooms: **cell, corridor, great_hall, crypt, chapel, vault**. Same path convention:
`assets/mud/grimhold_keep/<room_id>.webp`.

## Shared style spec — prepend to EVERY Grimhold prompt

> 16-bit SNES-era pixel-art adventure-game background, painterly pixel art with
> subtle dithering; grim dark-fantasy ruined castle; cohesive palette of cold
> grey stone + torch-orange + deep shadow; first-person "standing in the doorway"
> view of the room; damp, oppressive, atmospheric depth; NO characters (unless
> noted), NO text, NO UI, NO border; landscape ~16:10. Same art style, palette
> and lighting across all six rooms.

## Per-room prompts (append to the style spec)

- **cell.png** — A damp dungeon prison cell deep underground; a broken iron door
  hanging off its hinges, mildewed stone walls with words scratched into them,
  scattered straw and rusted chains, faint torchlight from beyond the doorway.
- **corridor.png** — A long weeping-stone castle corridor; a few torches
  guttering in iron sconces throwing pools of orange light, dark passages
  branching off in several directions, puddles on worn flagstones.
- **great_hall.png** — A vast ruined great hall; fallen banners and shattered
  feasting tables, a crouching black stone gargoyle glaring from a plinth, and a
  heavy iron portcullis barring a doorway at the far end.
- **crypt.png** — A cold burial crypt; rows of mouldering stone tombs, a cracked
  sarcophagus with its lid shoved askew at the center, cobwebs and bone-dust,
  dim greenish light.
- **chapel.png** — A ruined castle chapel; a toppled altar among rubble, broken
  stained-glass letting in pale light, and an intact iron reliquary sealed with a
  glowing rune-etched lock.
- **vault.png** — A cold sealed stone vault; a single raised plinth at the center
  holding the Emberheart — a fist-sized gem pulsing with trapped fire — casting
  warm red light across the grey stone.

---

# Derelict: SS Erebus — room art (world #3, sci-fi)

Rooms: **airlock, corridor, cargo, engineering, bridge**. Path:
`assets/mud/ss_erebus/<room_id>.webp`.

## Shared style spec — prepend to EVERY Erebus prompt

> 16-bit SNES-era pixel-art adventure-game background, painterly pixel art with
> subtle dithering; derelict deep-space cargo ship interior, powered down; cohesive
> palette of cold steel-blue + emergency-red lighting + dark shadow, with a few
> amber console glows; first-person "standing in the doorway" view of the room;
> claustrophobic, eerie, weightless dust motes, atmospheric depth; NO characters,
> NO text, NO UI, NO border; landscape 16:10. Same art style, palette and lighting
> across all five rooms.

## Per-room prompts (append to the style spec)

- **airlock.png** — A cramped ship airlock lit by dim red emergency lighting; a
  heavy inner hatch leading deeper into the ship, a cracked datapad tethered to
  the wall drifting slightly, scuffed metal decking.
- **corridor.png** — A long dead spinal corridor of a spaceship; flickering
  gravity-plating floor, branching hatches fore and aft, a wall-mounted power
  console blinking sullen amber, and a large sealed forward blast door (unpowered).
- **cargo.png** — A zero-gravity cargo bay; toppled and drifting crates, a
  bolted rack of labelled pressurized canisters on the bulkhead, loose salvage
  floating in the dim light.
- **engineering.png** — A ship engineering bay dominated by a large dark cold
  reactor housing; an empty coolant intake port gaping beside it, a plasma igniter
  resting in a wall cradle, dead pipework and conduits.
- **bridge.png** — A spaceship command bridge; a helm console with a glowing
  receiver slot holding a softly-humming navigation core, black viewports full of
  dead stars, seats and dead screens, faint restored-power glow.

---

## Workflow

Cody writes prompts → JJ generates PNGs (Codex 5.5 image2) → JJ drops them in
`viewer/static/assets/mud/<scenario>/` → Cody optimizes to webp (1280px wide,
q85 — ~93% smaller) and mirrors to `docs/viewer/...`. Commit the **.webp** only;
source PNGs are git-ignored. Regenerate freely; always keep the shared style spec
for cross-room consistency.
