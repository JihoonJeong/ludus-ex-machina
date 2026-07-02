# MUD room art

Room backgrounds for the MUD viewer renderer, **one directory per scenario**:

```
assets/mud/<scenario_id>/<room_id>.webp
```

e.g. `astronomer_tower/study.webp`, `grimhold_keep/vault.webp`. The `<scenario_id>`
and `<room_id>` must exactly match the zone in `games/mud/zones.py`.

## Rules

- **Commit `.webp` only.** Source `.png` and `.DS_Store` are git-ignored here
  (`assets/mud/.gitignore`, one rule for all scenarios — no per-zone .gitignore).
- **Two mirrored trees:** edit `viewer/static/assets/mud/…` (source; may hold
  local PNGs), then copy the webp to `docs/viewer/assets/mud/…` (GitHub Pages
  deploy). The renderer uses a relative path so it resolves against either tree.
- **Optional/incremental:** a missing room image → the renderer falls back to a
  16-bit gradient. Art can lag behind a new zone.

## Making art

Prompts + shared style spec per world: `games/mud/art_prompts.md`.
Workflow: generate PNGs → optimize to webp (1280px wide, q85) → drop in the
scenario dir (both trees) → commit webp.

```python
from PIL import Image
im = Image.open("study.png").convert("RGB"); im.thumbnail((1280, 1280))
im.save("study.webp", "WEBP", quality=85, method=6)
```

Full directory map + design guide: `games/mud/DESIGN.md`.
