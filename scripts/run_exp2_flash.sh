#!/usr/bin/env bash
# Experiment 2: Flash only (re-run with fixed adapter + correct model)
# Chess G5-G6 + Codenames G5-G6: llama3.1 vs gemini-3-flash-preview
# Timeout 60s, max-retries 1

set -euo pipefail
cd "$(dirname "$0")/.."

export CLAUDE_CODE_GIT_BASH_PATH='D:\Git\bin\bash.exe'
export PYTHONIOENCODING=utf-8

echo "============================================"
echo "  Experiment 2: Flash (gemini-3-flash-preview)"
echo "============================================"
echo ""

# ── Chess Game 5-6: llama3.1 vs Flash ────────────────────
echo "── Chess Game 5-6: llama3.1 vs Flash ──"
echo ""

for i in 5 6; do
  ii=$(printf "%02d" $i)
  echo ">>> Chess game $i (Flash)"
  python scripts/run_match.py \
    --game chess \
    --match-id "exp2_chess_llama_vs_flash_g${ii}" \
    --agents llama31_w flash_b \
    --adapters ollama gemini \
    --models llama3.1:8b gemini-3-flash-preview \
    --timeout 60 \
    --max-retries 1 \
    --skip-eval
  echo ""
done

echo "── Chess Flash complete ──"
echo ""

# ── Codenames Game 5-6: llama3.1 spy vs Flash spy ───────
echo "── Codenames Game 5-6: llama3.1 spy vs Flash spy (Haiku guessers) ──"
echo ""

for i in 5 6; do
  ii=$(printf "%02d" $i)
  echo ">>> Codenames game $i (Flash)"
  python scripts/run_match.py \
    --game codenames \
    --match-id "exp2_codenames_llama_vs_flash_g${ii}" \
    --agents llama31_spy haiku_guesser_r flash_spy haiku_guesser_b \
    --adapters ollama claude gemini claude \
    --models llama3.1:8b haiku gemini-3-flash-preview haiku \
    --timeout 60 \
    --max-retries 1 \
    --skip-eval
  echo ""
done

echo "── Codenames Flash complete ──"
echo ""
echo "============================================"
echo "  Experiment 2: Flash DONE"
echo "============================================"
