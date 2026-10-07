# Virtual INR capital

Paper starts accept `paper_capital_inr`, default ₹100,000. The amount is positive, finite, and limited to ₹1 billion. Requested shares, lots, and Delta contracts are preserved. Insufficient virtual buying power blocks the entry; it never scales down quantity or substitutes a live broker balance.

The shared Renko and RSI runners use separate wallets for each run, including independent saved instruments. EMA Band and KAMA use their own run wallets. Delta's standalone manual/strategy Paper workflow shares its durable isolated Paper ledger; historical realized P&L and fee provisions remain in that wallet. Straddles use isolated simulation copies and per-run wallets, retaining the original wallet and lot setting while held exposure is resumed.

Available capital equals initial capital plus gross realized P&L, less reserved premium/notional and simulated fee provision. Open unrealized gains do not increase buying power. Cash and futures reserve full notional; long options reserve full premium. There is no simulated leverage or broker-margin estimate. A 1% entry cushion is required in addition to the fee provision.

Fee provisions are conservative buying-power allowances, not broker invoices: FYERS uses 0.5% of notional/premium per filled side; Delta options use the 3.5% premium fee cap plus 18% GST; standalone Delta futures use 0.05% notional plus 18% GST. Existing trade performance remains explicitly gross or uses its existing cost estimator.

Delta uses the verified fixed platform settlement conversion (currently ₹85 per USD). Missing or stale conversion evidence blocks new Paper commitments and shows INR unavailable. Fresh market data, exact contract units, spread gates, completed-candle rules, trade limits, configured premium/loss limits, and expiry controls remain active. Paper does not read live balances for buying-power validation. FYERS authentication is still required to obtain FYERS market data; Delta Renko Paper uses public market data.

Live orders retain broker funds/margin checks, order gates, quantities, and approval requirements. Deploying the backend requires a safe server restart. A running Paper session continues with the deployed code until stopped; frontend start guards refuse to claim virtual capital support from an older backend. Deployment never arms or replays a strategy.

Delta chart prices, P&L, trade tables and research result money use INR display. Contract symbols, quantities, RSI/ADX, percentages and explicitly labelled native-point inputs remain native. Audit JSON preserves original calculation and order evidence.
