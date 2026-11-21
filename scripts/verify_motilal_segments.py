"""Read-only exchange coverage audit; history staging never authorizes trading."""
import argparse,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from sector_heatmap.workspaces import WorkspaceStore
from sector_heatmap.motilal_service import Service
from sector_heatmap.motilal_strategy_broker import Broker
from sector_heatmap.motilal_history_seed import Seed
from sector_heatmap.motilal_api import READS

def main():
    p=argparse.ArgumentParser();p.add_argument('--motilal-account',required=True);p.add_argument('--fyers-account',required=True);args=p.parse_args()
    store=WorkspaceStore(root/'.private/dashboard-login/registry.sqlite3')
    with store.db() as db:a=dict(db.execute('SELECT * FROM accounts WHERE id=? AND broker=?',(args.motilal_account,'MOTILAL_OSWAL')).fetchone() or {})
    if not a:raise ValueError('Native account unavailable.')
    user=dict(id=a['user_id']);store.account(user,args.fyers_account)
    x=Service(store.folder(a),a);x.ready();request=x.client.request
    def read_only(operation,payload=None):
        if operation not in READS:raise AssertionError('Coverage audit cannot mutate broker orders.')
        return request(operation,payload)
    x.client.request=read_only;b=Broker(x);seed=Seed(store,user,a)
    cfg=dict(fyers_history_enabled=True,fyers_history_account_id=args.fyers_account)
    for symbol in ('NSE:NIFTY50-INDEX','NSE:NIFTYBANK-INDEX','BSE:SENSEX-INDEX','NSE:RELIANCE-EQ','BSE:RELIANCE-EQ','MCX:569901'):
        result=dict(underlying=symbol,orders_sent=0)
        try:
            meta=b.underlying(symbol);result.update(native_symbol=meta['symbol'],native_name=meta['name'])
            options=b.option_rows(symbol);result.update(native_options=len(options),option_exchanges=sorted({r['exchange'] for r in options}),paired_types=sorted({r['option_type'] for r in options}))
            rows=seed.candles(cfg,dict(meta,history_symbol=symbol),60,'09:00' if meta['exchange']=='MCX' else '09:15')
            result.update(history='PASS',usable_completed_minutes=len(rows),historical_evidence=seed.evidence[(args.fyers_account,meta['symbol'])],execution_preflight='NOT VERIFIED: cash/indices market closed; historical prices are not executable quotes')
        except Exception as e:result.update(error=str(e))
        print(json.dumps(result),flush=True)
if __name__=='__main__':main()
