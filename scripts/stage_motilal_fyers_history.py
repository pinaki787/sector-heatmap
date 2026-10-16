"""Stage read-only FYERS candles for an exact Motilal underlying, without activation."""
import argparse,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from sector_heatmap.workspaces import WorkspaceStore
from sector_heatmap.motilal_service import Service
from sector_heatmap.motilal_strategy_broker import Broker
from sector_heatmap.motilal_history_seed import Seed

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--motilal-account',required=True);parser.add_argument('--fyers-account',required=True);parser.add_argument('--underlying',required=True);args=parser.parse_args()
    store=WorkspaceStore(root/'.private/dashboard-login/registry.sqlite3')
    with store.db() as db:
        account=dict(db.execute('SELECT * FROM accounts WHERE id=? AND broker=?',(args.motilal_account,'MOTILAL_OSWAL')).fetchone() or {})
    if not account:raise ValueError('Native account not found.')
    user=dict(id=account['user_id']);source=store.account(user,args.fyers_account)
    if source['broker']!='FYERS':raise ValueError('Select an owner-matched FYERS account.')
    service=Service(store.folder(account),account);service.ready();meta=Broker(service).underlying(args.underlying)
    seed=Seed(store,user,account);rows=seed.candles(dict(fyers_history_enabled=True,fyers_history_account_id=source['id']),dict(meta,history_symbol=args.underlying),60,'09:00' if meta['exchange']=='MCX' else '09:15')
    print(json.dumps(dict(source='FYERS_EXPLICIT_HISTORY',underlying=meta['name'],completed_minutes=len(rows),first=rows[0]['timestamp'] if rows else None,last=rows[-1]['timestamp'] if rows else None,orders_sent=0,runners_started=0)))
if __name__=='__main__':main()
