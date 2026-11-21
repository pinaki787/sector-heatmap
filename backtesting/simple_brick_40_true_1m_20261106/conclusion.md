# Final timeframe comparison

2026-09-23 to 2026-11-05, 30 sessions

| Timeframe | Sizing | Net P&L | Maximum drawdown | Profit factor | Win rate | Trades |
|---|---|---:|---:|---:|---:|---:|
| 1 minute | auto | ₹-1,924.19 | ₹8,197.64 | 0.92 | 28.67% | 150 |
| 1 minute | manual | ₹10,683.80 | ₹15,721.97 | 1.26 | 28.12% | 96 |
| 5 minutes | auto | ₹3,390.40 | ₹11,152.70 | 1.07 | 28.24% | 131 |
| 5 minutes | manual | ₹11,223.52 | ₹18,152.99 | 1.29 | 28.99% | 69 |

Daily-recalculated Manual on 1-minute observations had the stronger net-profit-to-maximum-drawdown balance in this sample. 5-minute Manual produced the highest net profit, but only 539.72 INR more with 2431.02 INR additional maximum drawdown. True 1-minute Auto lost money after costs. No live activation recommendation from this short candle-based sample.

Earlier 9755.34 INR Auto result used 5-minute-sized boxes with 1-minute observations; true 1-minute Auto sizing produced -1924.19 INR.

One lot, ₹40 target premiums, ₹100,000 initial capital, maximum five entries per session. Session-based prior completed ATR5 sizing recalculated daily; no future-session input. Manual sizing is independent of observation timeframe. Existing loss-range protection included. Estimated next-minute-open fills, assumed slippage and FYERS fees; one-minute valuation, unavailable intraminute tick path. No missing simulated prices; all four outcomes and sample P&Ls validated.
