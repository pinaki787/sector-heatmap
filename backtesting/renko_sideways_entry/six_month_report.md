# Six-month NIFTY sideways-filter research

Underlying-price proxy ONLY; not executable options returns.

{
  "requested_from": "2026-04-12",
  "requested_to": "2026-10-11",
  "actual_from": "2026-04-13",
  "actual_to": "2026-10-09",
  "sessions": 124,
  "bars": 9300,
  "warmup_sessions": 12,
  "warmup_start": "2026-03-23",
  "missing_within_returned_sessions": [],
  "excluded_offsession": [
    {
      "timestamp": 1788752400,
      "time": "2026-09-07T09:10:00+05:30",
      "reason": "OUTSIDE_REGULAR_SESSION"
    },
    {
      "timestamp": 1788838800,
      "time": "2026-09-08T09:10:00+05:30",
      "reason": "OUTSIDE_REGULAR_SESSION"
    },
    {
      "timestamp": 1788924900,
      "time": "2026-09-09T09:05:00+05:30",
      "reason": "OUTSIDE_REGULAR_SESSION"
    },
    {
      "timestamp": 1788925200,
      "time": "2026-09-09T09:10:00+05:30",
      "reason": "OUTSIDE_REGULAR_SESSION"
    }
  ],
  "absent_weekdays": [
    "2026-04-14",
    "2026-05-01",
    "2026-05-28",
    "2026-06-26",
    "2026-09-14",
    "2026-10-02"
  ],
  "duplicates": 0,
  "revisions": 0
}

Fixed saved baseline: five-minute Auto bricks, ATR5, factor3 with existing regime adjustment; EMA10/30 widening2; RSI14 slope; EMA30 exit;15:10 cutoff. No higher timeframe or RSI level filter. Same Engine formulas, completed ordinary candles, next contiguous open, preserved exits, three chronological splits with prior-history warmup. No threshold search. Final holdout was not used to select parameters; some dates were previously examined in other research, so this is not globally unseen data.

Quota audit: production max_trades=2 counts accepted entry submissions per runner run, may be consumed even if broker rejects. RUN2 models two successful simulated entries per evaluation period and then no more (optimistic absent reject evidence). DAILY2 assumes a fresh run each session, which is NOT automatic production behavior. UNLIMITED is continuous signal research. Actual historical user restart times are unavailable.

Costs:0/2/5bp PER SIDE on underlying are sensitivity assumptions, not verified option commissions/spread/slippage. No historical option executable quotes, contract selection or broker rejection simulation. No production or account state changed.

