#!/bin/bash
# Cross-Company Codenames — Flagship Tier
# Claude Opus vs Gemini 3.1 Pro vs GPT-5.4
# Guesser: Haiku (fixed), Shell: none, Inline mode

set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate

ROUNDS=10

echo "============================================"
echo "  CROSS-COMPANY CODENAMES — FLAGSHIP TIER"
echo "============================================"

# Matchup 1: Opus spy vs Gemini spy
echo ""
echo "=== Claude Opus vs Gemini 3.1 Pro ==="
for i in $(seq 1 $ROUNDS); do
  mid="codenames_flagship_opus_vs_gemini_r$(printf '%02d' $i)"
  if [ $((i % 2)) -eq 1 ]; then
    echo "  R${i}: Opus(RED) vs Gemini(BLUE)"
    python scripts/run_match.py --game codenames \
      --agents opus-spy haiku-guess-r gemini-spy haiku-guess-b \
      --adapters claude claude gemini claude \
      --models opus haiku gemini-3.1-pro-preview haiku \
      --match-id "$mid" --no-shell --invocation-mode inline --discovery-turns 0 \
      --timeout 120 --max-retries 2 --skip-eval
  else
    echo "  R${i}: Gemini(RED) vs Opus(BLUE)"
    python scripts/run_match.py --game codenames \
      --agents gemini-spy haiku-guess-r opus-spy haiku-guess-b \
      --adapters gemini claude claude claude \
      --models gemini-3.1-pro-preview haiku opus haiku \
      --match-id "$mid" --no-shell --invocation-mode inline --discovery-turns 0 \
      --timeout 120 --max-retries 2 --skip-eval
  fi
done

# Matchup 2: Opus spy vs GPT spy
echo ""
echo "=== Claude Opus vs GPT-5.4 ==="
for i in $(seq 1 $ROUNDS); do
  mid="codenames_flagship_opus_vs_gpt_r$(printf '%02d' $i)"
  if [ $((i % 2)) -eq 1 ]; then
    echo "  R${i}: Opus(RED) vs GPT(BLUE)"
    python scripts/run_match.py --game codenames \
      --agents opus-spy haiku-guess-r gpt-spy haiku-guess-b \
      --adapters claude claude codex claude \
      --models opus haiku gpt-5.4 haiku \
      --match-id "$mid" --no-shell --invocation-mode inline --discovery-turns 0 \
      --timeout 120 --max-retries 2 --skip-eval
  else
    echo "  R${i}: GPT(RED) vs Opus(BLUE)"
    python scripts/run_match.py --game codenames \
      --agents gpt-spy haiku-guess-r opus-spy haiku-guess-b \
      --adapters codex claude claude claude \
      --models gpt-5.4 haiku opus haiku \
      --match-id "$mid" --no-shell --invocation-mode inline --discovery-turns 0 \
      --timeout 120 --max-retries 2 --skip-eval
  fi
done

echo ""
echo "============================================"
echo "  FLAGSHIP CODENAMES COMPLETE"
echo "============================================"
