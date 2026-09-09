#!/usr/bin/env python3
"""Read-only FYERS ranking for a supplied Chartink cash-equity shortlist."""
from __future__ import annotations

from datetime import datetime
import json
import sys
import time

from fyers_apiv3 import fyersModel

from analyze_mahabank import adx, ema, history, rsi
from sector_heatmap.config import load_config
from sector_heatmap.market_calendar import IST


TICKERS = (
    "MAHABANK RBLBANK SOLARINDS SBICARD KEI GMRAIRPORT SONACOMS INDUSINDBK "
    "PHOENIXLTD RVNL LICI GODREJPROP NBCC DELHIVERY LICHSGFIN POLYCAB "
    "BAJAJHLDNG UNITDSPR BEL"
).split()
if len(sys.argv) > 1:
    TICKERS = sys.argv[1:]


def summary(rows):
    closes = [row[4] for row in rows]
    last = rows[-1]
    prior = rows[-21:-1]
    average_volume = sum(row[5] for row in prior) / len(prior)
    return {
        "close": last[4], "ema21": ema(closes[-80:], 21), "ema50": ema(closes[-100:], 50),
        "rsi": rsi(closes[-100:]), "adx": adx(rows[-100:]),
        "volume_ratio": last[5] / average_volume if average_volume else 0,
        "prior_high": max(row[2] for row in prior), "prior_low": min(row[3] for row in prior),
    }


def score(daily, hourly, quote):
    points, notes = 0, []
    if daily["close"] > daily["ema21"] > daily["ema50"]:
        points += 25; notes.append("daily EMA trend")
    if hourly["close"] > hourly["ema21"] > hourly["ema50"]:
        points += 20; notes.append("hourly aligned")
    if 52 <= daily["rsi"] <= 68:
        points += 10; notes.append("daily RSI usable")
    elif daily["rsi"] > 72:
        points -= 8; notes.append("daily extended")
    if 50 <= hourly["rsi"] <= 68:
        points += 10; notes.append("hourly RSI usable")
    elif hourly["rsi"] > 72:
        points -= 8; notes.append("hourly extended")
    if daily["adx"] >= 20:
        points += 10; notes.append("daily ADX")
    if hourly["adx"] >= 20:
        points += 10; notes.append("hourly ADX")
    if daily["volume_ratio"] >= 1.2:
        points += 10; notes.append("daily volume")
    change = float(quote.get("chp") or 0)
    if change > 4:
        points -= 12; notes.append("intraday extension")
    bid, ask = quote.get("bid"), quote.get("ask")
    if bid and ask and ask >= bid and (ask - bid) / ask <= 0.002:
        points += 5; notes.append("tight spread")
    return points, notes


def main():
    token = load_config().get("FYERS_ACCESS_TOKEN", "")
    if ":" not in token:
        raise RuntimeError("No reusable FYERS token is configured.")
    app_id, access_token = token.split(":", 1)
    client = fyersModel.FyersModel(client_id=app_id, token=access_token)
    symbols = [f"NSE:{ticker}-EQ" for ticker in TICKERS]
    quote_response = client.quotes({"symbols": ",".join(symbols)})
    if quote_response.get("s") != "ok":
        raise RuntimeError(quote_response.get("message") or "FYERS quotes unavailable")
    quotes = {item.get("n"): item.get("v", {}) for item in quote_response.get("d", [])}
    rankings, errors = [], {}
    for symbol in symbols:
        try:
            hourly = summary(history(client, "60", 90)) if symbol == "NSE:MAHABANK-EQ" else None
            # history() has a module-level symbol for the single-stock helper, so use a client wrapper here.
            def pull(resolution, days):
                from datetime import timedelta
                today = datetime.now(IST).date()
                response = client.history({"symbol": symbol, "resolution": resolution, "date_format": "1", "range_from": (today - timedelta(days=days)).isoformat(), "range_to": today.isoformat(), "cont_flag": "1"})
                if response.get("s") != "ok" or not response.get("candles"):
                    raise RuntimeError(response.get("message") or "no candles")
                rows = response["candles"]
                if resolution == "60":
                    now = datetime.now(IST)
                    rows = [
                        row for row in rows
                        if datetime.fromtimestamp(row[0], IST) + timedelta(minutes=60) <= now
                    ]
                else:
                    rows = rows[:-1]
                return rows
            hourly = summary(pull("60", 90))
            daily = summary(pull("D", 180))
            ticker = symbol.split(":", 1)[1].removesuffix("-EQ")
            quote = quotes.get(symbol, {})
            points, notes = score(daily, hourly, quote)
            rankings.append({"ticker": ticker, "score": points, "ltp": quote.get("lp"), "change_pct": quote.get("chp"), "daily": {key: round(value, 2) for key, value in daily.items()}, "hourly": {key: round(value, 2) for key, value in hourly.items()}, "notes": notes})
        except Exception as error:
            errors[symbol] = str(error)
        time.sleep(0.13)
    rankings.sort(key=lambda row: row["score"], reverse=True)
    print(json.dumps({"fetched_at": datetime.now(IST).isoformat(), "rankings": rankings, "errors": errors}, indent=2))


if __name__ == "__main__":
    main()
