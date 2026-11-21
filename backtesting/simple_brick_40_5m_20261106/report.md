# Simple Brick Only — NIFTY 50 ₹40 options — five-minute candles

30 completed sessions: 2026-09-23 to 2026-11-05. One lot of 65, ₹100,000 research capital, maximum five entries per session. Buy CALL on green, PUT on red; same strike held until opposite completed brick or 15:10 IST cutoff. Existing loss-range lock retained.

| Metric | Auto | Daily recalculated Manual |
|---|---:|---:|
| Gross P&L | ₹10,461.75 | ₹14,972.75 |
| Estimated charges | ₹7,071.35 | ₹3,749.23 |
| Net P&L | ₹3,390.40 | ₹11,223.52 |
| Return on research capital | 3.39% | 11.22% |
| Maximum marked drawdown | ₹11,152.70 | ₹18,152.99 |
| Maximum drawdown percent | 9.93% | 14.43% |
| Win rate | 28.24% | 28.99% |
| Profit factor, after costs | 1.07 | 1.29 |
| Trades | 131 | 69 |
| CALL trades | 62 | 37 |
| PUT trades | 69 | 32 |
| Average net trade | ₹25.88 | ₹162.66 |

NIFTY underlying buy-and-hold price return over the same window: 5.07% (not an option strategy or equal-risk benchmark).

Sizing is causal and recalculated before every session. Prior full-session Wilder ATR5; verified 375-minute session. Auto uses ATR × 3 × 5/375; Manual uses ATR/(375/30), rounded to two decimals, fixed for that day. No future session OHLC used.

Execution limitations: completed five-minute underlying CLOSE samples feed the deployed price-brick engine. Intraminute tick paths are unavailable. ₹40 selection uses the closest prior completed one-minute option CLOSE, with next-minute OPEN fills and ₹0.05 premium slippage each side. Thus historical bid/ask execution cannot be certified and fills can differ from ₹40. Drawdown uses net equity marked at one-minute boundaries while signals remain on completed five-minute candles, not intraminute extrema. Costs use the existing FYERS estimate, not broker bills. Dhan nearest-week rolling surface plus FYERS exact-contract repairs; historical absolute expiry identification is calendar-assisted.

Validation: both simulations COMPLETE, no price-gap or premium-surface audit issues, no missing marks; ten sample fixed-contract P&Ls independently matched backtesting.py. Source hashes, raw responses, journal CSVs, equity curves and full audit retained beside this report. No runners, settings, services or orders changed.

[Dhan historical rolling data documentation](https://dhanhq.co/docs/v2/expired-options-data/) · [FYERS fixed-contract historical data](https://fyers.in/api-docs/v3/api/market-data/expired-fo-data/get-expired-fo-data/) · [NSE lot-size circular](https://nsearchives.nseindia.com/content/circulars/FAOP70616.pdf)
