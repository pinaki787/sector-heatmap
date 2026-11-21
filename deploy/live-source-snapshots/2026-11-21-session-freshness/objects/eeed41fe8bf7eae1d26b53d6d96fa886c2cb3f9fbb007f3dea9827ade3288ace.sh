#!/usr/bin/env sh
# Deliberately expose only the KAMA confirmation-gated ticket route.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
export SECTOR_PULSE_ENABLE_FYERS_LIVE_ORDERS=0
export SECTOR_PULSE_ENABLE_KAMA_LIVE_ORDERS=1
exec sh ./run_live_heatmap.sh
