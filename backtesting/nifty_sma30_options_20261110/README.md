# NIFTY SMA30 fixed-contract options baseline

Run from /home/trading/sector-heatmap:
FYERS_RESEARCH_TOKEN_FILE=<existing approved account token path> backtesting/nifty_sma30_options_20261110/venv312/bin/python backtesting/nifty_sma30_options_20261110/nifty_sma30_backtest.py

Research only: no runner, broker-order, restart or deployment APIs.

## Rules
October 2026, regular-session NIFTY50 spot one-minute candles. SMA30 uses the prior 30 available completed regular-session candles continuously across days (including September warmup). A crossing above buys a CE, below buys a PE. One lot (65 units), no pyramiding. The existing contract closes on the next opposite crossing before its replacement opens. Strike rounds the signal-close spot price to the nearest 50, ties upward. Expiry is the earliest provider-listed expired options expiry on or after that session. Contract symbol comes from the broker contract listing and is held unchanged until exit.

Signal candle timestamps identify interval starts: its close becomes known one minute later. Executions use that next minute option bar open. No opening position is carried from yesterday. No new entry at 15:29; surviving contracts close at the scheduled 15:29 bar open. This deliberately exits one minute before market close, avoiding invented 15:30 opens. A signal in the 15:29 bar is ignored because it completes at market close. Missing execution timestamps or zero-volume execution candles block aggregate metrics; missing held-contract marks also block them.

The initial spot archive is reused and supplemented only for October 24–31. No spot or option prices are interpolated or fabricated. Raw broker responses and SHA256 checksums are retained. Calendar completeness is not independently certified. The script requires 375 regular-session bars on each observed day; that cannot establish every exchange session is present.

## Estimated costs and execution limits
Flat INR20 per executed options order; exchange premium turnover rate 0.0355299%; clearing 0.009%; SEBI INR10/crore; IPFT INR0.01/crore; GST18% on brokerage/exchange/clearing/SEBI/IPFT; stamp0.003% buys; STT0.15% sells. Fee components retain precision, without contract-note daily rounding. These are modeled FYERS costs, not actual contract-note charges.

Sources:
- https://fyers.in/charges-list
- https://nsearchives.nseindia.com/content/circulars/FA73061.pdf
- https://nsearchives.nseindia.com/content/circulars/FAOP70616.pdf
- https://nsearchives.nseindia.com/content/circulars/FATAX73524.pdf
- https://fyers.in/api-docs/v3/api/market-data/expired-fo-data/get-expired-fo-data/

No spread, market impact, latency or slippage in the baseline. Candle opens with positive traded volume are historical prices, not assured executable fills. Equity marks held contracts at one-minute closes, pays entry fees at entry and exit fees at exit. Maximum drawdown is the resulting one-minute marked equity peak-to-trough rupee decline, including an initial zero P&L peak, rather than intrabar risk. Percentage drawdown is undefined without user-specified trading capital. NIFTY spot buy-and-hold return is a context benchmark, not an investible options comparison.

trades.csv is the immutable-contract round-trip ledger, equity.csv is the minute marked P&L, equity.html is a standalone chart, results.json holds calculated metrics. VectorBT independently replays each ledger trade with the exact two execution prices and total round-trip fees charged at entry for terminal-P&L verification only (VectorBT rejects exits whose fees exceed their sale proceeds). The main ledger and minute equity preserve side-specific fees and timing and verifies aggregate net P&L. No optimization or parameter search.

