#!/usr/bin/env sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$project_dir"

if [ -x .venv/bin/python ]; then
  bootstrap_python=.venv/bin/python
elif command -v python3 >/dev/null 2>&1; then
  bootstrap_python=python3
elif command -v python >/dev/null 2>&1; then
  bootstrap_python=python
else
  echo "Python 3.9 or newer is required." >&2
  exit 1
fi

if ! "$bootstrap_python" -c 'import sys; raise SystemExit(sys.version_info < (3, 9))'; then
  echo "Python 3.9 or newer is required." >&2
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  "$bootstrap_python" -m venv .venv
fi

.venv/bin/python -m pip install --disable-pip-version-check --requirement requirements.lock

if ! command -v node >/dev/null 2>&1 || ! command -v npx >/dev/null 2>&1; then
  echo "Node.js 20.19 or newer, including npx, is required to build the UI." >&2
  exit 1
fi
if ! node -e 'const [major, minor] = process.versions.node.split(".").map(Number); process.exit(major > 20 || (major === 20 && minor >= 19) ? 0 : 1)'; then
  echo "Node.js 20.19 or newer is required to build the UI." >&2
  exit 1
fi

(
  cd client
  npx --yes pnpm@10.17.1 install --frozen-lockfile
  npx --yes pnpm@10.17.1 run build
)

if [ "${HEATMAP_SETUP_ONLY:-0}" = "1" ]; then
  echo "Environment setup and UI build completed."
  exit 0
fi

exec .venv/bin/python heatmap_server.py
