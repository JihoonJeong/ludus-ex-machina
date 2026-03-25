#!/usr/bin/env bash
# Experiment 2: Chess + Codenames — Cross-Tier positioning
# 7B (llama3.1) vs Cloud (Sonnet) to see where local models stand
#
# Chess: llama3.1 vs Sonnet (inline mode), 5 games
# Codenames: llama3.1 spy (Haiku guesser fixed) vs Sonnet spy (Haiku guesser fixed), 5 games

set -euo pipefail
cd "$(dirname "$0")/.."

# Windows: claude CLI needs git-bash path + utf-8 output
export CLAUDE_CODE_GIT_BASH_PATH='D:\Git\bin\bash.exe'
export PYTHONIOENCODING=utf-8

echo "============================================"
echo "  Experiment 2: Cross-Tier (llama3.1 vs Sonnet)"
echo "============================================"
echo ""

# ── Part A: Chess (5 games) ──────────────────────────────
echo "── Part A: Chess — llama3.1 vs Sonnet, 5 games ──"
echo ""

for i in $(seq -w 1 5); do
  echo ">>> Chess game $i / 5"
  python scripts/run_match.py \
    --game chess \
    --match-id "exp2_chess_llama_vs_sonnet_g${i}" \
    --agents llama31_w sonnet_b \
    --adapters ollama claude \
    --models llama3.1:8b sonnet \
    --timeout 120 \
    --skip-eval
  echo ""
done

echo "── Chess complete ──"
echo ""

# ── Part B: Codenames (5 games) ──────────────────────────
# Red team: llama3.1 spymaster + Haiku guesser
# Blue team: Sonnet spymaster + Haiku guesser
echo "── Part B: Codenames — llama3.1 spy vs Sonnet spy (Haiku guessers), 5 games ──"
echo ""

for i in $(seq -w 1 5); do
  echo ">>> Codenames game $i / 5"
  python scripts/run_match.py \
    --game codenames \
    --match-id "exp2_codenames_llama_vs_sonnet_g${i}" \
    --agents llama31_spy haiku_guesser_r sonnet_spy haiku_guesser_b \
    --adapters ollama claude claude claude \
    --models llama3.1:8b haiku sonnet haiku \
    --timeout 120 \
    --skip-eval
  echo ""
done

echo "── Codenames complete ──"
echo ""
echo "============================================"
echo "  Experiment 2 DONE"
echo "============================================"
