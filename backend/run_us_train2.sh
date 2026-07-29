#!/usr/bin/env bash
cd "$(dirname "$0")"
export MARKET=US
export DATABASE_URL="sqlite:///./sahm-us.db"
echo "=== US train (backtest already done) started $(date) ==="
python -m app.cli train && echo "=== TRAIN DONE $(date) ===" || { echo "=== TRAIN FAILED $(date) ==="; exit 1; }
python -m app.cli scan && echo "=== SCAN DONE $(date) ===" || { echo "=== SCAN FAILED $(date) ==="; exit 1; }
echo "=== ALL DONE $(date) ==="
