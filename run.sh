#!/usr/bin/env bash
# Arranque rápido en Linux / macOS
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
source .venv/bin/activate
pip install -q -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
