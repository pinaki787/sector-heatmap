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

exec "$python_command" heatmap_server.py
