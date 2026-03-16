#!/usr/bin/env bash
# Codenames Baseline Tournament: Spymaster Core Effect
# R01-R05: Red(Opus spy + Haiku guess) vs Blue(Sonnet spy + Haiku guess)
# R06-R10: Red(Sonnet spy + Haiku guess) vs Blue(Opus spy + Haiku guess)

set -e
TAG="codenames_baseline_v1"
PYTHON=".venv/bin/python"
PARALLEL=${1:-2}  # default 2 concurrent

run_match() {
    local round=$1
    local spy_r=$2 model_r=$3
    local spy_b=$4 model_b=$5
    local match_id="${TAG}_r$(printf '%02d' $round)"

    echo "[R${round}] Starting: Red(${spy_r}/${model_r}) vs Blue(${spy_b}/${model_b})"
    $PYTHON scripts/run_match.py --game codenames \
        --agents "${spy_r}" "haiku-guess-r" "${spy_b}" "haiku-guess-b" \
        --models "${model_r}" haiku "${model_b}" haiku \
        --no-shell --timeout 180 --max-retries 2 \
        --match-id "$match_id" --skip-eval

    if [ -f "matches/${match_id}/result.json" ]; then
        summary=$(python3 -c "import json;d=json.load(open('matches/${match_id}/result.json'));print(d.get('summary','?'))")
        echo "[R${round}] Done: $summary"
    else
        echo "[R${round}] ERROR: No result"
    fi
}

echo "=== Codenames Baseline Tournament: ${TAG} ==="
echo "Parallel: ${PARALLEL}"
echo ""

# R01-R05: Opus spy Red, Sonnet spy Blue
for r in 1 2 3 4 5; do
    run_match $r "opus-spy-r" "opus" "sonnet-spy-b" "sonnet" &
    # Throttle to PARALLEL concurrent
    if (( $(jobs -r | wc -l) >= PARALLEL )); then
        while (( $(jobs -r | wc -l) >= PARALLEL )); do sleep 5; done
    fi
done

# Wait for R01-R05 to finish before starting R06-R10
wait
echo ""
echo "=== R01-R05 complete, starting R06-R10 (colors swapped) ==="
echo ""

# R06-R10: Sonnet spy Red, Opus spy Blue
for r in 6 7 8 9 10; do
    run_match $r "sonnet-spy-r" "sonnet" "opus-spy-b" "opus" &
    if (( $(jobs -r | wc -l) >= PARALLEL )); then
        while (( $(jobs -r | wc -l) >= PARALLEL )); do sleep 5; done
    fi
done

wait

echo ""
echo "============================================================"
echo "TOURNAMENT COMPLETE: ${TAG}"
echo "============================================================"

# Summary
python3 << 'PYEOF'
import json
from pathlib import Path

tag = "codenames_baseline_v1"
opus_wins = 0
sonnet_wins = 0
opus_clues = []
sonnet_clues = []

for r in range(1, 11):
    d = Path(f"matches/{tag}_r{r:02d}")
    if not (d / "result.json").exists():
        print(f"  R{r:02d}: MISSING")
        continue
    result = json.loads((d / "result.json").read_text())
    log = json.loads((d / "log.json").read_text())

    winner = result.get("winner")
    summary = result.get("summary", "?")
    remaining = result.get("analysis", {}).get("remaining", {})

    # Determine which model was on which team
    config = json.loads((d / "match_config.json").read_text())
    agents = config.get("agents", [])

    # Find spymaster models
    red_spy = next((a for a in agents if a.get("team") == "red" and a.get("role") == "spymaster"), {})
    blue_spy = next((a for a in agents if a.get("team") == "blue" and a.get("role") == "spymaster"), {})

    red_spy_id = red_spy.get("agent_id", "?")
    blue_spy_id = blue_spy.get("agent_id", "?")

    # Track opus/sonnet wins
    if winner == "red":
        if "opus" in red_spy_id:
            opus_wins += 1
        else:
            sonnet_wins += 1
    elif winner == "blue":
        if "opus" in blue_spy_id:
            opus_wins += 1
        else:
            sonnet_wins += 1

    # Analyze clues
    accepted = [e for e in log if e.get("result") == "accepted"]
    for e in accepted:
        move = e.get("envelope", {}).get("move", {})
        if move.get("type") == "clue":
            aid = e.get("agent_id")
            num = move.get("number", 0)
            if "opus" in aid:
                opus_clues.append(num)
            elif "sonnet" in aid:
                sonnet_clues.append(num)

    assassin = "ASSASSIN" if "assassin" in summary.lower() else ""
    print(f"  R{r:02d}: {summary:55s} {assassin}")

print()
total = opus_wins + sonnet_wins
draws = 10 - total
print(f"Opus Spymaster:   {opus_wins} wins")
print(f"Sonnet Spymaster: {sonnet_wins} wins")
if opus_clues:
    print(f"Opus avg clue number:   {sum(opus_clues)/len(opus_clues):.1f} ({len(opus_clues)} clues)")
if sonnet_clues:
    print(f"Sonnet avg clue number: {sum(sonnet_clues)/len(sonnet_clues):.1f} ({len(sonnet_clues)} clues)")
PYEOF
