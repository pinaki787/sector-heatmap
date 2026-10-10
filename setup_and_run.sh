#!/usr/bin/env sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$project_dir"

# Keep downloaded tools project-local; do not replace system Python or Node.
tools_dir="$project_dir/.private/setup-tools"
mkdir -p "$tools_dir/bin"
PATH="$tools_dir/bin:$tools_dir/node/bin:${HOME}/.local/bin:$PATH"
export PATH

fetch() {
  if command -v curl >/dev/null 2>&1; then
    curl --fail --location --silent --show-error --retry 3 "$1" -o "$2"
  elif command -v wget >/dev/null 2>&1; then
    wget -q "$1" -O "$2"
  else
    echo "Install curl or wget to download setup tools." >&2
    exit 1
  fi
}

# The locked NumPy/pandas/aiohttp versions are validated with Python 3.12.
# Copied virtual environments and Python 3.14 are not suitable for these pins.
if ! .venv/bin/python -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 12) or sys.prefix == sys.base_prefix)' >/dev/null 2>&1; then
  bootstrap_python=
  for candidate in python3.12 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 &&
       "$candidate" -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 12))' >/dev/null 2>&1; then
      bootstrap_python=$candidate
      break
    fi
  done
  if [ -z "$bootstrap_python" ]; then
    if ! command -v uv >/dev/null 2>&1; then
      fetch https://astral.sh/uv/install.sh "$tools_dir/install-uv.sh"
      UV_INSTALL_DIR="$tools_dir/bin" UV_NO_MODIFY_PATH=1 sh "$tools_dir/install-uv.sh"
    fi
    uv python install 3.12
    bootstrap_python=$(uv python find 3.12)
  fi
  if [ -e .venv ] || [ -L .venv ]; then
    backup_dir=$(mktemp -d "$project_dir/.private/venv-backup.XXXXXX")
    mv .venv "$backup_dir/venv"
    echo "Preserved the previous virtual environment in $backup_dir/venv"
  fi
  "$bootstrap_python" -m venv .venv
fi
if ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
  .venv/bin/python -m ensurepip --upgrade
fi
.venv/bin/python --version
.venv/bin/python -m pip install --disable-pip-version-check --requirement requirements.lock
.venv/bin/python -m pip check

node_ready() {
  command -v node >/dev/null 2>&1 && command -v npx >/dev/null 2>&1 &&
    node -e 'const [major, minor] = process.versions.node.split(".").map(Number); process.exit((major === 20 && minor >= 19) || (major === 22 && minor >= 12) || major >= 24 ? 0 : 1)' >/dev/null 2>&1
}
if ! node_ready; then
  node_version=22.23.3
  case "$(uname -s)" in
    Linux) node_os=linux ;;
    Darwin) node_os=darwin ;;
    *) echo "Automatic Node.js setup supports Linux and macOS." >&2; exit 1 ;;
  esac
  case "$(uname -m)" in
    aarch64|arm64) node_arch=arm64 ;;
    x86_64|amd64) node_arch=x64 ;;
    *) echo "Unsupported Node.js architecture: $(uname -m)" >&2; exit 1 ;;
  esac
  node_archive="node-v$node_version-$node_os-$node_arch.tar.gz"
  node_url="https://nodejs.org/dist/v$node_version"
  download_dir=$(mktemp -d "$tools_dir/node-download.XXXXXX")
  trap 'rm -rf "$download_dir"' 0
  trap 'exit 1' 1 2 15
  echo "Installing project-local Node.js $node_version ($node_os/$node_arch)..."
  fetch "$node_url/$node_archive" "$download_dir/$node_archive"
  fetch "$node_url/SHASUMS256.txt" "$download_dir/SHASUMS256.txt"
  .venv/bin/python - "$download_dir" "$node_archive" <<'PYTHON'
import hashlib
import pathlib
import sys
folder, name = pathlib.Path(sys.argv[1]), sys.argv[2]
expected = next((line.split()[0] for line in (folder / 'SHASUMS256.txt').read_text().splitlines()
                 if line.split()[-1] == name), None)
with (folder / name).open('rb') as stream:
    actual = hashlib.file_digest(stream, 'sha256').hexdigest()
if expected is None or actual != expected:
    raise SystemExit('Node.js archive checksum verification failed')
PYTHON
  tar -xzf "$download_dir/$node_archive" -C "$download_dir"
  if [ -e "$tools_dir/node" ]; then
    previous_node=$(mktemp -d "$tools_dir/node-backup.XXXXXX")
    mv "$tools_dir/node" "$previous_node/node"
  fi
  mv "$download_dir/node-v$node_version-$node_os-$node_arch" "$tools_dir/node"
  rm -rf "$download_dir"
  trap - 0 1 2 15
  if ! node_ready; then
    echo "Downloaded Node.js cannot run on this OS; check platform runtime compatibility." >&2
    exit 1
  fi
fi
node --version

npm_cache_dir=${TMPDIR:-/tmp}/sector-heatmap-npm-cache
mkdir -p "$npm_cache_dir"
(
  cd client
  CI=true NPM_CONFIG_CACHE="$npm_cache_dir" npx --yes pnpm@10.17.1 install --frozen-lockfile
  CI=true NPM_CONFIG_CACHE="$npm_cache_dir" npx --yes pnpm@10.17.1 run build
)

if [ "$(uname -s)" = "Darwin" ] && command -v swiftc >/dev/null 2>&1; then
  sh scripts/whatsapp/build.sh
else
  echo "WhatsApp native polling is available only on macOS with Swift installed."
fi
.venv/bin/python scripts/check_setup.py
if [ "${HEATMAP_INSTALL_RESEARCH:-0}" = "1" ]; then
  .venv/bin/python -m pip install --requirement requirements-research.txt
fi

# Public HTTPS hosting is explicit; normal local setup keeps its existing behavior.
if [ "${HEATMAP_SERVER_SETUP:-0}" = "1" ]; then
  if [ -z "${HEATMAP_DOMAIN:-}" ]; then
    echo "Set HEATMAP_DOMAIN to the public DNS hostname for server setup." >&2
    exit 1
  fi
  set -- --domain "$HEATMAP_DOMAIN" --user "$(id -un)"
  if [ -n "${HEATMAP_CERT_EMAIL:-}" ]; then
    set -- "$@" --email "$HEATMAP_CERT_EMAIL"
  fi
  if [ "${HEATMAP_TEST_RENEWAL:-0}" = "1" ]; then
    set -- "$@" --test-renewal
  fi
  sudo -- "$project_dir/.venv/bin/python" "$project_dir/scripts/configure_server.py" "$@"
  exit 0
fi

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
file_parser_live_orders=
if [ -f .env ]; then
  file_parser_live_orders=$(sed -n 's/^SECTOR_PULSE_ENABLE_TRADE_PARSER_LIVE_ORDERS=//p' .env | tail -n 1 | tr -d '\r')
fi
export SECTOR_PULSE_ENABLE_TRADE_PARSER_LIVE_ORDERS="${SECTOR_PULSE_ENABLE_TRADE_PARSER_LIVE_ORDERS:-${file_parser_live_orders:-0}}"
case "$SECTOR_PULSE_ENABLE_TRADE_PARSER_LIVE_ORDERS" in
  0|1) ;;
  *) echo "Live-order switches must each be 0 or 1." >&2; exit 1 ;;
esac

exec .venv/bin/python heatmap_server.py
