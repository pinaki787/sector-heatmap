# NIFTY SMA30 with V1 grid trailing stops

Actual backtest window: 1–30 October 2026; 20 regular sessions. Real FYERS option premiums, 65 units per trade, no optimization. The original 657-trade flip baseline remains unchanged in the adjacent directory.

| Metric | SMA30 flip baseline | V1 grid trailing |
|---|---:|---:|
| Closed round trips | 657 | 225 |
| Net wins | 125 | 46 |
| Net win rate | 19.03% | 20.44% |
| Net profit factor | 0.88 | 0.86 |
| Gross P&L, INR | 20,221.50 | 1,530.75 |
| Estimated costs, INR | 44,096.88 | 14,936.54 |
| Net P&L, INR | -23,875.38 | -13,405.79 |
| Maximum minute-marked drawdown, INR | 40,149.00 | 32,406.89 |

The grid-trailing version loses less money and has lower marked drawdown, largely alongside fewer trades and lower costs. Its gross profit and profit factor are lower. Neither tested version is profitable after modeled costs.

## Confirmed entry and exit rules
Use the unchanged completed one-minute SMA30 crossing signals, next-minute option-open entries, nearest-expiry ATM at signal close, one 65-unit lot, fixed purchased contract and daily 15:29-open flatten. ATM rounds to nearest 50 points, ties up. No partial booking or pyramiding.

CALL initial spot stop = low of the one-minute candle immediately before the SIGNAL candle. PUT initial spot stop = that previous candle high. Validate against actual next-open spot entry; an invalid stop after a gap skips the trade. No such invalid gaps occurred among eligible entries.

Ignore opposite SMA crossings while holding, including crossings confirmed during the stop-trigger minute before the delayed exit is filled. A later fresh crossing is needed to re-enter.

Freeze the current day's completed V1 reference grid at entry. On NIFTY this is the first bearish 5-minute candle after the opening 09:15 candle, published only when its five minutes close. No use of prior-session, Shadow Candle or extra 30-minute grids. Skip signals before that current grid exists: 26 signals skipped.

Grid centers are H+nR and L-nR for n=1..10, R=H-L; select successive centers strictly in the favorable direction from the actual spot entry. Grid H/L and internal 44/50/56 levels are not substituted for target centers. The 44/50/56 constants and all Pine defaults remain untouched. SMART visibility is a display/reveal filter: the mathematical ten-level grid is fixed and known from the completed reference, so future formula-derived centers are available to the trail even before SMART draws them. No price-dependent future reference is used. Full grid/target choices are retained in grid_events.csv.

First favorable center reached: hold, move spot stop to actual NIFTY entry open. Second center: stop to first center. Third: stop to second, continuing one behind. Reaching multiple centers in one minute advances to one behind the furthest reached center, at that minute's close, effective only next minute. The largest target reached was seventh; the ten-level cap did not bind.

Old stop governs the complete current minute. If its OHLC touches both old stop and a new favorable target, assume old stop first; do not apply later targets retroactively. One ambiguous candle received this treatment. A confirmed target touch activates its new stop next minute. No optimistic same-bar trailing stop fill.

## Executions, equity and costs
Stop touches are detected using completed NIFTY minute OHLC; options exit at the NEXT available positive-volume option minute open, rather than an invented premium at the spot stop touch. This includes entry-minute stops. All stop exits had that next-minute bar available (zero extra delayed bars). EOD exit is scheduled at 15:29 open. A stop can gap, and entry-price spot breakeven is neither option-premium breakeven nor net-cost breakeven. Same-minute path ordering remains unknowable from OHLC.

Cost schedule is identical to the baseline: INR20 per order; exchange0.0355299%, clearing0.009%, SEBI10/crore, IPFT0.01/crore, GST18%, buy stamp0.003%, sell STT0.15%. No spread, latency, impact or slippage; positive volume does not prove executable fills. Contract-note rounding not modeled. Rates and sources are documented in the preserved baseline README.

Drawdown is peak-to-trough minute-close marked option equity, with actual entry/exit cost timing, not an intrabar worst case. Capital was unspecified, so rupee drawdown is provided; strategy percentage return and percentage drawdown are not asserted.

## Evidence
All 225 initial stops independently match the immediately preceding spot candle, all grids are available by entry, no trades overlap or carry overnight, all 657 candidate signals reconcile (225 entries, 26 pre-grid skips, 406 ignored while held). Exit reasons:127 initial stop,87 trailing stop,11 EOD. 147 trail-advancement events. Zero missing entry executions or invalid-stop skips. Full ledger net reconciles with marked-equity endpoint and an independent VectorBT terminal-P&L replay. VectorBT allocates round-trip fees at entry solely for its terminal cross-check, to avoid its low-premium-sale fee restriction; primary equity preserves actual cost timing. Five synthetic checks cover CALL/PUT mirroring, stop-first ambiguity and delayed trail activation.

Artifacts: grid_backtest.py; grid_trades.csv; grid_equity.csv; grid_events.csv; signal_decisions.csv; grid_results.json; comparison.csv; comparison.html; comparison_provenance.json. The raw option archive and its checksums remain in the baseline directory.

Run from /home/trading/sector-heatmap:
backtesting/nifty_sma30_options_20261110/venv312/bin/python backtesting/nifty_sma30_v1_grid_20261110/grid_backtest.py

Canonical V1 source SHA256: b61873371261ccda8aa64644ff64e2f5adecf425a9a9bdf0bb79da2da7566c19.
No live orders, runner state, settings, deployment or services changed.
