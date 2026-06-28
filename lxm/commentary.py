"""LLM match commentary — spectator broadcast narration over a match.

Generates "sportscaster"-style commentary from the **full god's-eye match log**
(the mirror layer): the commentator sees hidden info players cannot — secret
orders, private press, hidden roles/cards — and reveals the real story.

INVARIANT — spectator-only: commentary is produced from the log and written to a
separate channel (commentary.json / viewer). It MUST NEVER be fed back into any
player's prompt; doing so would leak hidden information (= cheating). This module
only READS match data and WRITES the commentary file — it never touches the
turn/prompt pipeline.

Per-beat & incremental, so the same core serves post-hoc (replay a finished log)
and, later, live (call per beat as the match advances). Bilingual ({en, ko}).
0/1/N commentator brains → N tracks (viewer shows them as sub-tabs).
"""

from __future__ import annotations

import json
import os
import re
import tempfile

from lxm.adapters.registry import get_adapter_class, get_game_class


# ── beat builders (god's-eye digest per game) ───────────────────────────────

def _name_fn(players):
    return lambda a: players.get(a, {}).get("name", a)


def _diplomacy_beats(log: list) -> list[dict]:
    """One beat per game-year, at its order resolution. Reveals secret press +
    orders + dislodgements + standings — everything, including what players hid."""
    beats, seen = [], set()
    for e in log:
        pms = e.get("post_move_state")
        if not pms:
            continue
        lr = pms.get("last_resolution")
        if not lr or lr.get("year") in seen:
            continue
        y = lr["year"]
        seen.add(y)
        nm = _name_fn(pms.get("players", {}))
        lines = [f"YEAR {y}"]
        press = [m for m in pms.get("press_messages", []) if m.get("year") == y]
        if press:
            lines.append("Private cables (you see ALL; players only see their own):")
            for m in press:
                to = "everyone" if m["to"] == "all" else nm(m["to"])
                lines.append(f"  {nm(m['from'])} → {to}: {m['text'][:200]}")
        orders, out = lr.get("orders", {}), lr.get("outcomes", {})
        mv = [f"{p}→{o['dest']} [{out.get(p, '?')}]" for p, o in orders.items() if o.get("type") == "move"]
        if mv:
            lines.append("Orders resolved: " + ", ".join(mv))
        dis = lr.get("dislodged", {})
        if dis:
            lines.append("Dislodged: " + ", ".join(f"{nm(o)} from {p}" for p, o in dis.items()))
        sc: dict = {}
        for prov, o in pms.get("sc_owner", {}).items():
            if o:
                sc[nm(o)] = sc.get(nm(o), 0) + 1
        lines.append("Supply centers now: " + ", ".join(f"{k} {v}" for k, v in sorted(sc.items(), key=lambda x: -x[1])))
        beats.append({"turn": e.get("turn", 0), "label": f"Year {y}", "digest": "\n".join(lines)})
    return beats


