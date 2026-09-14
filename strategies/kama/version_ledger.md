# KAMA Strategy Version Ledger

Use the same symbol, chart interval, date range, and Strategy Tester settings for each comparison.
Do not promote a new version without comparing it to the current baseline.

| Version | Rule change | Window | Net P&L | Max drawdown | Profit factor | Profitable trades | Trade count | Status |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| V5 | KAMA direction plus ATR-scaled slope and breakout/reclaim entries | Not retained | — | — | — | — | — | Replaced after delayed impulse entries |
| V6 | Removes ATR-scaled slope threshold; KAMA direction plus efficiency ratio and breakout/reclaim | Last 7 days | ₹278.90 | ₹76.50 | 2.170 | 33.33% (7/21) | 21 | Baseline for V7 comparison |
| V7 | Breakout-only; removes reclaim entries; 0.10 ATR breakout buffer; 5-bar cooldown | Last 7 days | ₹205.05 | ₹79.75 | 2.092 | 29.41% (5/17) | 17 | Active test; does not yet beat V6 on this window |

## Review protocol

1. Compare V6 and V7 only on the same seven-day window.
2. Record every rule change before it is tested.
3. Review losing trades and visibly missed moves before proposing a new version.
4. Expand to longer windows only after the seven-day comparison is understood.
