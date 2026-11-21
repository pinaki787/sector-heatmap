# Exit attribution — saved two-lot midpoint study

Read-only ledger analysis; no strategy rerun or trading changes.

Whole-entry terminal closures (256 entries, percentages use256):
| Terminal reason | Entries | % | Gross INR | Costs INR | Net INR |
|---|---:|---:|---:|---:|---:|
| Initial previous-candle stop, both lots |138|53.91| -150,085.00|11,729.15|-161,814.15|
| Midpoint stop after first-target partial |108|42.19|181,099.75|12,131.81|168,967.94|
| Scheduled15:29, both lots |10|3.91|1,599.00|877.22|721.78|
| Total |256|100.00|32,613.75|24,738.18|7,875.57|

Midpoint-terminal category includes BOTH the earlier first-target sale and remaining-lot result. Do not add first-target partial profits again to this whole-entry table.

Lot-leg exits (512 accounting lots, not independent entries):
| Actual lot-leg reason |65-unit legs|% of512|Gross INR|Allocated costs INR|Net INR|
|---|---:|---:|---:|---:|---:|
|Initial stop|276|53.91|-150,085.00|11,729.15|-161,814.15|
|First target partial|108|21.09|87,048.00|6,058.81|80,989.19|
|Midpoint stop remainder|108|21.09|94,051.75|6,073.00|87,978.75|
|EOD|20|3.91|1,599.00|877.22|721.78|

Main closing reason and dominant loss contributor: initial previous-candle spot stop, closing both lots before first target in138/256 entries. These were not all instantaneous:14/138 triggered during entry minute,33/138 in first2 candles,74/138 (53.62%) in first5 candles. Median stop trigger was4 minutes after entry; median actual option exit was5 minutes after entry. Thus rapid early stops were common, but entry-minute stops alone were not dominant.

For initial-stop entries, median entry-to-stop distance13.90 NIFTY points versus first-target distance35.52 points. For midpoint-terminal entries, medians14.58 and12.20 points respectively. This is a descriptive association: many initial-stop entries had a materially farther first grid target than initial stop. It does not independently establish the SMA signal or distance ratio caused the outcome.

110/256 entries (42.97%) touched first target.108 booked the separate65-unit target exit;2 hit in the final eligible minute and were netted into a single130-unit EOD order. All10 EOD entries therefore closed both lots there. No double-counting of partials:138 initial-stop entries+108 midpoint-terminal entries+10 EOD entries=256;276+108+108+20=512 lot legs.

CALL135 entries net-18,627.23; PUT121 entries net+26,502.79.

Triggers are NIFTY spot low/high touches of the active stop. After first target, the stop is full-candle(H+L)/2, only tightens, and becomes active next minute. Trigger detection occurs on completed minute OHLC; actual exits use next positive-volume option-minute OPEN. There were0 same-minute initial-stop/first-target ambiguous cases in this run and0 extra delayed exit bars. A spot stop can still occasionally produce a profitable option exit due to premium dynamics/timing; one initial-stop whole entry was net positive.

Sources: existing entries.csv,legs.csv,orders.csv,events.csv. Reproduce with .venv/bin/python backtesting/nifty_sma30_two_lot_midpoint_20261110/analyze_exits.py. exit_analysis.json retains all counts, duration distributions, side splits and EOD details; exit_terminal_summary.csv and exit_leg_summary.csv are table artifacts.

