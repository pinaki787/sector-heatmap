"""Append explicitly exploratory journals without changing frozen selection."""
import datetime,gzip,json,pickle
from pathlib import Path
from replay import IST,load_quotes,simulate
folder=Path('backtesting/nifty_atm_options');output=folder/'full-grid';analysis=json.loads((output/'analysis.json').read_text());journals=json.loads((output/'journals.json').read_text());known={r['id'] for r in journals}
with gzip.open(folder/'common.pkl.gz','rb') as f:common=pickle.load(f)
days=set().union(*common['periods'].values());indexes=[i for i,r in enumerate(common['rows']) if datetime.datetime.fromtimestamp(r['timestamp'],IST).date().isoformat() in days];rows=[common['rows'][i] for i in indexes];quotes,_=load_quotes([folder/'cache'])
for r in analysis['exploratory_both_periods']:
 if r['id'] in known:continue
 with gzip.open(folder/f"signals-{int(r['id'].split('-')[0]):02d}.pkl.gz",'rb') as f:entry=pickle.load(f)
 journal=simulate(rows,[entry['signals'][i] for i in indexes],quotes,entry['config'],r['risk'],[common['zones'][i] for i in indexes],common['rsi_context'],common['periods'],True)
 assert journal['metrics']==r['metrics'] and journal['valid']==r['valid']
 journals.append(dict(id=r['id'],selection='EXPLORATORY_USING_BOTH_PERIODS',entry_bits=r['entry_bits'],risk=r['risk'],**journal))
(output/'journals.json').write_text(json.dumps(journals,indent=2));print('Journal configurations',len(journals))
