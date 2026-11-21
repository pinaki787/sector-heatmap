# Nifty Renko Supertrend — thirty-session review

**Decision: Needs Improvement. No live parameter change is justified by this study.**

Period: 2026-09-04 through 2026-10-19, 30 complete trading sessions. Development: first 20; chronological validation: final 10. All 39 variants were declared before option replay. This validation overlaps earlier research and is not pristine unseen evidence.

## Configuration and execution

FYERS Nifty one-minute spot candles supply signals; Dhan expired-option candles supply premium history. These are simulated FYERS trades, not historical FYERS fills. One lot of 65, starting capital INR100,000; nearest weekly ATM call on bullish entry or put on bearish entry, strike frozen until exit. Expiry dates are calendar inferred, not broker-certified. No manual overrides.

Daily arming at 09:15 IST; indicators retain preceding-session warmup. Evaluate only completed candles; execute at the next contiguous one-minute open. First completed-host evaluation: 5-minute 09:20, 1-minute 09:16. Fresh higher-timeframe confirmation delays possible entry: saved 5m/15m setup no earlier than 09:30; prior 1m/5m setup no earlier than 09:20. Mandatory square-off 15:10, no overnight positions. No automatic job/schedule or runner start was created.

Costs use the [FYERS published tariff](https://fyers.in/charges-list): INR20 per executed option order plus STT, exchange, clearing, SEBI, IPFT, stamp and GST. Base adverse slippage: 0.05% per side; stress: 0.20% per side, with full path reruns. Historical bid/ask spreads and tick execution are unavailable; actual fees and fills may differ.

## Data quality

Underlying: 0 duplicate, 0 invalid, 17 off-session rows excluded. Every scored spot session has 375 contiguous one-minute candles. Option history: 519,616 unique valid strike/time observations; 0 conflicting observations removed; 0 invalid observations and 14270 off-session observations excluded.

Complete scenario coverage: 39 / 39 variants. A missing required contract invalidates a replay; it is never filled with a different strike or a zero-profit trade.

## Development-ranked comparison

Ranking uses development stress net minus half sampled drawdown. Validation is displayed only after the candidate is selected; it does not select a replacement.

| Variant | Dev trades | Dev net, base INR | Dev net, stress INR | Validation trades | Validation net, base INR | Validation net, stress INR | Validation drawdown, base INR |
|---|---:|---:|---:|---:|---:|---:|---:|
| saved_5m_15m | 7 | -5,684.96 | -5,835.50 | 5 | -2,641.38 | -2,741.27 | 5,131.77 |
| prior_1m_5m | 18 | -4,931.69 | -5,215.40 | 6 | 12,412.67 | 12,280.30 | 3,144.26 |
| RSI_slope_only | 24 | 4,524.58 | 4,074.30 | 12 | 17,718.04 | 17,447.19 | 6,056.10 |
| ema_proximity_distance_0.75 | 14 | 3,954.82 | 3,714.24 | 10 | 1,908.52 | 1,684.62 | 7,946.68 |
| EMA_8_21 | 1 | 3,682.93 | 3,658.54 | 4 | -3,132.11 | -3,209.28 | 3,635.92 |
| retest_off | 0 | 0.00 | 0.00 | 2 | 832.72 | 781.77 | 1,857.34 |
| EMA_13_50 | 0 | 0.00 | 0.00 | 0 | 0.00 | 0.00 | 0.00 |
| RSI_wider | 21 | 5,781.65 | 5,401.49 | 8 | -598.93 | -767.22 | 5,262.27 |
| gap_contraction_exit | 7 | -1,100.17 | -1,256.59 | 6 | 644.43 | 531.72 | 1,196.01 |
| supertrend_timeframe_1 hour | 3 | 827.18 | 761.90 | 4 | -4,120.74 | -4,198.82 | 6,139.33 |

Development-eligible candidates: 0. Selected: none. Validation gate passed: False. The gate requires at least eight development trades, positive call and put stress net, and positive stress net in both development halves; validation requires at least five trades and positive call and put stress net.

## Call/put and risk detail

### saved_5m_15m

- development: calls 4 trades / INR-6,633.28; puts 3 trades / INR948.32; win rate 14.3%, profit factor 0.4270945481586749, expectancy INR-812.14, largest win INR4,238.08, largest loss INR-2,447.53, worst loss streak 3, fees INR454.29.
- validation: calls 4 trades / INR-4,120.74; puts 1 trades / INR1,479.37; win rate 20.0%, profit factor 0.35900481776009974, expectancy INR-528.28, largest win INR1,479.37, largest loss INR-1,712.41, worst loss streak 2, fees INR320.08.
### prior_1m_5m

- development: calls 7 trades / INR-2,755.95; puts 11 trades / INR-2,175.74; win rate 22.2%, profit factor 0.08025885020056327, expectancy INR-273.98, largest win INR262.19, largest loss INR-856.30, worst loss streak 11, fees INR1,089.54.
- validation: calls 5 trades / INR12,229.11; puts 1 trades / INR183.55; win rate 66.7%, profit factor 16.348873874430883, expectancy INR2,068.78, largest win INR7,005.00, largest loss INR-557.33, worst loss streak 1, fees INR406.70.
### RSI_slope_only

- development: calls 10 trades / INR-11,093.23; puts 14 trades / INR15,617.81; win rate 25.0%, profit factor 1.2638306811845192, expectancy INR188.52, largest win INR7,559.10, largest loss INR-2,235.59, worst loss streak 7, fees INR1,519.84.
- validation: calls 7 trades / INR5,873.07; puts 5 trades / INR11,844.97; win rate 41.7%, profit factor 4.419767331664955, expectancy INR1,476.50, largest win INR10,915.45, largest loss INR-1,712.41, worst loss streak 3, fees INR813.84.

## What to do before the next live run

Do not pick the largest historical winner. If no candidate passes, retain the baseline only as a research reference and do not label any replacement ideal. Manual overrides must be assessed separately; today they bypassed the very filters being optimized. The existing sideways control is a quick-loss range lock, not a predictive entry classifier. ADX and widening/proximity changes are tests of selectivity, not guarantees against ranges. Broker quantity reconciliation is an independent operational concern.

Thirty sessions and a maximum two trades/day cannot establish robust live profitability across regimes. These tests do not exhaust all combinations. A promising candidate requires paper forward testing and additional genuinely unseen sessions, including higher slippage and expiry-day checks.

## Reproduction and artifacts

Run research.py prepare, research.py run, then report.py in this folder. Retained plan.json includes all configured settings, tested changes, data audit and source hashes. comparison.csv includes all scenarios; trade-journal.csv includes fixed strikes, entry/exit times, reasons, costs and entry indicators. A no-trade cash benchmark earns INR0; the original and saved runner settings are the actionable strategy benchmarks.

No live settings, credentials, runner activation, orders, or service state were changed.

## Full thirty-session outcomes — descriptive, not selection evidence

| Configuration | Trades | Net INR | Win rate | Max sampled drawdown INR | Call net INR | Put net INR |
|---|---:|---:|---:|---:|---:|---:|
| saved_5m_15m | 12 | -8,326.34 | 16.7% | 14,149.68 | -10,754.02 | 2,427.68 |
| prior_1m_5m | 24 | 7,480.98 | 33.3% | 6,372.92 | 9,473.17 | -1,992.19 |
| RSI_slope_only | 36 | 22,242.62 | 30.6% | 15,449.06 | -5,220.16 | 27,462.78 |
| ema_proximity_distance_0.75 | 24 | 5,863.35 | 29.2% | 17,840.52 | -7,484.06 | 13,347.41 |

Exploratory RSI-slope-only variant: remove the host RSI level band, retain RSI14 slope and every other saved baseline setting. Removing its three largest winners changes full-period net to INR-6,151.06. Its call side is negative across the full sample. This is not sufficient evidence for a combined call/put live setting.

The ADX20/25 variants and quick-loss-window changes did not improve the baseline trade path in this sample. More enabled filters do not automatically remove range losses.

## Saved baseline settings

| Setting | Value |
|---|---|
| timeframe | 5 minutes |
| supertrend_timeframe | 15 minutes |
| brick_mode | Manual |
| manual_brick | 24.92 |
| atr_length | 5 |
| factor | 3.0 |
| ema_fast_length | 10 |
| ema_slow_length | 30 |
| widening_window | 2 |
| ema_proximity_mode | ATR |
| ema_proximity_distance | 0.5 |
| rsi_slope_length | 14 |
| rsi_bullish_min | 60.0 |
| rsi_bullish_max | 70.0 |
| rsi_bearish_min | 35.0 |
| rsi_bearish_max | 40.0 |
| retest_enabled | True |
| use_adx | False |
| adx_threshold | 20.0 |
| ema_exit_length | 30 |
| sideways_enabled | True |
| sideways_max_candles | 2 |
| trailing_enabled | False |
| max_trades | 2 |
| lots | 1 |
| rsi_htf_1_enabled | False |
| rsi_htf_2_enabled | False |
| rsi_htf_3_enabled | False |

## Next trading session

Tuesday 20 October is an NSE F&O trading holiday for Dussehra. The next normal session is Wednesday 21 October. Source: [NSE 2026 F&O holiday circular](https://nsearchives.nseindia.com/content/circulars/FAOP71777.pdf). No schedule has been created.

A saved-config.json snapshot preserves every configured field. An isolated plotting environment is used only for this research. QuantStats is unavailable; annualized performance ratios and risk-of-ruin forecasts are omitted because this short option sample would not establish them.