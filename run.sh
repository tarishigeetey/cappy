#!/bin/bash
# Cappy launcher for macOS
# First run creates a virtual environment and installs PyQt6.
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Setting up Cappy (one-time)…"
  python3 -m venv .venv
  ./.venv/bin/pip install --upgrade pip -q
  ./.venv/bin/pip install -r requirements.txt -q
fi

exec ./.venv/bin/python -m cappy.app
