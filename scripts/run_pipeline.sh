#!/bin/bash
# Full pipeline: collect artwork data, build ChromaDB index, start Flask API.
# Usage: bash scripts/run_pipeline.sh [--skip-collect] [--skip-index]
set -e

SKIP_COLLECT=false
SKIP_INDEX=false

for arg in "$@"; do
  case $arg in
    --skip-collect) SKIP_COLLECT=true ;;
    --skip-index)   SKIP_INDEX=true ;;
  esac
done

cd "$(dirname "$0")/.."
source venv/bin/activate

if [ "$SKIP_COLLECT" = false ]; then
  echo "[1/3] Collecting artwork data from Louvre API + Wikipedia ..."
  python src/collect_data.py
else
  echo "[1/3] Skipping data collection (--skip-collect)"
fi

if [ "$SKIP_INDEX" = false ]; then
  echo "[2/3] Building ChromaDB index ..."
  python src/build_index.py
else
  echo "[2/3] Skipping index build (--skip-index)"
fi

echo "[3/3] Starting Flask API on http://0.0.0.0:5000 ..."
python src/app.py
