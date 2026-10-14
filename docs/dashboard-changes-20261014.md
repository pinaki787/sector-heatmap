# Dashboard updates — 14 October 2026

Deployed changes include read-only holdings review and visibility registration, collapsible signal/risk/exit settings with header switches, complete settings and selected chart timeframe transfer at Start, and historical OHLC recovery for chart display and fresh flat initialization. Completed-session validation remains strict for manual brick sizing; unfinished reference sessions are excluded first.

Trading session hours is a derived display: NSE/BSE equities, indices and derivatives 6; MCX commodities 14; Delta crypto 23. This field does not change the brick-size calculation.

The continuation-entry switch is present but remains disabled until its separately staged backend implementation is loaded. That backend implementation is not included here. Detailed broker diagnostics wiring and canonical per-instrument configuration consolidation remain unfinished. Sideways scalping is a proposal only.

Validation: seven Node interaction/settings tests and 25 Python holdings/history tests. Category display checks covered NSE stocks, Bank Nifty/index/futures, BSE stocks/indices, MCX and crypto. Mounted Start checks use mocked transport; no Live order or fill is asserted by these tests. No service restart or runner activation is part of this commit.