def _generic_beats(log: list) -> list[dict]:
    """Fallback for games without a dedicated digest: chunk accepted moves."""
    acc = [e for e in log if e.get("envelope")]
    if not acc:
        return []
    step = max(1, len(acc) // 12)
    beats = []
    for i in range(0, len(acc), step):
        chunk = acc[i:i + step]
        lines = [f"Moves {i + 1}–{i + len(chunk)} (full state):"]
        for e in chunk:
            mv = (e.get("envelope") or {}).get("move", {})
            lines.append(f"  {e.get('agent_id')}: {json.dumps(mv, ensure_ascii=False)[:140]}")
        beats.append({"turn": chunk[-1].get("turn", 0), "label": f"Turn {chunk[-1].get('turn', 0)}", "digest": "\n".join(lines)})
    return beats


def build_beats(game_name: str, log: list) -> list[dict]:
    return _diplomacy_beats(log) if game_name == "diplomacy" else _generic_beats(log)


# ── generation ──────────────────────────────────────────────────────────────

_SYS = (
    "You are a sharp, neutral broadcast commentator for the strategy game '{game}'. "
    "You have a GOD'S-EYE view — you see hidden information the players cannot (secret "
    "orders, private messages, hidden roles or cards). Use it to reveal the REAL story: "
    "who is secretly allying, who is bluffing, who is about to be betrayed, why a move "
    "matters. Be punchy and dramatic like a live broadcast, 2–4 sentences. Explain the "
    "WHY and the tension — do not merely restate the moves.\n\nGAME RULES:\n{rules}\n"
)
_BEAT = (
    "{prior}CURRENT BEAT — {label} (the complete god's-eye picture):\n{digest}\n\n"
    "Commentate THIS beat in BOTH English and Korean. Output ONLY a single-line JSON "
    'object, nothing else: {{"en":"...","ko":"..."}}'
)
_INTRO = (
    "OPENING BROADCAST — introduce this match for spectators who may not know the game. "
    "In 1–2 punchy sentences: name the game, the sides in play, the win condition, and the "
    "single most interesting thing to watch for. Do NOT narrate moves (the game hasn't started "
    "yet). Keep it short — viewers who know the game shouldn't be bored.\n"
    "Setup: {digest}\n\n"
    'Output ONLY a single-line JSON object: {{"en":"...","ko":"..."}}'
)


def _parse_bilingual(stdout: str) -> dict:
    s = (stdout or "").strip()
    for m in re.finditer(r'\{[^{}]*"en"[^{}]*\}', s, re.S):
        try:
            o = json.loads(m.group(0))
            if "en" in o:
                return {"en": str(o.get("en", "")).strip(), "ko": str(o.get("ko", "")).strip()}
        except json.JSONDecodeError:
            continue
    return {"en": s[:600], "ko": ""}  # tolerant fallback


def generate_track(adapter, scratch_dir: str, game_name: str, rules: str, beats: list[dict]) -> list[dict]:
    sys = _SYS.format(game=game_name, rules=(rules or "")[:2000])
    out, prior = [], ""
    for b in beats:
        if b.get("intro"):
            prompt = sys + "\n" + _INTRO.format(digest=b["digest"])
        else:
            prompt = sys + "\n" + _BEAT.format(prior=prior, label=b["label"], digest=b["digest"])
        try:
            res = adapter.invoke(scratch_dir, prompt)
            text = res.get("stdout", "") if isinstance(res, dict) else ""
        except Exception:
            text = ""
        beat = _parse_bilingual(text)
        beat.update({"turn": b["turn"], "label": b["label"]})
        out.append(beat)
        prior = "STORY SO FAR:\n" + "\n".join(f"- {o['label']}: {o['en']}" for o in out[-4:]) + "\n\n"
    return out


def _translate_rules(adapter, scratch_dir: str, rules_en: str) -> str:
    """One-shot Korean translation of the rules text (for the bilingual Rules tab)."""
    if not rules_en:
        return ""
    prompt = ("Translate the following game rules into natural, readable Korean. Preserve the "
              "structure (headings, lists) and all meaning. Output ONLY the Korean translation, "
              "with no preamble or notes.\n\n" + rules_en)
    try:
        res = adapter.invoke(scratch_dir, prompt)
        return (res.get("stdout", "") if isinstance(res, dict) else "").strip()
    except Exception:
        return ""


def commentate(match_dir: str, commentators: list[tuple[str, str]]) -> dict:
    """Generate commentary for a match.

    commentators: list of (adapter_name, model). Each → one track. Empty → no tracks.
    Returns the commentary dict (also the shape written to commentary.json).
    """
    config = json.loads(open(os.path.join(match_dir, "match_config.json")).read())
    log = json.loads(open(os.path.join(match_dir, "log.json")).read())
    game_name = config.get("game", {}).get("name", "unknown")
    try:
        rules = get_game_class(game_name)().get_rules()
    except Exception:
        rules = ""
    beats = build_beats(game_name, log)
    # opening intro beat (turn 0) — short scene-set for spectators new to the game
    roster = ", ".join(a.get("display_name", a.get("agent_id", "")) for a in config.get("agents", []))
    beats = [{"turn": 0, "label": "Intro", "intro": True, "digest": f"Game: {game_name}. Sides: {roster}."}] + beats

    scratch = tempfile.mkdtemp(prefix="commentary_")
    # instantiate commentator adapters once
    objs = []
    for i, (adapter_name, model) in enumerate(commentators):
        adapter = get_adapter_class(adapter_name)({"agent_id": f"commentator_{i}", "model": model})
        ctx = getattr(adapter, "set_context", None)
        if callable(ctx):
            try:
                ctx(f"commentator_{i}")
            except Exception:
                pass
        objs.append((adapter_name, model, adapter))

    # bilingual rules for the 규칙 tab — translate once, reusing the first brain
    rules_ko = _translate_rules(objs[0][2], scratch, rules) if (rules and objs) else ""

    tracks = []
    for adapter_name, model, adapter in objs:
        tracks.append({
            "id": f"{adapter_name}:{model}",
            "label": f"{adapter_name}/{model}",
            "brain": {"adapter": adapter_name, "model": model},
            "beats": generate_track(adapter, scratch, game_name, rules, beats),
        })
    return {"game": game_name, "match_id": config.get("match_id", os.path.basename(match_dir.rstrip("/"))),
            "rules": {"en": rules, "ko": rules_ko}, "commentators": tracks}
