#!/bin/bash
# Cappy launcher for macOS
# First run creates a virtual environment and installs PyQt6.
set -e
cd "$(dirname "$0")"

# Make sure we don't keep old copies of the app alive from earlier launches,
# otherwise the new behavior won't appear.
pkill -f "python -m cappy.app" 2>/dev/null || true
pkill -f "cappy.app" 2>/dev/null || true

if [ ! -d ".venv" ]; then
  echo "Setting up Cappy (one-time)…"
  python3 -m venv .venv
  ./.venv/bin/pip install --upgrade pip -q
  ./.venv/bin/pip install -r requirements.txt -q
fi

# Start the app detached from the terminal so it keeps running even after the
# shell exits or the terminal window is closed.
nohup ./.venv/bin/python -m cappy.app >/dev/null 2>&1 &

echo "Cappy started in the background."
disown 2>/dev/null || true
