"""Explicit-owner broker GETs and bounded CE candle repeat audit; no mutation paths."""
import sys,json,time,hashlib,sqlite3
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from run import client,ok,atomic,IST
from live import Reads
from sector_heatmap.fyers_history import history
out=Path(__file__).parent/'evidence/readiness-provider';out.mkdir(exist_ok=True)
api_raw=client('bf46fc364b610a0dfd338419e133cb41');api=Reads(api_raw)
report=dict(checked_at=datetime.now(IST).isoformat(),orders_submitted=0)
try:
    positions=ok(api.positions())['netPositions'];orders=ok(api.orderbook())['orderBook']
    report['fyers']=dict(authentication='PASS',open_positions=[dict(symbol=r.get('symbol'),qty=r.get('netQty'),product=r.get('productType')) for r in positions if int(r.get('netQty',0))],pending_order_count=sum(r.get('status') in (1,4,6) for r in orders))
    report['ce_queries']=[]
    symbol='NSE:NIFTY26NOV25850CE';target=1795064520
    for name,dates in [('day-repeat-a',dict(date_format=1,range_from='2026-11-19',range_to='2026-11-19')),
                       ('epoch-1030-1035',dict(date_format=0,range_from='1795064400',range_to='1795064700')),
                       ('day-repeat-b',dict(date_format=1,range_from='2026-11-19',range_to='2026-11-19'))]:
        response=ok(history(api,dict(symbol=symbol,resolution='1',cont_flag=0,**dates)))
        atomic(out/(name+'.json'),response)
        rows=response.get('candles',[]);group={}
        for r in rows:group.setdefault(r[0],[]).append(r)
        conflicts=[stamp for stamp,values in group.items() if any(r[:5]!=values[0][:5] for r in values)]
        report['ce_queries'].append(dict(query=name,rows=len(rows),unique=len(group),ohlc_conflicts=conflicts,target_rows=group.get(target,[]),
             first=min(group) if group else None,last=max(group) if group else None))
finally:api_raw._sector_pulse_ipv4_session.close()
# Bind Delta credentials to its exact registry owner; bypass stateful object construction.
account='a6ef4c9bcecd21d54c4a07e2b9b137a7';folder=ROOT/'.private/dashboard-login/accounts'/account
creds=json.loads((folder/'credentials.json').read_text())
with sqlite3.connect((ROOT/'.private/dashboard-login/registry.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
    binding=db.execute('select broker,credential_identity from accounts where id=?',(account,)).fetchone()
assert binding[0]=='DELTA_INDIA' and hashlib.sha256(('DELTA_INDIA|'+creds['DELTA_INDIA_API_KEY']).encode()).hexdigest()==binding[1]
from sector_heatmap.delta_india import DeltaIndia,delta_request_session
delta=object.__new__(DeltaIndia);delta.requester=delta_request_session();delta.clock=time.time
try:
    positions=delta._private('GET','/v2/positions/margined',credentials=creds)['result']
    orders=delta._private('GET','/v2/orders',params={'state':'open'},credentials=creds)['result']
    report['delta']=dict(authentication='PASS',open_positions=[{k:r.get(k) for k in ('product_symbol','product_id','size')} for r in positions if float(r.get('size',0))!=0],
                         pending_order_count=len(orders),broker_account_scope=account)
finally:delta.requester.close()
atomic(out/'report.json',report);print(json.dumps(report,indent=2))
