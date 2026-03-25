#!/usr/bin/env bash
# Experiment 2 (continued): Chess + Codenames — Cross-Tier
# Games 3-4: llama3.1 vs Haiku
# Games 5-6: llama3.1 vs Flash (Gemini CLI)
# Timeout 180s, max-retries 1 (= 2 attempts total)

set -euo pipefail
cd "$(dirname "$0")/.."

export CLAUDE_CODE_GIT_BASH_PATH='D:\Git\bin\bash.exe'
export PYTHONIOENCODING=utf-8

echo "============================================"
echo "  Experiment 2 (continued): Haiku + Flash"
echo "============================================"
echo ""

# ── Chess Game 3-4: llama3.1 vs Haiku ────────────────────
echo "── Chess Game 3-4: llama3.1 vs Haiku ──"
echo ""

for i in 3 4; do
  ii=$(printf "%02d" $i)
  echo ">>> Chess game $i / 6"
  python scripts/run_match.py \
    --game chess \
    --match-id "exp2_chess_llama_vs_haiku_g${ii}" \
    --agents llama31_w haiku_b \
    --adapters ollama claude \
    --models llama3.1:8b haiku \
    --timeout 180 \
    --max-retries 1 \
    --skip-eval
  echo ""
done

echo "── Chess Haiku complete ──"
echo ""

# ── Chess Game 5-6: llama3.1 vs Flash ────────────────────
echo "── Chess Game 5-6: llama3.1 vs Flash (Gemini) ──"
echo ""

for i in 5 6; do
  ii=$(printf "%02d" $i)
  echo ">>> Chess game $i / 6"
  python scripts/run_match.py \
    --game chess \
    --match-id "exp2_chess_llama_vs_flash_g${ii}" \
    --agents llama31_w flash_b \
    --adapters ollama gemini \
    --models llama3.1:8b gemini-2.0-flash \
    --timeout 180 \
    --max-retries 1 \
    --skip-eval
  echo ""
done

echo "── Chess Flash complete ──"
echo ""

# ── Codenames Game 3-4: llama3.1 spy vs Haiku spy ────────
echo "── Codenames Game 3-4: llama3.1 spy vs Haiku spy (Haiku guessers) ──"
echo ""

for i in 3 4; do
  ii=$(printf "%02d" $i)
  echo ">>> Codenames game $i / 6"
  python scripts/run_match.py \
    --game codenames \
    --match-id "exp2_codenames_llama_vs_haiku_g${ii}" \
    --agents llama31_spy haiku_guesser_r haiku_spy haiku_guesser_b \
    --adapters ollama claude claude claude \
    --models llama3.1:8b haiku haiku haiku \
    --timeout 180 \
    --max-retries 1 \
    --skip-eval
  echo ""
done

echo "── Codenames Haiku complete ──"
echo ""

# ── Codenames Game 5-6: llama3.1 spy vs Flash spy ────────
echo "── Codenames Game 5-6: llama3.1 spy vs Flash spy (Haiku guessers) ──"
echo ""

for i in 5 6; do
  ii=$(printf "%02d" $i)
  echo ">>> Codenames game $i / 6"
  python scripts/run_match.py \
    --game codenames \
    --match-id "exp2_codenames_llama_vs_flash_g${ii}" \
    --agents llama31_spy haiku_guesser_r flash_spy haiku_guesser_b \
    --adapters ollama claude gemini claude \
    --models llama3.1:8b haiku gemini-2.0-flash haiku \
    --timeout 180 \
    --max-retries 1 \
    --skip-eval
  echo ""
done

echo "── Codenames Flash complete ──"
echo ""
echo "============================================"
echo "  Experiment 2 (continued) DONE"
echo "============================================"
