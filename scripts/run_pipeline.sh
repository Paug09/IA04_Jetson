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
PYTHON=""

# Try to activate common virtualenv locations; fall back to system python3
if [ -f "venv/bin/activate" ]; then
  echo "Activating virtualenv venv..."
  # shellcheck disable=SC1091
  . venv/bin/activate
  PYTHON="venv/bin/python"
elif [ -f ".venv/bin/activate" ]; then
  echo "Activating virtualenv .venv..."
  # shellcheck disable=SC1091
  . .venv/bin/activate
  PYTHON=".venv/bin/python"
elif [ -f "env/bin/activate" ]; then
  echo "Activating virtualenv env..."
  # shellcheck disable=SC1091
  . env/bin/activate
  PYTHON="env/bin/python"
else
  if command -v python3 >/dev/null 2>&1; then
    echo "No local venv found — using system python3"
    PYTHON="python3"
  elif command -v python >/dev/null 2>&1; then
    echo "No local venv found — using system python"
    PYTHON="python"
  else
    echo "No python interpreter found (neither venv nor system python3). Exiting." >&2
    exit 1
  fi
fi

if [ "$SKIP_COLLECT" = false ]; then
  echo "[1/3] Collecting artwork data from Louvre API + Wikipedia ..."
  "$PYTHON" src/collect_data.py
else
  echo "[1/3] Skipping data collection (--skip-collect)"
fi

if [ "$SKIP_INDEX" = false ]; then
  echo "[2/3] Building ChromaDB index ..."
  "$PYTHON" src/build_index.py
else
  echo "[2/3] Skipping index build (--skip-index)"
fi

echo "[3/3] Starting Flask API on http://0.0.0.0:5000 ..."
"$PYTHON" src/app.py
