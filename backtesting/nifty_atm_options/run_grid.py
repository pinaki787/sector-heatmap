"""Checkpointed read-only parameter replay. Two research CPU workers at most."""
import os,argparse,concurrent.futures,gzip,pickle,itertools,json,datetime,multiprocessing,hashlib
from pathlib import Path
from replay import load_quotes,simulate,IST
STATE=None

def batch(n):
 folder,output,common,quotes,cache_key=STATE
 result_path=output/f'batch-{n:02d}.json'
 if result_path.exists():
  previous=json.loads(result_path.read_text())
  if previous.get('cache_key')==cache_key:return previous
 with gzip.open(folder/f'signals-{n:02d}.pkl.gz','rb') as f:entry=pickle.load(f)
 assert entry['cache_key']==json.loads((folder/'grid.json').read_text())['cache_key'],'Stale research indicator cache'
 indexes=common['indexes'];values=[entry['signals'][i] for i in indexes];rows=common['selected_rows'];zone_values=[common['zones'][i] for i in indexes];results=[]
 for proximity,rsi_mtf in itertools.product((False,True),repeat=2):
  for exit in ('ST','EMA10','EMA30'):
   for contraction,zones,trailing,sideways in itertools.product((False,True),repeat=4):
    risk=dict(proximity=proximity,rsi_mtf=rsi_mtf,exit=exit,contraction=contraction,zones=zones,trailing=trailing,sideways=sideways)
    r=simulate(rows,values,quotes,entry['config'],risk,zone_values,common['rsi_context'],common['periods'])
    results.append(dict(id=f'{n:02d}-{len(results):03d}',entry_bits=entry['bits'],risk=risk,**r))
 result=dict(cache_key=cache_key,entry=n,results=results);temp=result_path.with_suffix('.tmp');temp.write_text(json.dumps(result));temp.replace(result_path);return result

def main():
 global STATE
 os.nice(10)
 parser=argparse.ArgumentParser();parser.add_argument('--folder',default='backtesting/nifty_atm_options');parser.add_argument('--pilot',action='store_true');parser.add_argument('--workers',type=int,default=2);args=parser.parse_args();folder=Path(args.folder);grid=json.loads((folder/'grid.json').read_text())
 with gzip.open(folder/'common.pkl.gz','rb') as f:common=pickle.load(f)
 if args.pilot:common['periods']={'pilot':{'2026-10-08','2026-10-09'}}
 days=set().union(*common['periods'].values());indexes=[i for i,r in enumerate(common['rows']) if datetime.datetime.fromtimestamp(r['timestamp'],IST).date().isoformat() in days];common['indexes']=indexes;common['selected_rows']=[dict(common['rows'][i],_day=datetime.datetime.fromtimestamp(common['rows'][i]['timestamp'],IST).date().isoformat(),_minute=datetime.datetime.fromtimestamp(common['rows'][i]['timestamp'],IST).hour*60+datetime.datetime.fromtimestamp(common['rows'][i]['timestamp'],IST).minute) for i in indexes]
 quote_paths=[folder/'cache']
 if args.pilot:quote_paths=[folder/'cache',Path('backtesting/nifty_atm_option_review/pilot-cache')]
 quotes,quality=load_quotes(quote_paths);output=folder/('pilot-grid' if args.pilot else 'full-grid');output.mkdir(exist_ok=True)
 quote_digest=hashlib.sha256(json.dumps([(str(k),q) for k,q in sorted(quotes.items())],sort_keys=True).encode()).hexdigest();cache_key=hashlib.sha256((grid['cache_key']+quote_digest+''.join((folder/name).read_text() for name in ('replay.py','expiry_calendar.py','run_grid.py'))+str(args.pilot)).encode()).hexdigest();STATE=(folder,output,common,quotes,cache_key)
 batches=[]
 with concurrent.futures.ProcessPoolExecutor(max_workers=min(args.workers,2),mp_context=multiprocessing.get_context('fork')) as pool:
  for value in pool.map(batch,range(64)):
   batches.append(value);print('Completed entry batches',len(batches),'/64',flush=True)
 results=[r for b in batches for r in b['results']];first='pilot' if args.pilot else 'development';valid=[r for r in results if r['valid']];valid.sort(key=lambda r:r['metrics'][first]['net'],reverse=True)
 # Selection is frozen using the earlier period only.
 eligible=[r for r in valid if r['metrics'][first]['trades']>=(1 if args.pilot else 30)]
 selected=[r['id'] for r in eligible[:20]];(output/'selected-on-development.json').write_text(json.dumps(selected,indent=2))
 out=dict(cache_key=cache_key,quality=quality,grid=grid,results=results,selected_on_development=selected,periods={k:sorted(v) for k,v in common['periods'].items()},missing_contract_keys=sorted({(p['at'],p.get('side'),p.get('strike')) for r in results for p in r['problems'] if p['type'].startswith('MISSING_')}))
 (output/'results.json').write_text(json.dumps(out,indent=2));print(json.dumps(dict(configurations=len(results),valid=len(valid),missing_keys=len(out['missing_contract_keys']),quality=quality)))
 # Save reviewable journals/equity for selected candidates and the ST baseline.
 ids=set(selected[:5]);ids.add('00-000');journals=[]
 for r in results:
  if r['id'] not in ids:continue
  n=int(r['id'].split('-')[0])
  with gzip.open(folder/f'signals-{n:02d}.pkl.gz','rb') as f:entry=pickle.load(f)
  values=[entry['signals'][i] for i in indexes];zones=[common['zones'][i] for i in indexes]
  journal=simulate(common['selected_rows'],values,quotes,entry['config'],r['risk'],zones,common['rsi_context'],common['periods'],True);journals.append(dict(id=r['id'],entry_bits=r['entry_bits'],risk=r['risk'],**journal))
 (output/'journals.json').write_text(json.dumps(journals,indent=2))
if __name__=='__main__':main()
