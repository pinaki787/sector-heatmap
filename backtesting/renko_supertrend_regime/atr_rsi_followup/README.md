# ATR, RSI and directional-efficiency follow-up

An optional combined regime gate is implemented in the isolated research script. It is not connected to a Live runner.

Proposed entry gate, using completed five-minute host candles only:

- Existing Supertrend direction supplies bullish/bearish orientation.
- ATR5 is at least 1.05 times the mean of its preceding 20 values.
- Over 12 bars, direction-adjusted net price movement / total absolute close movement is at least 0.30.
- The direction-adjusted net movement is at least one ATR5.
- RSI14 is at least 55 for bullish entries, or at most 45 for bearish entries.
- ADX14 is at least 20. Combined mode does not require rising ADX.
- Require full warm-up and a same-session 12-bar price lookback.

| Period | Baseline PF | Combined PF | Combined signals | Positive moves: baseline | Positive moves: combined |
|---|---:|---:|---:|---:|---:|
| First six months | 1.15 | 1.19 | 88 | 52.97% | 47.73% |
| Middle quarter | 0.99 | 1.27 | 37 | 48.30% | 54.05% |
| Latest quarter | 0.90 | 1.42 | 50 | 49.27% | 42.00% |
| Full year | 1.06 | 1.25 | 175 | 50.96% | 47.43% |

Full-year retention: 175 of 1,978 entry signals (8.85%). Average direction-adjusted 30-minute movement: 2.97 points, versus baseline 0.72. A hypothetical total 2-point drag leaves 0.97 points per retained signal; this is not an actual cost model.

**Interpretation:** the combination improved signal profit factor across the three displayed periods, but did not improve positive-move frequency consistently. In the latest quarter the combined positive-move rate was 42.00%, despite profit factor 1.42: larger wins can improve PF while losses remain frequent. Better winning streaks are not established.

**Research limits:** all statistics refer to overlapping, hypothetical underlying-index signals at next-bar opens, measured 30 minutes later, before actual trading costs. They are not option P&L or executed trade win rates. Earlier results had already been inspected before these follow-up rules were tested, so the latest quarter is not a fresh untouched holdout. Only 37 middle-quarter and 50 latest-quarter signals survived. Current 27.71-point brick is retrospectively applied. Complete runner lifecycle, position/exposure limits, historical option premiums and exact costs remain untested.

**Additional earlier-year check, same frozen specification:** 25 October 2024–24 October 2025, 246 regular sessions. Baseline signal PF was 1.14 across 2,009 signals; combined PF was 1.01 across 189 signals. Combined mean forward movement was only 0.10 points, and -1.90 after hypothetical 2-point drag. The earlier year has no pre-archive warm-up; normal indicator warm-up is excluded. Retrospective manual-brick and execution limitations still apply.

**Conclusion:** this is a working isolated regime classifier, not a robust strategy enhancement. Do not activate it as a proven profit or winning-streak improvement. Next research should test sensible brick-size stability and complete trade lifecycle with actual executable instrument data rather than keep adjusting thresholds to fit these observed samples. No runtime restart or trading-setting change was made.

Reproduce: followup.py in the parent folder; eight boundary tests in test_followup.py.
