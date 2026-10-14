#!/usr/bin/env sh
# Linux / macOS launcher: creates .venv on first start, installs deps, runs the app.
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
fi
.venv/bin/python -m pip install --disable-pip-version-check -q -r requirements.txt
exec .venv/bin/python main.py
