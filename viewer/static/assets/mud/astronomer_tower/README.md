# MUD room backgrounds — astronomer_tower

The renderer loads **`<room_id>.webp`** (study / landing / library / alchemy /
observatory). It overlays a dark gradient for text legibility and falls back to a
16-bit gradient when an image is absent (art is optional/incremental).

**Workflow:** drop source PNGs here (any size) → optimize to webp (1280px wide, q85):

```python
from PIL import Image
im = Image.open("study.png").convert("RGB")
im.thumbnail((1280, 1280))
im.save("study.webp", "WEBP", quality=85, method=6)
```

Commit the **.webp** only — source PNGs are git-ignored (~2.5MB each; webp is ~93%
smaller, ~150–230KB). Mirror the webp to `docs/viewer/assets/mud/astronomer_tower/`
for GitHub Pages. Prompts + shared style spec: `games/mud/art_prompts.md`.
