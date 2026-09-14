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

npm_cache_dir=${TMPDIR:-/tmp}/sector-heatmap-npm-cache
mkdir -p "$npm_cache_dir"
(
  cd client
  CI=true NPM_CONFIG_CACHE="$npm_cache_dir" npx --yes pnpm@10.17.1 install --frozen-lockfile
  CI=true NPM_CONFIG_CACHE="$npm_cache_dir" npx --yes pnpm@10.17.1 run build
)

if [ "${HEATMAP_SETUP_ONLY:-0}" = "1" ]; then
  echo "Environment setup and UI build completed."
  exit 0
fi

# Read only the two supported switches from the local .env file. Caller-provided
# environment variables take precedence, and a fresh installation is fail-closed.
file_fyers_live_orders=
file_kama_live_orders=
if [ -f .env ]; then
  file_fyers_live_orders=$(sed -n 's/^SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS=//p' .env | tail -n 1 | tr -d '\r')
  file_kama_live_orders=$(sed -n 's/^SECTOR_PULSE_ENABLE_KAMA_LIVE_ORDERS=//p' .env | tail -n 1 | tr -d '\r')
fi
export SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS="${SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS:-${file_fyers_live_orders:-0}}"
export SECTOR_PULSE_ENABLE_KAMA_LIVE_ORDERS="${SECTOR_PULSE_ENABLE_KAMA_LIVE_ORDERS:-${file_kama_live_orders:-0}}"
case "$SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS:$SECTOR_PULSE_ENABLE_KAMA_LIVE_ORDERS" in
  0:0|0:1|1:0|1:1) ;;
  *) echo "Live-order switches must each be 0 or 1." >&2; exit 1 ;;
esac

exec .venv/bin/python heatmap_server.py
