from pathlib import Path
import json,html,base64
import numpy as np,pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent
j=json.loads((P/'summary.json').read_text());audit=j['audit'];res=pd.DataFrame(j['strategy']);cov=pd.DataFrame(j['coverage']);fwd=pd.read_csv(P/'forward_study.csv');matched=pd.read_csv(P/'matched_forward.csv');month=pd.read_csv(P/'monthly.csv');breakdown=pd.read_csv(P/'breakdown.csv')
main=res[(res.variant=='main')&(res.roundtrip_cost_points==2)].iloc[0]
net=res[res.roundtrip_cost_points==2].set_index('variant');gross=res[res.roundtrip_cost_points==0].set_index('variant')
labels={'baseline':'Unfiltered EMA direction','loose':'Loose checklist','main':'Main checklist','strict':'Strict checklist','zero_overlap':'Literal zero overlap'}
fig,axes=plt.subplots(1,2,figsize=(14,5),gridspec_kw={'width_ratios':[1.25,1]},facecolor='#f5f7fb')
for ax in axes:ax.set_facecolor('#f5f7fb');ax.spines[['top','right']].set_visible(False);ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
names=list(net.index);y=np.arange(len(names));axes[0].barh(y-.17,[gross.loc[n].net_points for n in names],height=.3,color='#96b4d5',label='Before costs');axes[0].barh(y+.17,[net.loc[n].net_points for n in names],height=.3,color=['#ad5768' if net.loc[n].net_points<0 else '#21837a' for n in names],label='After 2-point round trip');axes[0].set_yticks(y,[labels[n] for n in names]);axes[0].invert_yaxis();axes[0].axvline(0,color='#64748b',lw=.8);axes[0].set_xlabel('Nifty index points · illustrative strategy');axes[0].set_title('Costs erase the apparent edge',loc='left',fontweight='bold');axes[0].legend(loc='lower left',fontsize=8)
funnel=pd.DataFrame(j['gate_funnel']);axes[1].barh(range(4),funnel.cumulative_pass_percent,color=['#97afc8','#7698bb','#577eaa','#294d7b']);axes[1].set_yticks(range(4),['ATR gate','+ EMA slope','+ EMA separation','+ Candle structure']);axes[1].invert_yaxis();axes[1].set_xlim(0,50);axes[1].set_xlabel('% of all five-minute bars remaining');axes[1].set_title('Main filter keeps only 1.92% of bars',loc='left',fontweight='bold')
for i,v in enumerate(funnel.cumulative_pass_percent):axes[1].text(v+.5,i,f'{v:.2f}%',va='center',fontsize=9)
fig.suptitle('Nifty 5-minute anti-chop study | 24 Oct 2025–23 Oct 2026',x=.04,ha='left',fontsize=15,fontweight='bold',color='#20334e');fig.text(.04,.02,'247 complete sessions · spot-index proxy · next-open fills · no futures/option execution claim',fontsize=9,color='#52657d');fig.tight_layout(rect=[0,.05,1,.91]);fig.savefig(P/'summary.png',dpi=150,bbox_inches='tight');plt.close(fig)
def table(df):return df.to_markdown(index=False,floatfmt='.2f')
comparison=net.reset_index()[['variant','trades','net_points','win_rate_percent','profit_factor','max_drawdown_points','daily_sharpe_proxy','daily_sortino_proxy']].copy();comparison.variant=comparison.variant.map(labels)
source_files=['nifty_antichop_backtest.py','verify_antichop.py','audit.json','verification.json','requirements-lock.txt','bar_evidence.csv','strategy_comparison.csv','forward_study.csv','matched_forward.csv','monthly.csv','breakdown.csv']
text=f'''# Nifty five-minute anti-chop backtest

**Result: this test does not establish a profitable trading edge.** The main illustrative strategy made **16.70 points before costs**, but lost **499.30 points after a hypothetical two-point round-trip deduction**. Profit factor was **0.79** across **258 closed trades**. This is one explicit interpretation of a discretionary filter, not a claim that every strategy using the checklist will lose.

## Data and integrity

Period: **24 October 2025–23 October 2026**, the latest complete year in the reusable archive; it ends before the current date. Instrument: **FYERS NIFTY 50 spot index**, not futures or options. **247 sessions / 18,525 five-minute bars**, regular session 09:15–15:30 IST. More than a year of earlier bars provides indicator warmup. All accepted sessions contain 75 five-minute and 375 one-minute bars. No candles were forward-filled. Aggregating the one-minute archive reproduced five-minute OHLC exactly (36,900 compared bars across the full eligible archive; zero discrepancies). Exchange holiday-calendar completeness has not been independently certified. Off-hours and incomplete special-session data are excluded.

Source hashes, exact coverage and provenance are in `audit.json`; indicator library is OpenAlgo ta, portfolio simulator VectorBT. The reproduction script and package lock are included. No broker requests, production settings, runners or orders were changed for this research.

## Rules translated from your checklist

The wording describes a filter rather than a complete strategy. You selected a filter study plus a clearly labelled example strategy. Only the ATR condition is numerically specified in the original wording; the following thresholds are **research assumptions**, not optimized values or your supplied rules.

| Check | Main interpretation |
|---|---|
| Volatility | ATR(14) strictly greater than SMA(20) of ATR(14) |
| EMA20 slope | `(EMA20[t] - EMA20[t-3]) / ATR14[t]` at least +0.15 for long, at most -0.15 for short |
| EMA separation | Absolute EMA20–EMA50 gap at least 0.20 ATR; no EMA20/50 cross during the latest six bars; EMA20 above EMA50 for long, below for short |
| Clean structure | Three same-session candles with two successive higher-high AND higher-low steps for long, or lower-low AND lower-high steps for short; mean adjacent range-overlap no greater than 50% |

Overlap equals the intersecting price range divided by the smaller adjacent candle range. Zero-range candles fail this structure check. Structure does not span overnight gaps. ATR and EMAs use continuous regular-session history rather than resetting daily.

The looser version uses slope 0.10 ATR, separation 0.10 ATR, one directional step and overlap ≤65%. The stricter version uses slope 0.25 ATR, separation 0.30 ATR, two steps and overlap ≤35%. A separate **literal zero-overlap** case keeps the main slope/separation/two-step settings and requires no adjacent range intersection. These are sensitivity scenarios, not a search for the best parameters.

## Filter coverage

{table(cov)}

**Literal zero overlap produced zero qualifying bars and zero trades.** Thus, the relaxed 50% overlap assumption materially changes what is being tested.

Main gate funnel:

{table(pd.DataFrame(j['gate_funnel']))}

The structure/overlap condition is the main bottleneck: after ATR, slope and separation, 20.69% of all bars remain; adding structure reduces that to 1.92%. A clean-looking candle sequence often lasts only one qualifying bar. This is why using the filter itself as an immediate exit rule can create short holding periods and cost sensitivity.

## Filter-only forward study

At a qualifying completed bar, evaluate entry at the next bar open and direction-adjusted movement through the close 15, 30 or 60 minutes later. Long and short moves are signed consistently. Any sample that would cross a session boundary is excluded. These samples overlap and are not statistically independent; no statistical-significance claim is made.

Main results against controls matched by calendar month, half-hour time slot and EMA trend direction:

{table(matched)}

The main filter does not consistently outperform the matched baseline: it is weaker over 15 and 30 minutes and stronger over 60 minutes. This does not by itself define a tradeable system.

## Example strategy — assumed entry and exit rules

1. Observe only completed five-minute candles. Long when all checks pass with bullish EMA alignment; short for bearish alignment.
2. Enter at the **next five-minute open**, once per fresh qualifying episode. No same-close fills.
3. Signal exits when any checklist condition fails or EMA direction changes; execute at the following bar open. An opposite entry closes the current position; it does not instantly reverse at that same fill.
4. Entry signal windows are 09:25–15:10 IST. The 15:20 candle forces an exit at the 15:25 open, so there is no overnight position.
5. One spot-index point unit, no leverage/margin modelling. Initial bookkeeping cash is twice the first index open. Percentage returns and daily risk ratios depend on this normalization and are not deployable futures returns.
6. Compare zero, two and five **hypothetical index points per round trip**; these are sensitivity deductions, not verified broker fees. No extra slippage, bid/ask, futures basis, rolls, expiry, lot size or option premium dynamics are modelled.

## Strategy comparison

All rows below use the two-point round-trip deduction. The unfiltered baseline trades EMA20/50 direction with the same session, entry/exit execution and sizing rules, but without the four anti-chop gates.

{table(comparison)}

Cost sensitivity:

{table(res[['variant','roundtrip_cost_points','trades','net_points','mean_trade_points']])}

The buy-and-hold Nifty spot reference lost **{j['benchmark']['net_points']:.2f} points**, with **{j['benchmark']['max_drawdown_points']:.2f} points** of marked drawdown. It holds overnight and is not a like-for-like intraday benchmark. The intraday EMA baseline is the more relevant comparison.

Normalized comparison (same initial bookkeeping notional; not futures margin returns):

{table(pd.read_csv(P/'benchmark_comparison.csv'))}

## Stability and limitations

Main strategy by chronological half, with the same fixed parameters: first half **-413.70 points**, second half **-85.60 points** after the two-point round trip. No parameter was selected on the first half and then validated on untouched later data. Treat this as a descriptive one-year historical study, not walk-forward validation.

Twenty-seven prefix-invariance checks confirmed that EMA20, EMA50 and ATR14 values do not change when later data are removed. All accepted trade entry and exit prices reconcile to archived opens; all trades are flat by session end. The independent verifier checks the prior-bar signal and reconstructs every trade P&L. `verification.json` contains the evidence. Long/short and half-year breakdowns are in `breakdown.csv`; monthly results are in `monthly.csv`.

The strict case is closer to breakeven after costs but is still negative for this full year; do not treat its smaller sample as proof of superiority. The checklist can be evaluated as an entry filter for a separately defined setup without forcing an immediate exit on every filter failure. That would be a different backtest and may produce different results.

**Interpretation:** visually cleaner conditions are not automatically better entry locations. This particular interpretation is very restrictive and its illustrative trade edge does not survive modest hypothetical costs. Do not promote it to an automatic execution rule from this result alone.

## Included artifacts

- `equity.html`: interactive equity and drawdown chart, two-point round-trip scenario.
- `tearsheet.html`: OpenStatz daily return dashboard for the main spot proxy, with Nifty reference.
- `summary.png`: compact results chart.
- CSVs for trades, bar-by-bar gates, coverage, forward study, matched controls and monthly results.
- Reproducible script, package lock, audit and independent verification.
'''
(P/'report.md').write_text(text)
# Self-contained report HTML: embedded figure plus readable preformatted Markdown.
img=base64.b64encode((P/'summary.png').read_bytes()).decode()
try:
 import markdown
 body=markdown.markdown(text,extensions=['tables','fenced_code'])
except ImportError:
 body='<pre>'+html.escape(text)+'</pre>'
page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Nifty anti-chop backtest</title><style>body{max-width:1120px;margin:40px auto;padding:0 24px;background:#f5f7fb;color:#20334e;font:16px/1.6 system-ui}h1,h2{line-height:1.25}h2{margin-top:36px}table{border-collapse:collapse;font-size:13px;display:block;overflow:auto;background:white;width:100%}th,td{padding:10px 12px;text-align:left;border-bottom:1px solid #dbe2ec;white-space:normal}th{background:#e6edf5}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.7 ui-monospace,monospace}img{width:100%;height:auto}code{overflow-wrap:anywhere}a{color:#245e98}</style><main><img alt="Anti-chop study results and filter coverage" src="data:image/png;base64,'''+img+'"><p><a href="equity.html">Interactive equity chart</a> · <a href="tearsheet.html">Daily return dashboard</a></p>'+body+'</main></html>'
(P/'report.html').write_text(page)
if (P/'tearsheet.html').exists() and (P/'tearsheet_error.txt').exists():(P/'tearsheet_error.txt').unlink()
print(json.dumps({'report':str(P/'report.html'),'main':main.to_dict(),'coverage':cov.to_dict('records')},indent=2))
