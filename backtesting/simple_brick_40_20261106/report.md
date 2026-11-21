# Simple Brick Only — NIFTY 50 ₹40 options

30 completed sessions: 2026-09-23 to 2026-11-05. One lot of 65, ₹100,000 research capital, maximum five entries per session. Buy CALL on green, PUT on red; same strike held until opposite completed brick or 15:10 IST cutoff. Existing loss-range lock retained.

| Metric | Auto | Daily recalculated Manual |
|---|---:|---:|
| Gross P&L | ₹17,592.25 | ₹15,873.00 |
| Estimated charges | ₹7,836.91 | ₹5,189.20 |
| Net P&L | ₹9,755.34 | ₹10,683.80 |
| Return on research capital | 9.76% | 10.68% |
| Maximum marked drawdown | ₹10,945.12 | ₹15,721.97 |
| Maximum drawdown percent | 10.36% | 12.62% |
| Win rate | 26.90% | 28.12% |
| Profit factor, after costs | 1.23 | 1.26 |
| Trades | 145 | 96 |
| CALL trades | 73 | 46 |
| PUT trades | 72 | 50 |
| Average net trade | ₹67.28 | ₹111.29 |

NIFTY underlying buy-and-hold price return over the same window: 5.07% (not an option strategy or equal-risk benchmark).

Sizing is causal and recalculated before every session. Prior full-session Wilder ATR5; verified 375-minute session. Auto uses ATR × 3 × 5/375; Manual uses ATR/(375/30), rounded to two decimals, fixed for that day. No future session OHLC used.

Execution limitations: ordered one-minute underlying CLOSE samples feed the deployed price-brick engine. Intraminute tick paths are unavailable. ₹40 selection uses the closest prior completed one-minute option CLOSE, with next-minute OPEN fills and ₹0.05 premium slippage each side. Thus historical bid/ask execution cannot be certified and fills can differ from ₹40. Drawdown uses net equity marked at minute boundaries, not intraminute extrema. Costs use the existing FYERS estimate, not broker bills. Dhan nearest-week rolling surface plus FYERS exact-contract repairs; historical absolute expiry identification is calendar-assisted.

Validation: both simulations COMPLETE, no price-gap or premium-surface audit issues, no missing marks; deterministic replay tests passed and ten sample fixed-contract P&Ls independently matched backtesting.py. Source hashes, raw responses, journal CSVs, equity curves and full audit retained beside this report. No runners, settings, services or orders changed.

[Dhan historical rolling data documentation](https://dhanhq.co/docs/v2/expired-options-data/) · [FYERS fixed-contract historical data](https://fyers.in/api-docs/v3/api/market-data/expired-fo-data/get-expired-fo-data/) · [NSE lot-size circular](https://nsearchives.nseindia.com/content/circulars/FAOP70616.pdf)
