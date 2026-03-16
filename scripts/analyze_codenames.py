"""Analyze Codenames tournament results — Spymaster Core comparison."""

import json
import sys
from pathlib import Path
from collections import defaultdict

def analyze_tournament(tag: str, matches_dir: str = "matches"):
    results = []
    for r in range(1, 20):
        d = Path(matches_dir) / f"{tag}_r{r:02d}"
        if not (d / "result.json").exists():
            continue
        config = json.loads((d / "match_config.json").read_text())
        result = json.loads((d / "result.json").read_text())
        log = json.loads((d / "log.json").read_text())
        accepted = [e for e in log if e.get("result") == "accepted"]

        # Identify spymaster models
        agents = config.get("agents", [])
        spy_models = {}  # team -> model name
        for a in agents:
            if a.get("role") == "spymaster":
                agent_id = a["agent_id"]
                # Extract model from agent_id (e.g., "opus-spy-r" -> "opus")
                model = agent_id.split("-")[0]
                spy_models[a["team"]] = model

        winner = result.get("winner")
        winner_spy = spy_models.get(winner) if winner else None

        # Analyze clues and guesses
        clues = []  # (team, model, word, number)
        guesses = []  # (team, word, category, correct)

        for e in accepted:
            move = e.get("envelope", {}).get("move", {})
            agent_id = e.get("agent_id", "")
            post = e.get("post_move_state", {})

            if move.get("type") == "clue":
                team = post.get("active_team")
                # The clue was given by the team that was active BEFORE role switch
                # After clue, active_role becomes "guesser" but team stays same
                # Actually, the active_team in post_move_state is the team that gave the clue
                model = agent_id.split("-")[0]
                clues.append({
                    "team": team,
                    "model": model,
                    "word": move.get("word"),
                    "number": move.get("number", 0),
                    "round": r,
                })
            elif move.get("type") == "guess":
                guess_ctx = e.get("post_move_context", {})
                guess_history = guess_ctx.get("guess_history", [])
                if guess_history:
                    last_guess = guess_history[-1]
                    guesses.append({
                        "team": last_guess.get("team"),
                        "word": last_guess.get("word"),
                        "category": last_guess.get("category"),
                        "correct": last_guess.get("correct", False),
                        "round": r,
                    })

        assassin_hit = "assassin" in result.get("summary", "").lower()

        results.append({
            "round": r,
            "spy_models": spy_models,
            "winner": winner,
            "winner_spy": winner_spy,
            "summary": result.get("summary", ""),
            "remaining": result.get("analysis", {}).get("remaining", {}),
            "clues": clues,
            "guesses": guesses,
            "assassin": assassin_hit,
            "total_clues": len(clues),
            "total_guesses": len(guesses),
        })

    if not results:
        print("No completed matches found.")
        return

    # === Per-round summary ===
    print(f"{'='*70}")
    print(f"CODENAMES TOURNAMENT ANALYSIS: {tag}")
    print(f"{'='*70}")
    print()

    for r in results:
        spy_str = " | ".join(f"{t.upper()}: {m} spy" for t, m in r["spy_models"].items())
        assassin_mark = " [ASSASSIN]" if r["assassin"] else ""
        print(f"  R{r['round']:02d}: {spy_str}")
        print(f"        {r['summary']}{assassin_mark}")
        print(f"        Clues: {r['total_clues']}, Guesses: {r['total_guesses']}")
        print()

    # === Spymaster model win rates ===
    print(f"{'─'*70}")
    print("SPYMASTER MODEL WIN RATES")
    print(f"{'─'*70}")

    model_stats = defaultdict(lambda: {"wins": 0, "losses": 0, "games": 0,
                                        "wins_red": 0, "wins_blue": 0,
                                        "games_red": 0, "games_blue": 0})

    for r in results:
        for team, model in r["spy_models"].items():
            model_stats[model]["games"] += 1
            if team == "red":
                model_stats[model]["games_red"] += 1
            else:
                model_stats[model]["games_blue"] += 1

            if r["winner_spy"] == model:
                model_stats[model]["wins"] += 1
                if team == "red":
                    model_stats[model]["wins_red"] += 1
                else:
                    model_stats[model]["wins_blue"] += 1
            elif r["winner"] is not None:
                model_stats[model]["losses"] += 1

    for model, s in sorted(model_stats.items()):
        wr = s["wins"] / s["games"] if s["games"] else 0
        wr_r = s["wins_red"] / s["games_red"] if s["games_red"] else 0
        wr_b = s["wins_blue"] / s["games_blue"] if s["games_blue"] else 0
        print(f"  {model:>8}: {s['wins']}W {s['losses']}L / {s['games']}G ({wr:.0%})")
        print(f"           Red: {s['wins_red']}/{s['games_red']} ({wr_r:.0%}) | Blue: {s['wins_blue']}/{s['games_blue']} ({wr_b:.0%})")
    print()

    # === Color advantage ===
    print(f"{'─'*70}")
    print("COLOR ADVANTAGE (Red goes first with 9 words)")
    print(f"{'─'*70}")
    red_wins = sum(1 for r in results if r["winner"] == "red")
    blue_wins = sum(1 for r in results if r["winner"] == "blue")
    total = len(results)
    print(f"  Red wins: {red_wins}/{total} ({red_wins/total:.0%})")
    print(f"  Blue wins: {blue_wins}/{total} ({blue_wins/total:.0%})")
    print()

    # === Clue analysis by model ===
    print(f"{'─'*70}")
    print("CLUE ANALYSIS BY SPYMASTER MODEL")
    print(f"{'─'*70}")

    model_clues = defaultdict(list)
    for r in results:
        for c in r["clues"]:
            model_clues[c["model"]].append(c)

    for model, clue_list in sorted(model_clues.items()):
        numbers = [c["number"] for c in clue_list]
        avg_num = sum(numbers) / len(numbers) if numbers else 0
        multi = sum(1 for n in numbers if n >= 2)
        safe = sum(1 for n in numbers if n <= 1)
        print(f"  {model:>8}: {len(clue_list)} clues")
        print(f"           Avg number: {avg_num:.1f}")
        print(f"           Multi-word (≥2): {multi} ({multi/len(clue_list):.0%})")
        print(f"           Safe (≤1):       {safe} ({safe/len(clue_list):.0%})")
        # Distribution
        dist = defaultdict(int)
        for n in numbers:
            dist[n] += 1
        dist_str = " ".join(f"{k}:{v}" for k, v in sorted(dist.items()))
        print(f"           Distribution: {dist_str}")
    print()

    # === Clue success rate ===
    print(f"{'─'*70}")
    print("CLUE SUCCESS RATE (guesses correct / clue number)")
    print(f"{'─'*70}")

    # Group guesses by team and round to match with clues
    model_success = defaultdict(lambda: {"intended": 0, "correct": 0, "total_guesses": 0})

    for r in results:
        # Match clues to subsequent guesses
        current_clue = None
        correct_for_clue = 0

        for e_idx, c in enumerate(r["clues"]):
            model = c["model"]
            intended = c["number"]
            # Count correct guesses for this clue's team
            team_guesses = [g for g in r["guesses"]
                           if g["team"] == c["team"] and g["round"] == r["round"]]
            # This is approximate — we count all correct guesses for the team
            model_success[model]["intended"] += intended

        # Simpler: count all correct guesses per spy model's team
        for c in r["clues"]:
            model = c["model"]
            team = c["team"]
            team_correct = sum(1 for g in r["guesses"]
                              if g["team"] == team and g["correct"])
            team_total = sum(1 for g in r["guesses"] if g["team"] == team)

        # Actually, let's just count per-model totals
        for team, model in r["spy_models"].items():
            correct = sum(1 for g in r["guesses"]
                         if g["team"] == team and g["correct"])
            total_g = sum(1 for g in r["guesses"] if g["team"] == team)
            model_success[model]["correct"] += correct
            model_success[model]["total_guesses"] += total_g

    for model, s in sorted(model_success.items()):
        rate = s["correct"] / s["total_guesses"] if s["total_guesses"] else 0
        print(f"  {model:>8}: {s['correct']}/{s['total_guesses']} guesses correct ({rate:.0%})")
    print()

    # === Assassin incidents ===
    assassins = [r for r in results if r["assassin"]]
    if assassins:
        print(f"{'─'*70}")
        print("ASSASSIN HITS")
        print(f"{'─'*70}")
        for r in assassins:
            print(f"  R{r['round']:02d}: {r['summary']}")
        print()


if __name__ == "__main__":
    tag = sys.argv[1] if len(sys.argv) > 1 else "codenames_baseline_v1"
    analyze_codenames = analyze_tournament(tag)
