# Renko Engine modes

Renko Engine preserves its independent brick and entry rules. It does not use Renko Supertrend signals.

Select a saved private broker account and instrument in the existing form. FYERS, Dhan and Delta India requests are scoped to the selected owner and account. FYERS requires its private workspace; shared server credentials are not a fallback.

Backtest replays completed broker candles without starting a runner or placing orders. Results use one chart-instrument unit, native quote currency, 0.03 percent commission per side and two ticks slippage. They are not option returns.

Paper and Live run on the server in separate Renko Engine state for each account. Preview activation, review the account, instrument, mode and limits, then enter the exact fresh confirmation phrase to start. Selecting Live alone does not start anything. Live retains broker authentication, account capability, quote, margin, position, duplicate-order and reconciliation checks.

Bullish option entries buy calls; bearish option entries buy puts. Opposite independent signals close the held position even when the replacement direction is disallowed. Session/end exits follow the independent settings. Manual override is unavailable.

Changing accounts clears the old chart and activation preview. Backtest, mode selection and chart refresh never arm a runner. Stop acts only on the selected account's Renko Engine runner. Existing Renko Supertrend runners are separate.

Validation covers 72 browser/server strategy combinations, isolated account routing for all three brokers, Paper execution, opposite exits, and uncertain Live acknowledgments using fake brokers. Deployment does not constitute a verified real Live fill.
