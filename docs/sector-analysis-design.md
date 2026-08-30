# Multi-Timeframe Sector Analysis Design

## Existing architecture

- The production dashboard is `index.html` plus `dashboard-enhancements.js`, served by Python's `ThreadingHTTPServer` from `sector_heatmap/web.py`.
- The React/Vite client is a parallel build artifact and is not the page served by `heatmap_server.py`.
- FYERS is the only market-data provider. `FyersLiveFeed` supplies live index and constituent ticks; `FyersModel` supplies account and historical candle APIs.
- The project previously had no candle cache, indicator utility, ranking engine, persistent database, scheduler, or charting library.

## Analysis flow

```text
FYERS history API
  -> shared completed-candle cache
  -> dependency-free indicator functions
  -> timeframe trend + RS states
  -> mode-weighted sector score
  -> ranking + bounded snapshot history
  -> rotation/events
  -> /api/sector-analysis
  -> existing dashboard
```

15-minute, 1-hour, and Daily candles are requested once per symbol per cache TTL. Weekly candles are derived from the same long Daily series, avoiding a duplicate provider download. Indicators for a timeframe share that candle list.

## Deterministic calculations

- Trend uses EMA20/50/200 structure, ATR-normalized EMA20/50 slope, RSI14, and directional ADX/DMI14. ADX supplies strength; `+DI` versus `-DI` supplies direction.
- Relative strength is `sector close / NIFTY 50 close`, aligned by candle timestamp. Its score uses position versus RS EMA20, five-bar percentage slope, and ROC10.
- Momentum combines RSI (45%), normalized ROC10 (30%), and ATR-normalized EMA20 slope (25%).
- Overall score starts with trend 25%, relative strength 25%, breadth 20%, volume participation 15%, and momentum 15%. Missing components are never invented; their weight is redistributed proportionally across available components and the effective weights are returned.
- Intraday mode weights 15m/1h/Daily/Weekly at 30/40/25/5. Swing weights them at 0/10/50/40.
- Alignment is separate from score. Full alignment requires at least three available timeframes pointing the same way; Daily plus Weekly agreement produces bullish or bearish alignment; other combinations are mixed.
- Rotation requires persisted observations and combines current score, score velocity, rank direction, and acceleration relative to the previous velocity.

## Cache, history, and refresh

- Candle cache is process-local and timeframe-aware: 15m 15 minutes, 1h one hour, Daily one hour, Weekly six hours.
- The background analysis refresh checks every five minutes, while cached candle TTLs prevent unnecessary history calls.
- Bounded snapshot history (120 points per sector and mode) is stored atomically under `~/.fyers/sector-heatmap/analysis-history.json`, or `SECTOR_ANALYSIS_STATE_FILE` when configured. No database was added.
- Indicator states use completed candles only. Data quality is explicit: `DELAYED`, `STALE`, `INSUFFICIENT DATA`, or `UNAVAILABLE`.

## Current data boundaries

- Breadth and volume participation calculations exist as reusable, tested engines. Live values remain unavailable because the existing application does not retrieve completed historical candles for every constituent. The API redistributes their score weights and explains the omission.
- The stock drill-down uses the existing live constituent basket and identifies current strongest/weakest contributors. It is analytical prioritization, not a full stock setup engine and never submits an order.
- With no existing chart library, the detail view uses small dependency-free SVG history lines. It does not add a competing chart package.
- Alert-ready transition events are returned in the analysis snapshot; notification delivery is intentionally not implemented because the application has no alert subsystem.
