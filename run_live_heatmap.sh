#!/usr/bin/env sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ -x .venv/bin/python ]; then
  python_command=.venv/bin/python
elif command -v python3 >/dev/null 2>&1; then
  python_command=python3
elif command -v python >/dev/null 2>&1; then
  python_command=python
else
  echo "Python 3 is required." >&2
  exit 1
fi
exec "$python_command" heatmap_server.py