| Period | Quota | Filter | Trades | Gross pts | Net2bp | DD pts | Absent losers | Missed winners | Mean matched delay min |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| DEVELOPMENT 2026-04-13–2026-06-11 | UNLIMITED | BASELINE | 129 | -128.4 | -1357.533 | 1453.752 | 0 | 0 | — |
| DEVELOPMENT 2026-04-13–2026-06-11 | UNLIMITED | CHOP55 | 116 | -104.65 | -1208.842 | 1305.061 | 17 | 10 | 10.36 |
| DEVELOPMENT 2026-04-13–2026-06-11 | UNLIMITED | CHOP61.8 | 123 | -76.45 | -1247.694 | 1343.913 | 6 | 5 | 8.75 |
| DEVELOPMENT 2026-04-13–2026-06-11 | UNLIMITED | ADX20 | 110 | -731.6 | -1779.755 | 1875.974 | 27 | 22 | 24.67 |
| DEVELOPMENT 2026-04-13–2026-06-11 | UNLIMITED | ADX25 | 77 | -622.05 | -1356.209 | 1357.959 | 53 | 31 | 27.97 |
| DEVELOPMENT 2026-04-13–2026-06-11 | UNLIMITED | REVERSALS_LOW_PROGRESS | 129 | -128.4 | -1357.533 | 1453.752 | 0 | 0 | — |
| DEVELOPMENT 2026-04-13–2026-06-11 | DAILY2 | BASELINE | 81 | -781.05 | -1553.433 | 1555.183 | 0 | 0 | — |
| DEVELOPMENT 2026-04-13–2026-06-11 | DAILY2 | CHOP55 | 80 | -675.25 | -1437.788 | 1521.552 | 6 | 2 | 10.0 |
| DEVELOPMENT 2026-04-13–2026-06-11 | DAILY2 | CHOP61.8 | 81 | -711.5 | -1483.856 | 1515.847 | 3 | 1 | 10.0 |
| DEVELOPMENT 2026-04-13–2026-06-11 | DAILY2 | ADX20 | 79 | -890.85 | -1644.057 | 1645.807 | 11 | 7 | 22.5 |
| DEVELOPMENT 2026-04-13–2026-06-11 | DAILY2 | ADX25 | 69 | -522.05 | -1179.727 | 1181.477 | 30 | 13 | 25.42 |
| DEVELOPMENT 2026-04-13–2026-06-11 | DAILY2 | REVERSALS_LOW_PROGRESS | 81 | -781.05 | -1553.433 | 1555.183 | 0 | 0 | — |
| DEVELOPMENT 2026-04-13–2026-06-11 | RUN2 | BASELINE | 2 | -182.45 | -201.437 | 202.137 | 0 | 0 | — |
| DEVELOPMENT 2026-04-13–2026-06-11 | RUN2 | CHOP55 | 2 | -182.45 | -201.437 | 202.137 | 0 | 0 | — |
| DEVELOPMENT 2026-04-13–2026-06-11 | RUN2 | CHOP61.8 | 2 | -182.45 | -201.437 | 202.137 | 0 | 0 | — |
| DEVELOPMENT 2026-04-13–2026-06-11 | RUN2 | ADX20 | 2 | -198.85 | -217.84 | 218.54 | 1 | 0 | 5.0 |
| DEVELOPMENT 2026-04-13–2026-06-11 | RUN2 | ADX25 | 2 | -179.5 | -198.651 | 211.649 | 1 | 0 | — |
| DEVELOPMENT 2026-04-13–2026-06-11 | RUN2 | REVERSALS_LOW_PROGRESS | 2 | -182.45 | -201.437 | 202.137 | 0 | 0 | — |
| VALIDATION 2026-06-12–2026-08-10 | UNLIMITED | BASELINE | 128 | 370.1 | -866.146 | 1128.027 | 0 | 0 | — |
| VALIDATION 2026-06-12–2026-08-10 | UNLIMITED | CHOP55 | 108 | 568.55 | -474.43 | 909.6 | 28 | 7 | 17.33 |
| VALIDATION 2026-06-12–2026-08-10 | UNLIMITED | CHOP61.8 | 122 | 351.05 | -826.959 | 1013.995 | 9 | 5 | 12.5 |
| VALIDATION 2026-06-12–2026-08-10 | UNLIMITED | ADX20 | 83 | 596.85 | -204.721 | 667.229 | 45 | 14 | 28.21 |
| VALIDATION 2026-06-12–2026-08-10 | UNLIMITED | ADX25 | 60 | 593.25 | 13.727 | 472.502 | 67 | 25 | 35.22 |
| VALIDATION 2026-06-12–2026-08-10 | UNLIMITED | REVERSALS_LOW_PROGRESS | 128 | 370.1 | -866.146 | 1128.027 | 0 | 0 | — |
| VALIDATION 2026-06-12–2026-08-10 | DAILY2 | BASELINE | 80 | 227.2 | -545.922 | 642.796 | 0 | 0 | — |
| VALIDATION 2026-06-12–2026-08-10 | DAILY2 | CHOP55 | 76 | 391.9 | -342.276 | 591.992 | 11 | 3 | 21.0 |
| VALIDATION 2026-06-12–2026-08-10 | DAILY2 | CHOP61.8 | 79 | 230.95 | -532.313 | 586.792 | 4 | 2 | 10.0 |
| VALIDATION 2026-06-12–2026-08-10 | DAILY2 | ADX20 | 74 | 775.15 | 60.177 | 471.055 | 18 | 3 | 27.0 |
| VALIDATION 2026-06-12–2026-08-10 | DAILY2 | ADX25 | 58 | 645.2 | 84.817 | 401.412 | 35 | 14 | 38.12 |
| VALIDATION 2026-06-12–2026-08-10 | DAILY2 | REVERSALS_LOW_PROGRESS | 80 | 227.2 | -545.922 | 642.796 | 0 | 0 | — |
| VALIDATION 2026-06-12–2026-08-10 | RUN2 | BASELINE | 2 | -77.55 | -96.236 | 96.236 | 0 | 0 | — |
| VALIDATION 2026-06-12–2026-08-10 | RUN2 | CHOP55 | 2 | -77.55 | -96.236 | 96.236 | 0 | 0 | — |
| VALIDATION 2026-06-12–2026-08-10 | RUN2 | CHOP61.8 | 2 | -77.55 | -96.236 | 96.236 | 0 | 0 | — |
| VALIDATION 2026-06-12–2026-08-10 | RUN2 | ADX20 | 2 | 97.85 | 79.081 | 91.847 | 1 | 0 | — |
| VALIDATION 2026-06-12–2026-08-10 | RUN2 | ADX25 | 2 | 66.75 | 47.975 | 91.847 | 1 | 0 | — |
| VALIDATION 2026-06-12–2026-08-10 | RUN2 | REVERSALS_LOW_PROGRESS | 2 | -77.55 | -96.236 | 96.236 | 0 | 0 | — |
| HOLDOUT 2026-08-11–2026-10-09 | UNLIMITED | BASELINE | 126 | 746.25 | -443.824 | 1230.292 | 0 | 0 | — |
| HOLDOUT 2026-08-11–2026-10-09 | UNLIMITED | CHOP55 | 112 | 705.15 | -351.527 | 1126.084 | 21 | 6 | 18.08 |
| HOLDOUT 2026-08-11–2026-10-09 | UNLIMITED | CHOP61.8 | 120 | 778.5 | -354.294 | 1164.543 | 7 | 2 | 5.0 |
| HOLDOUT 2026-08-11–2026-10-09 | UNLIMITED | ADX20 | 90 | 329.25 | -519.251 | 1097.747 | 44 | 21 | 27.07 |
| HOLDOUT 2026-08-11–2026-10-09 | UNLIMITED | ADX25 | 71 | 161.45 | -507.645 | 1051.675 | 64 | 32 | 40.0 |
| HOLDOUT 2026-08-11–2026-10-09 | UNLIMITED | REVERSALS_LOW_PROGRESS | 126 | 720.8 | -469.269 | 1255.737 | 1 | 0 | 5.0 |
| HOLDOUT 2026-08-11–2026-10-09 | DAILY2 | BASELINE | 79 | 673.15 | -73.066 | 861.849 | 0 | 0 | — |
| HOLDOUT 2026-08-11–2026-10-09 | DAILY2 | CHOP55 | 76 | 632.1 | -85.198 | 861.442 | 8 | 1 | 28.75 |
| HOLDOUT 2026-08-11–2026-10-09 | DAILY2 | CHOP61.8 | 77 | 685.9 | -40.85 | 872.145 | 3 | 0 | — |
| HOLDOUT 2026-08-11–2026-10-09 | DAILY2 | ADX20 | 71 | 346.0 | -323.917 | 950.33 | 24 | 8 | 33.24 |
| HOLDOUT 2026-08-11–2026-10-09 | DAILY2 | ADX25 | 64 | 296.4 | -306.844 | 850.874 | 36 | 17 | 43.15 |
| HOLDOUT 2026-08-11–2026-10-09 | DAILY2 | REVERSALS_LOW_PROGRESS | 79 | 647.7 | -98.511 | 866.96 | 1 | 0 | 5.0 |
| HOLDOUT 2026-08-11–2026-10-09 | RUN2 | BASELINE | 2 | 32.2 | 12.626 | 51.287 | 0 | 0 | — |
| HOLDOUT 2026-08-11–2026-10-09 | RUN2 | CHOP55 | 2 | 188.3 | 168.759 | 33.007 | 1 | 0 | — |
| HOLDOUT 2026-08-11–2026-10-09 | RUN2 | CHOP61.8 | 2 | 188.3 | 168.759 | 33.007 | 1 | 0 | — |
| HOLDOUT 2026-08-11–2026-10-09 | RUN2 | ADX20 | 2 | 111.35 | 91.824 | 68.058 | 1 | 0 | — |
| HOLDOUT 2026-08-11–2026-10-09 | RUN2 | ADX25 | 2 | 47.3 | 27.787 | 43.527 | 1 | 0 | — |
| HOLDOUT 2026-08-11–2026-10-09 | RUN2 | REVERSALS_LOW_PROGRESS | 2 | 32.2 | 12.626 | 51.287 | 0 | 0 | — |

