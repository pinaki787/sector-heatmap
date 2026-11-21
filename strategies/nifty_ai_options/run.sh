#!/usr/bin/env bash
set -euo pipefail
strategy_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$strategy_dir/.venv/bin/python" "$strategy_dir/run.py" "$@"
