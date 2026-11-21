"""Read-only public broker catalog audit; never updates account/order masters."""
import concurrent.futures,csv,io,json,hashlib,time,collections
from pathlib import Path
from urllib.request import Request,urlopen
from sector_heatmap.motilal_master import contract
folder=Path('.private/chart-order-rollouts/motilal-public-master-20261119')
account=Path('.private/dashboard-login/accounts/08823c4c2082f03de07634a51e39f9fb/motilal-master')
MAX_BYTES=64*1024*1024
def fetch(exchange):
 url='https://openapi.motilaloswal.com/getscripmastercsv?name='+exchange
 began=time.time()
 with urlopen(Request(url,headers={'User-Agent':'SectorPulse read-only catalog audit'}),timeout=20) as response:
  body=response.read(MAX_BYTES+1);status=response.status;mime=response.headers.get('Content-Type')
 if len(body)>MAX_BYTES:raise ValueError('Native master exceeds audit limit')
 (folder/(exchange+'.csv')).write_bytes(body)
 raw=list(csv.DictReader(io.StringIO(body.decode('utf-8-sig'))))
 if not raw or not {'scripcode','exchangename','instrumentname','ticksize'}.issubset(raw[0]):raise ValueError('Invalid native CSV schema')
 accepted=[];errors=collections.Counter()
 for row in raw:
  try:accepted.append(contract(row,exchange))
  except (ValueError,TypeError,KeyError) as e:errors[str(e)]+=1
 ids=[r['symbol'] for r in accepted]
 if len(ids)!=len(set(ids)):raise ValueError('Duplicate native identities')
 saved=json.loads((account/(exchange+'.json')).read_text());old={r['symbol'] for r in saved['rows']};new=set(ids)
 (folder/(exchange+'-normalized.json')).write_text(json.dumps(accepted,allow_nan=False))
 return {'exchange':exchange,'url':url,'status':status,'content_type':mime,'observed_at':time.time(),'elapsed_seconds':round(time.time()-began,2),'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body),'raw_rows':len(raw),'accepted_rows':len(accepted),'rejected_rows':sum(errors.values()),'rejection_reasons':dict(errors),'instrument_classes':dict(collections.Counter(r['instrument'] for r in accepted)),'previous_snapshot_at':saved['observed_at'],'added_since_cached':len(new-old),'removed_since_cached':len(old-new)}
results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 futures={pool.submit(fetch,e):e for e in ['NSE','BSE','NSEFO','BSEFO','NSECD','MCX','NCDEX']}
 for future in concurrent.futures.as_completed(futures):
  exchange=futures[future]
  try:result=future.result()
  except Exception as e:result={'exchange':exchange,'status':'ERROR','error':str(e)}
  results.append(result);print(json.dumps(result),flush=True)
report={'results':sorted(results,key=lambda r:r['exchange']),'scope':'Anonymous documented public broker CSV only. Account/order master, credentials, sessions, runners, and orders unchanged. Current native OHLC availability and account entitlements not established.'}
(folder/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
if any(r['status']!=200 for r in results):raise SystemExit(1)
