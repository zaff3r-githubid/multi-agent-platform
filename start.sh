#!/bin/bash
# start.sh — Starts the Multi-Agent Platform
# Prevents Mac from sleeping while platform is running

cd "$(dirname "$0")"

# Activate virtual environment FIRST
source venv/bin/activate

echo "================================================="
echo "  Multi-Agent Platform — Starting"
echo "================================================="
echo ""
echo "  Python: $(which python)"
echo "  Preventing Mac sleep with caffeinate..."
echo "  Dashboard → http://localhost:8000"
echo "  Press Control+C to stop"
echo ""

# ulimit prevents 'too many open files' error
ulimit -n 4096

# caffeinate -i prevents system sleep while python runs
caffeinate -i $(which python) main.py
