"""Read-only native ATM analysis; no ticket, runner start or broker order."""
import argparse,json,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from sector_heatmap.workspaces import WorkspaceStore
from sector_heatmap.motilal_service import Service
from sector_heatmap.motilal_strategy_broker import Broker
from sector_heatmap.motilal_analysis import Handoff
from sector_heatmap.motilal_api import READS

def main():
    p=argparse.ArgumentParser();p.add_argument('--account',required=True);p.add_argument('--underlying',required=True);args=p.parse_args()
    store=WorkspaceStore(root/'.private/dashboard-login/registry.sqlite3')
    with store.db() as db:account=dict(db.execute('SELECT * FROM accounts WHERE id=? AND broker=?',(args.account,'MOTILAL_OSWAL')).fetchone() or {})
    if not account:raise ValueError('Native account unavailable.')
    service=Service(store.folder(account),account);service.ready();request=service.client.request
    def read_only(operation,payload=None):
        if operation not in READS:raise AssertionError('Diagnostic cannot submit an order.')
        return request(operation,payload)
    service.client.request=read_only;h=Handoff.__new__(Handoff);h.execution=service;h.adapter=Broker(service)
    h.adapter.subscribe(args.underlying);h.adapter.start()
    try:
        for direction in ('BULLISH','BEARISH'):
            deadline=time.monotonic()+20
            while True:
                try:
                    spot,_=h.quote(args.underlying)
                    result=h.options(args.underlying,direction,dict(invalidation=spot-20 if direction=='BULLISH' else spot+20,minimum_reward_to_risk=2))
                    if result['status']!='READY':raise ValueError(result.get('reason'))
                    break
                except ValueError:
                    if time.monotonic()>deadline:raise
                    time.sleep(.3)
            proposal=result['proposals'][0];leg=proposal['legs'][0]
            print(json.dumps(dict(direction=direction,status=result['status'],broker=result['broker'],expiry=result['expiry_iso'],strike=leg['strike'],option_type=leg['option_type'],action=leg['action'],leg_count=len(proposal['legs']),greeks_required=proposal['greeks_required'],greeks_available=all(v is not None for v in leg['greeks'].values()),open_interest=leg['open_interest'],volume=leg['volume'],orders_sent=0)),flush=True)
    finally:service.feed.stop()
if __name__=='__main__':main()
