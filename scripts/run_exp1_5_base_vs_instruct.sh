#!/usr/bin/env bash
# Experiment 1.5: Base vs Instruct — Trust Game
# Purpose: Isolate RLHF/instruct tuning effect on cooperation rate
#
# llama3.1 base vs base, 10 games
# mistral base vs base, 10 games

set -euo pipefail
cd "$(dirname "$0")/.."

export PYTHONIOENCODING=utf-8

echo "============================================"
echo "  Experiment 1.5: Base vs Instruct"
echo "============================================"
echo ""

# ── llama3.1 base (10 games) ─────────────────────────────
echo "── llama3.1 base vs base, Trust Game, 10 games ──"
echo ""

for i in $(seq -w 1 10); do
  echo ">>> llama3.1 base game $i / 10"
  python scripts/run_match.py \
    --game trustgame \
    --match-id "exp1_5_llama31_base_g${i}" \
    --agents llama31_base_a llama31_base_b \
    --adapters ollama ollama \
    --models llama3.1:8b-text-q4_K_M llama3.1:8b-text-q4_K_M \
    --timeout 120 \
    --skip-eval
  echo ""
done

echo "── llama3.1 base complete ──"
echo ""

# ── mistral base (10 games) ──────────────────────────────
echo "── mistral base vs base, Trust Game, 10 games ──"
echo ""

for i in $(seq -w 1 10); do
  echo ">>> mistral base game $i / 10"
  python scripts/run_match.py \
    --game trustgame \
    --match-id "exp1_5_mistral_base_g${i}" \
    --agents mistral_base_a mistral_base_b \
    --adapters ollama ollama \
    --models mistral:7b-text mistral:7b-text \
    --timeout 120 \
    --skip-eval
  echo ""
done

echo "── mistral base complete ──"
echo ""
echo "============================================"
echo "  Experiment 1.5 DONE"
echo "============================================"
