#!/usr/bin/env sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ -f .venv/bin/activate ]; then . .venv/bin/activate; fi
python3 get_fyers_token.py
