#!/usr/bin/env bash
cd "$(dirname "$0")"
export MARKET=US
export DATABASE_URL="sqlite:///./sahm-us.db"
echo "=== US ingest loop started $(date) ==="
while : ; do
  python -m app.cli ingest --batch 2000 > _ingest_chunk.log 2>&1
  rem=$(grep -oE 'remaining=[0-9]+' _ingest_chunk.log | tail -1 | cut -d= -f2)
  echo "$(date +%H:%M:%S) remaining=${rem:-ERR}"
  if [ "$rem" = "0" ]; then echo "=== INGEST COMPLETE $(date) ==="; break; fi
  if [ -z "$rem" ]; then echo "=== STOPPED (error/quota) — tail: ==="; tail -5 _ingest_chunk.log; break; fi
done
