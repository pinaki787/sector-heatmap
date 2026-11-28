# Sector Pulse — Renko continuation and chart release, 28 November 2026

- Restore completed-adverse-brick confirmation for Renko-only target-grid trailing exits; price ticks can ratchet targets but cannot bypass the exit confirmation contract.
- Add persisted trailing-exit continuation: confirmed flat, completed counter-direction pullback, then a later completed original-direction close beyond a frozen reference. No fresh signal or touch-only catch-up entry.
- Retain support/resistance profit and failed-retest continuation alongside the optional target-grid ladder and verified strategy-stop display.
- Extend matching completed Supertrend toward the provisional brick in stopped/draft charts without feeding provisional values into execution.
- Reuse completed Renko preview history across partial ticks; invalidate on completed-data, history or account changes.
- Show the Midline on candlestick charts independently of its entry filter. Candlestick entry filter defaults on; explicit per-user/account/instrument opt-out survives refresh. Renko filter remains off and unavailable.
- Include associated maintained chart reference/source, historical label and presentation changes accumulated since the previous release commit.

Validation: 864 strategy tests passed for the execution release; 39 focused frontend checks passed after Midline default changes. Earlier chart projection/cache group passed 68 checks. Hosted stopped BTCUSD draft verified after 999 older candles and at 600px width. Candlestick default, explicit opt-out persistence and Renko/candlestick switching verified on hosted dashboard.

Deployment: canonical and six maintained source copies synchronized; Delta dashboard loaded the execution release while all Delta workers stopped. Latest Midline changes are static frontend only. Protected captured settings and ledgers retained identical hashes during the guarded reload. No worker starts or orders were performed. BTCUSD remains off for the user to start.

Limitations: no forced real-position exit/re-entry cycle; no guaranteed broker fill or millisecond Pine cold-start latency. Other workspaces received source files without trading-worker interruption.