## Monthly stability at2bp/side, continuous trades grouped by entry month

| Month | Quota | Baseline | CHOP55 | CHOP61.8 | ADX20 | ADX25 | Reversals/low progress |
|---|---|---:|---:|---:|---:|---:|---:|
| 2026-04 | UNLIMITED | -309.081 | -182.625 | -264.243 | -587.906 | -463.18 | -309.081 |
| 2026-04 | DAILY2 | -124.32 | -19.965 | -71.738 | -279.556 | -300.377 | -124.32 |
| 2026-05 | UNLIMITED | -501.224 | -525.634 | -409.717 | -642.867 | -295.123 | -501.224 |
| 2026-05 | DAILY2 | -932.435 | -921.144 | -915.439 | -768.073 | -328.343 | -932.435 |
| 2026-06 | UNLIMITED | -836.546 | -639.122 | -929.397 | -626.641 | -700.479 | -836.546 |
| 2026-06 | DAILY2 | -917.202 | -874.233 | -959.597 | -605.362 | -653.579 | -917.202 |
| 2026-07 | UNLIMITED | -383.82 | -198.711 | -329.927 | -139.912 | 82.808 | -383.82 |
| 2026-07 | DAILY2 | -0.684 | 95.155 | 13.468 | 56.261 | 153.898 | -0.684 |
| 2026-08 | UNLIMITED | -479.012 | -317.333 | -372.04 | -164.237 | -138.142 | -479.012 |
| 2026-08 | DAILY2 | -161.989 | -41.542 | -87.92 | -128.806 | -73.471 | -161.989 |
| 2026-09 | UNLIMITED | -662.023 | -620.684 | -627.826 | -743.748 | -717.27 | -687.468 |
| 2026-09 | DAILY2 | -531.11 | -543.957 | -531.11 | -631.761 | -581.141 | -556.555 |
| 2026-10 | UNLIMITED | 504.203 | 449.31 | 504.203 | 401.584 | 381.259 | 504.203 |
| 2026-10 | DAILY2 | 495.318 | 440.425 | 495.318 | 449.501 | 381.259 | 495.318 |

