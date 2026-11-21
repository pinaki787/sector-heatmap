"""Read-only account-scoped restart preflight; never submits orders."""
import json,os,time
from pathlib import Path
from sector_heatmap.fyers_execution import _current_client
from sector_heatmap.fyers_history import account_read
def audit():
 client=_current_client()
 positions=account_read(client,'positions');orders=account_read(client,'orderbook')
 if positions.get('s')!='ok' or orders.get('s')!='ok':raise ValueError('Fresh broker positions and orders are required.')
 contract='MCX:CRUDEOILM26NOV9650CE'
 held=[{k:r.get(k) for k in ('symbol','netQty','productType')} for r in positions.get('netPositions',[]) if r.get('symbol')==contract and float(r.get('netQty',0))]
 pending=[{k:r.get(k) for k in ('symbol','id','status','qty','filledQty')} for r in orders.get('orderBook',[]) if r.get('symbol')==contract and r.get('status') not in (1,2,5,7)]
 return {'checked_at':time.time(),'contract':contract,'open_positions':held,'pending_orders':pending,'total_open_positions':sum(bool(r.get('netQty')) for r in positions.get('netPositions',[]))}
if __name__=='__main__':print(json.dumps(audit()))
