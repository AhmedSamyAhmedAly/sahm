#!/usr/bin/env bash
cd "$(dirname "$0")"
export MARKET=US
export DATABASE_URL="sqlite:///./sahm-us.db"
echo "=== US retrain started $(date) ==="
python -m app.cli retrain && echo "=== RETRAIN DONE $(date) ===" || { echo "=== RETRAIN FAILED $(date) ==="; exit 1; }
python -m app.cli scan && echo "=== SCAN DONE $(date) ===" || { echo "=== SCAN FAILED $(date) ==="; exit 1; }
echo "=== ALL DONE $(date) ==="
