"""Render the audited grid summary as a reviewable Markdown artifact."""
import argparse,json
from pathlib import Path

def describe(r,grid):
 enabled=[name for name,on in zip(grid['entry_grid'],r['entry_bits']) if on]
 labels=dict(proximity='EMA10 proximity',rsi_mtf='30m RSI direction + slope',contraction='EMA10/30 contraction exit',zones='supply/demand exit',trailing='sampled 10% premium trail',sideways='quick-loss range lock')
 enabled += [labels[name] for name in labels if r['risk'][name]]
 return 'Supertrend; '+', '.join(enabled or ['no extra filters'])+'; '+r['risk']['exit']+' exit'

def render(folder):
 folder=Path(folder);data=json.loads((folder/'results.json').read_text());a=json.loads((folder/'analysis.json').read_text());selected=a['selected'];grid=data['grid'];lines=['# NIFTY ATM call/put option backtest','',f"Compared {a['configurations']:,} bounded configurations: {a['valid']:,} have complete replay paths; {a['invalid']:,} are excluded, never scored as zero-profit trades.",'']
 passing=[r for r in selected if r['metrics']['validation']['net']>0 and r['metrics']['validation']['stress_net']>0]
 if not passing:lines += ['**Recommendation: do not deploy a new setting from this search.** The development-selected shortlist did not retain positive validation net at the 0.2% per-side sensitivity. Increasing indicator count or choosing the highest historical win rate does not establish an edge.','']
 lines += [f"Of the 20 configurations selected using development net profit (minimum 30 development trades), {len(passing)} remained positive on validation at the 0.2% per-side cost sensitivity. This is a research screen, not evidence of executable live profitability.",'']
 for period,days in data['periods'].items():lines.append(f"- {period.title()}: {len(days)} sessions, {days[0]} through {days[-1]}.")
 lines += ['','## Development-selected configurations','', '| Rank | Rules | Development net ₹ | Validation net ₹ | Validation trades | Win rate | Expectancy ₹/trade | Drawdown ₹ | Net at 0.2%/side ₹ | Net at 0.5%/side ₹ |','|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
 for i,r in enumerate(selected,1):
  m=r['metrics']['validation'];lines.append(f"| {i} | {describe(r,grid)} | {r['metrics']['development']['net']:,.2f} | {m['net']:,.2f} | {m['trades']} | {100*(m['win_rate'] or 0):.1f}% | {(m['expectancy'] or 0):,.2f} | {m['max_drawdown']:,.2f} | {m['stress_net']:,.2f} | {m['very_stress_net']:,.2f} |")
 lines += ['','## Exploratory leads, selected after viewing both periods','','These are explicitly post-hoc candidates: at least 20 trades and positive net at 0.5% per-side sensitivity in each period. They were found using validation and therefore need new data before any profitability claim. Repeated rows can represent one identical trade path.','', '| Rules | Development trades / net ₹ | Validation trades / net ₹ | Validation 0.5% net ₹ | Validation drawdown ₹ |','|---|---:|---:|---:|---:|']
 for r in a['exploratory_both_periods']:
  d=r['metrics']['development'];v=r['metrics']['validation'];lines.append(f"| {describe(r,grid)} | {d['trades']} / {d['net']:,.2f} | {v['trades']} / {v['net']:,.2f} | {v['very_stress_net']:,.2f} | {v['max_drawdown']:,.2f} |")
 lines += ['','## Supertrend-only baseline','']
 b=a['baseline'];lines.append(f"Baseline coverage: {'complete' if b['valid'] else 'INCOMPLETE — metrics are not a full-sample comparison'}.")
 for period,m in b['metrics'].items():lines.append(f"- {period}: {m['trades']} trades; net ₹{m['net']:,.2f}; expectancy ₹{(m['expectancy'] or 0):,.2f}; win rate {100*(m['win_rate'] or 0):.1f}%; sampled maximum drawdown ₹{m['max_drawdown']:,.2f}.")
 lines += ['','## Paired filter comparisons','','Each pair changes only the named switch. These overlapping grid results are descriptive, not independent trials or a causal forecast. A gain can simply mean fewer losing trades; inspect activity as well.','', '| Switch | Complete pairs | Mean development net change ₹ | Mean validation net change ₹ | Validation pairs improved |','|---|---:|---:|---:|---:|']
 for name,p in a['paired_ablations'].items():
  d=p['development'];v=p['validation'];lines.append(f"| {name} | {v['pairs']} | {(d['mean_net_change'] or 0):,.2f} | {(v['mean_net_change'] or 0):,.2f} | {v['improved_pairs']} |")
 lines += ['','## Monthly and call/put consistency','','These journals cover the baseline, first five development-selected configurations and explicitly exploratory candidates. Identical trades across different switch combinations do not constitute independent confirmations.']
 for identifier,groups in a['journal_breakdowns'].items():
  lines += ['',f'### Configuration {identifier}','','| Period / month or side | Trades | Net ₹ | Win rate |','|---|---:|---:|---:|']
  for key,g in sorted(groups.items()):lines.append(f"| {key} | {g['trades']} | {g['net']:,.2f} | {100*g['wins']/g['trades']:.1f}% |")
  for period,u in a['uncertainty'][identifier].items():
   low,high=u['daily_resample_net_95pct'];lines.append(f"\n{period.title()} descriptive daily-bootstrap 95% net interval: ₹{low:,.2f} to ₹{high:,.2f}. Net after removing the single best trade: ₹{u['net_without_best_trade']:,.2f}.")
 lines += ['','The bootstrap uses 2,000 independent day-block resamples, including zero-trade sessions. It does not adjust for searching many configurations or serial market regimes and is not a predictive probability of profit.']
 lines += ['','## Method and limits','',
 'Bullish underlying signals buy ATM calls; bearish signals buy ATM puts. Both are long-premium trades. The nearest 50-point strike is chosen from the entry-time underlying open and held fixed until exit. Missing held-contract prices invalidate the configuration; there is no rolling-ATM replacement or fabricated price.',
 '', 'The host is five minutes, Supertrend ATR length 5 and multiplier 3 with the captured Auto-brick configuration. The bounded grid varies 64 entry combinations, four proximity/30-minute RSI combinations, and 48 exit/risk combinations. It tests the named switches, not every possible numeric period, threshold, host timeframe or strategy. Higher Supertrend confirmation is 15 minutes; RSI confirmation is completed 30-minute RSI14 above/below 50 with matching slope. Incomplete higher candles are excluded.',
 '', 'Entries and confirmed exits fill at the next contiguous five-minute option open with 0.05% adverse slippage per side. Entry liquidity uses preceding completed option volume. One 65-unit lot, ₹100,000 starting capital, one position at a time, maximum two entries per session, and mandatory 15:15 exit; no overnight holding. Entry conditions never constitute proof that a real order would fill.',
 '', 'Fee estimates use the frozen FYERS NSE-options cost helper: ₹20 per order plus exchange, clearing, STT, GST, stamp, SEBI and IPFT charges. Dhan supplies history; this does not use a Dhan contract note. The 0.2% and 0.5% sensitivities add cost to the same trades, without rerunning capital, range-lock or trailing decisions under those costs.',
 '', 'Trailing is a 10% option-premium trail observed only at five-minute opens. Quick-loss protection freezes the sampled underlying range after a losing trade of at most two host candles; it is not a predictive consolidation detector. These approximations cannot validate tick-level stop execution. Supply/demand uses prior confirmed zones. Drawdown uses five-minute closing option marks, not executable bid/ask or intrabar extremes.',
 '', 'Dhan rolling history provides relative strikes and weekly expiry ordinal, not an absolute historical contract symbol or expiry date. Expected expiry is inferred from the official NSE Tuesday/holiday calendar and held constant within a trade. No overnight holding reduces, but does not eliminate, the contract-identification limitation. Documented ATM ±10 availability can prevent pricing a fixed strike after a large move.',
 '', 'Chronological selection uses only the earlier 82 sessions. The later 42 sessions were already examined in earlier underlying-only research, so they are not a globally untouched holdout. Searching 12,288 correlated configurations creates selection risk. Positive configurations found by looking at validation are exploratory and must not be promoted as independently selected winners.',
 '', 'Historical candles lack bid/ask spreads, queue position and real fills. Results are estimated option P/L, not guaranteed returns. No production runner, broker setting or order was changed.',
 '', '## Data quality','', '```json',json.dumps(data['quality'],indent=2),'```','',f"Unresolved fixed-contract keys: {len(data['missing_contract_keys'])}. See `results.json` for exact missing timestamps and affected paths.",
 '', '## Sources','',
 '- [Dhan expired-option history and supported strike band](https://dhanhq.co/docs/v2/expired-options-data/)',
 '- [FYERS charges](https://fyers.in/charges-list)',
 '- [NSE NIFTY contract specifications](https://www.nseindia.com/static/products-services/equity-derivatives-nifty50)',
 '- [NSE 2026 F&O holidays](https://nsearchives.nseindia.com/content/circulars/FAOP71777.pdf)',
 '- [NSE lot-size circular](https://nsearchives.nseindia.com/content/circulars/FAOP70616.pdf)', '']
 (folder/'report.md').write_text('\n'.join(lines));print(folder/'report.md')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--folder',default='backtesting/nifty_atm_options/full-grid');a=p.parse_args();render(a.folder)
