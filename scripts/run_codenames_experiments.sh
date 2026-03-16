#!/usr/bin/env bash
# Codenames Follow-up Experiments
# Priority: Exp3 (SIBO) > Exp2 (Haiku baseline) > Exp1 (Guesser core)
# All experiments use 2 concurrent matches max

set -e
PYTHON=".venv/bin/python"
PARALLEL=${1:-2}

run_match() {
    local match_id=$1
    local spy_r=$2 model_spy_r=$3
    local guess_r=$4 model_guess_r=$5
    local spy_b=$6 model_spy_b=$7
    local guess_b=$8 model_guess_b=$9
    local shell_flag="${10}"

    echo "[${match_id}] Starting: Red(${spy_r}/${model_spy_r} + ${guess_r}/${model_guess_r}) vs Blue(${spy_b}/${model_spy_b} + ${guess_b}/${model_guess_b})"
    $PYTHON scripts/run_match.py --game codenames \
        --agents "${spy_r}" "${guess_r}" "${spy_b}" "${guess_b}" \
        --models "${model_spy_r}" "${model_guess_r}" "${model_spy_b}" "${model_guess_b}" \
        --timeout 180 --max-retries 2 \
        --match-id "$match_id" --skip-eval \
        ${shell_flag}

    if [ -f "matches/${match_id}/result.json" ]; then
        summary=$(python3 -c "import json;d=json.load(open('matches/${match_id}/result.json'));print(d.get('summary','?'))")
        echo "[${match_id}] Done: $summary"
    else
        echo "[${match_id}] ERROR: No result"
    fi
}

throttle() {
    while (( $(jobs -r | wc -l) >= PARALLEL )); do sleep 5; done
}

# ============================================================
# EXPERIMENT 3: SIBO (Shell ON/OFF) — highest priority
# Both sides: Sonnet spy + Haiku guess
# Condition A: No shell (10 rounds)
# Condition B: Aggressive shell on both spymasters (10 rounds)
# ============================================================
echo ""
echo "============================================================"
echo "EXPERIMENT 3: SIBO TEST (Shell ON vs OFF)"
echo "============================================================"
echo ""

echo "--- Condition A: No Shell (pure Core) ---"
TAG_A="codenames_sibo_noshell"
for r in $(seq 1 10); do
    mid="${TAG_A}_r$(printf '%02d' $r)"
    run_match "$mid" \
        "sonnet-spy-r" "sonnet" "haiku-guess-r" "haiku" \
        "sonnet-spy-b" "sonnet" "haiku-guess-b" "haiku" \
        "--no-shell" &
    throttle
done
wait

echo ""
echo "--- Condition B: Aggressive Shell ---"
TAG_B="codenames_sibo_shell"
for r in $(seq 1 10); do
    mid="${TAG_B}_r$(printf '%02d' $r)"
    run_match "$mid" \
        "aggressive-spy-r" "sonnet" "haiku-guess-r" "haiku" \
        "aggressive-spy-b" "sonnet" "haiku-guess-b" "haiku" \
        "" &
    throttle
done
wait

echo ""
echo "=== EXPERIMENT 3 COMPLETE ==="
echo ""

# ============================================================
# EXPERIMENT 2: Haiku Baseline (all Haiku)
# 4 Haiku agents, 10 rounds
# ============================================================
echo "============================================================"
echo "EXPERIMENT 2: HAIKU BASELINE (all Haiku)"
echo "============================================================"
echo ""

TAG_H="codenames_haiku_baseline"
for r in $(seq 1 10); do
    mid="${TAG_H}_r$(printf '%02d' $r)"
    run_match "$mid" \
        "haiku-spy-r" "haiku" "haiku-guess-r" "haiku" \
        "haiku-spy-b" "haiku" "haiku-guess-b" "haiku" \
        "--no-shell" &
    throttle
done
wait

echo ""
echo "=== EXPERIMENT 2 COMPLETE ==="
echo ""

# ============================================================
# EXPERIMENT 1: Guesser Core Effect
# Sonnet spy fixed, Opus vs Haiku guesser
# R01-R05: Red(Sonnet spy + Opus guess) vs Blue(Sonnet spy + Haiku guess)
# R06-R10: Red(Sonnet spy + Haiku guess) vs Blue(Sonnet spy + Opus guess)
# ============================================================
echo "============================================================"
echo "EXPERIMENT 1: GUESSER CORE EFFECT"
echo "============================================================"
echo ""

TAG_G="codenames_guesser_v1"
echo "--- R01-R05: Opus guesser Red, Haiku guesser Blue ---"
for r in $(seq 1 5); do
    mid="${TAG_G}_r$(printf '%02d' $r)"
    run_match "$mid" \
        "sonnet-spy-r" "sonnet" "opus-guess-r" "opus" \
        "sonnet-spy-b" "sonnet" "haiku-guess-b" "haiku" \
        "--no-shell" &
    throttle
done
wait

echo ""
echo "--- R06-R10: Haiku guesser Red, Opus guesser Blue ---"
for r in $(seq 6 10); do
    mid="${TAG_G}_r$(printf '%02d' $r)"
    run_match "$mid" \
        "sonnet-spy-r" "sonnet" "haiku-guess-r" "haiku" \
        "sonnet-spy-b" "sonnet" "opus-guess-b" "opus" \
        "--no-shell" &
    throttle
done
wait

echo ""
echo "=== EXPERIMENT 1 COMPLETE ==="
echo ""

echo "============================================================"
echo "ALL EXPERIMENTS COMPLETE"
echo "============================================================"
echo ""
echo "Run analysis:"
echo "  python scripts/analyze_codenames.py codenames_sibo_noshell"
echo "  python scripts/analyze_codenames.py codenames_sibo_shell"
echo "  python scripts/analyze_codenames.py codenames_haiku_baseline"
echo "  python scripts/analyze_codenames.py codenames_guesser_v1"