Absent baseline entries describe changed execution paths, not guaranteed saved money. Drawdown is mark-to-market underlying points; net figures are additive points, not percentage portfolio returns. No overnight underlying position carried. Four pre-open FYERS bars excluded consistently. All six absent weekdays match the official NSE2026 trading-holiday circular: https://nsearchives.nseindia.com/content/circulars/FAOP71777.pdf .

Validation: prefix invariance at100/1000/half-history, chronological unique OHLC/session checks. Warmup has no trades/quota use. Candidate uses no later data. Full trades and blocked assessments retained in JSON.

## Recommendation

Do not implement a sideways filter on this evidence. CHOP55 reduces unrestricted holdout loss443.82→351.53points and drawdown1230.29→1126.08, but sacrifices6baseline winners and does not make any split profitable at2bp/side. CHOP61.8 similarly remains negative throughout. Under the hypothetical daily two-entry scenario, CHOP55 worsens holdout−73.07→−85.20; CHOP61.8 improves it to−40.85, still negative. ADX20/25 are unstable and worsen unrestricted holdout. Reversal/low-progress worsens holdout−443.82→−469.27, despite the earlier short-sample result.

Monthly continuous results: baseline and CHOP55/61.8 negative in April(partial),May,June,July,August,September and positive only October(partial). ADX25 positive July and October, negative remaining months. No candidate shows broad monthly profitability. RUN2 comparisons are only two trades per split and cannot substantiate a general edge; actual unknown user restart/reject history prevents full production quota reconstruction.

All162 scenario summaries passed trade-total reconciliation and zero execution-gap checks; RUN2 never exceeded2entries and DAILY2 never exceeded2entries per session. Three prefix tests passed. Full trades, source/data hashes, blocked reasons, sensitivity cases and monthly attribution are retained alongside this report. No deployment recommended or performed.
