# October 2026 baseline result

Actual dates: 1–30 October 2026, 20 observed sessions, 7,500 spot minutes.
657 closed trades; 125 wins and 532 losses after costs.
One lot = 65 units; 99 immutable option contracts.

|Metric|Result|
|---|---:|
|Gross rupee P&L|20,221.50|
|Estimated costs|44,096.88|
|Net rupee P&L|-23,875.38|
|Net win rate|19.03%|
|Net profit factor|0.88|
|Maximum minute-marked rupee drawdown|40,149.00|

This unoptimized baseline lost money after estimated trading costs. Frequent crossings produced around 33 round trips per observed session. NIFTY spot rose 2.26% over the same window; this benchmark is contextual, with different exposure and no comparable options capital allocation. Percentage drawdown, percentage strategy return and Sharpe/Sortino are not reported because trading capital was unspecified.

Costs: brokerage 26,280.00; exchange 3,595.70; clearing 910.82; SEBI 10.12; IPFT 0.01; GST 5,543.40; stamp 151.50; STT 7,605.33. These are estimates from the published FYERS schedule, not actual contract notes.

Execution: next-minute option open after confirmed spot signal, chosen nearest expiry and ATM strike fixed until exit, no pyramiding, flat daily at 15:29 open. Zero modeled slippage, spread or latency. Positive-volume execution bars were required; real fills are unverified. SMA30 carries regular-session history across days. Marked drawdown uses minute closes, not intrabar extremes. See README.md for reproducible methodology and rate sources.

Both ledger-to-equity reconciliation and independent VectorBT terminal-P&L replay pass. VectorBT fee timing differs only for this terminal cross-check because one low-premium exit had fees exceeding its sale proceeds; authoritative equity retains actual entry/exit fee timing. No runners, settings, orders or hosted services were changed.
