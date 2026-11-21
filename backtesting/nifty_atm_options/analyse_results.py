"""Summarise the frozen development-selected grid; never tune on validation."""
import argparse,collections,datetime,json,random
from pathlib import Path
from zoneinfo import ZoneInfo

def analyse(folder):
 folder=Path(folder);data=json.loads((folder/'results.json').read_text());rows=data['results'];by_id={r['id']:r for r in rows};valid=[r for r in rows if r['valid']]
 selected=[by_id[i] for i in data['selected_on_development']]
 summary=dict(configurations=len(rows),valid=len(valid),invalid=len(rows)-len(valid),missing_contract_keys=data['missing_contract_keys'],positive_development=sum(r['metrics']['development']['net']>0 for r in valid),positive_both=sum(all(r['metrics'][k]['net']>0 for k in ('development','validation')) for r in valid),selected=selected,baseline=by_id['00-000'])
 summary['exploratory_both_periods']=[r for r in valid if all(r['metrics'][k]['trades']>=20 and r['metrics'][k]['very_stress_net']>0 for k in ('development','validation'))]
 # Paired ablations hold every other parameter fixed; invalid pairs are excluded.
 pairs={};lookup={(tuple(r['entry_bits']),tuple(sorted(r['risk'].items()))):r for r in valid}
 for flag in ('proximity','rsi_mtf','contraction','zones','trailing','sideways'):
  deltas=[]
  for r in valid:
   if r['risk'][flag]:continue
   risk=dict(r['risk'],**{flag:True});other=lookup.get((tuple(r['entry_bits']),tuple(sorted(risk.items()))))
   if other:deltas.append({k:other['metrics'][k]['net']-r['metrics'][k]['net'] for k in ('development','validation')})
  pairs[flag]={k:dict(pairs=len(deltas),mean_net_change=sum(d[k] for d in deltas)/len(deltas) if deltas else None,improved_pairs=sum(d[k]>0 for d in deltas)) for k in ('development','validation')}
 summary['paired_ablations']=pairs
 for index,label in enumerate(data['grid']['entry_grid']):
  deltas=[]
  for r in valid:
   bits=list(r['entry_bits'])
   if bits[index]:continue
   bits[index]=True;other=lookup.get((tuple(bits),tuple(sorted(r['risk'].items()))))
   if other:deltas.append({k:other['metrics'][k]['net']-r['metrics'][k]['net'] for k in ('development','validation')})
  pairs[label]={k:dict(pairs=len(deltas),mean_net_change=sum(d[k] for d in deltas)/len(deltas) if deltas else None,improved_pairs=sum(d[k]>0 for d in deltas)) for k in ('development','validation')}
 summary['primary_exit_groups']={exit:{period:dict(configurations=len(group),mean_net=sum(r['metrics'][period]['net'] for r in group)/len(group),positive=sum(r['metrics'][period]['net']>0 for r in group)) for period in ('development','validation')} for exit in ('ST','EMA10','EMA30') if (group:=[r for r in valid if r['risk']['exit']==exit])}
 journals=json.loads((folder/'journals.json').read_text());breakdowns={};uncertainty={};rng=random.Random(20261015)
 for journal in journals:
  groups=collections.defaultdict(lambda:dict(trades=0,net=0,wins=0))
  for period,trades in journal.get('trades',{}).items():
   for trade in trades:
    month=datetime.datetime.fromtimestamp(trade['entry_at'],ZoneInfo('Asia/Kolkata')).strftime('%Y-%m')
    for key in (period+'/'+month,period+'/'+trade['side']):
     g=groups[key];g['trades']+=1;g['net']+=trade['net'];g['wins']+=trade['net']>0
  breakdowns[journal['id']]=dict(groups)
  uncertainty[journal['id']]={}
  for period,trades in journal.get('trades',{}).items():
   daily={day:0. for day in data['periods'][period]}
   for t in trades:daily[datetime.datetime.fromtimestamp(t['entry_at'],ZoneInfo('Asia/Kolkata')).date().isoformat()]+=t['net']
   values=list(daily.values());samples=sorted(sum(rng.choices(values,k=len(values))) for _ in range(2000))
   uncertainty[journal['id']][period]=dict(daily_resample_net_95pct=[samples[50],samples[1949]],net_without_best_trade=sum(t['net'] for t in trades)-max((t['net'] for t in trades),default=0),method='2000 independent day-block resamples including zero-trade days; descriptive only, not corrected for selection or serial regimes')
 summary['journal_breakdowns']=breakdowns
 summary['uncertainty']=uncertainty
 (folder/'analysis.json').write_text(json.dumps(summary,indent=2))
 print(json.dumps({k:v for k,v in summary.items() if k in ('configurations','valid','invalid','positive_development','positive_both')}))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--folder',default='backtesting/nifty_atm_options/full-grid');a=p.parse_args();analyse(a.folder)
