"""Read-only native ATM resolution and preflight. Never submits an order."""
import argparse,json,sys,time
from decimal import Decimal,ROUND_CEILING
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from sector_heatmap.workspaces import WorkspaceStore
from sector_heatmap.motilal_service import Service
from sector_heatmap.motilal_strategy_broker import Broker
from sector_heatmap.motilal_api import READS
from sector_heatmap.motilal_analysis import native_liquidity

def main():
    p=argparse.ArgumentParser();p.add_argument('--account',required=True);p.add_argument('--underlying',required=True);args=p.parse_args()
    store=WorkspaceStore(root/'.private/dashboard-login/registry.sqlite3')
    with store.db() as db:account=dict(db.execute('SELECT * FROM accounts WHERE id=? AND broker=?',(args.account,'MOTILAL_OSWAL')).fetchone() or {})
    if not account:raise ValueError('Native account unavailable.')
    service=Service(store.folder(account),account);service.ready();request=service.client.request
    def read_only(operation,payload=None):
        if operation not in READS:raise AssertionError('Diagnostic cannot mutate broker orders.')
        return request(operation,payload)
    service.client.request=read_only;broker=Broker(service);config=dict(underlying=args.underlying,execution_route='OPTIONS')
    broker.subscribe(args.underlying);broker.start()
    try:
        deadline=time.monotonic()+15
        while True:
            try:price,stamp=broker.live_price(config,time.time());break
            except ValueError:
                if time.monotonic()>deadline:raise
                time.sleep(.2)
        for direction in ('BULLISH','BEARISH'):
            contract=broker.resolve(config,direction);deadline=time.monotonic()+15
            while True:
                try:quote=broker.quote(contract['symbol']);break
                except ValueError:
                    if time.monotonic()>deadline:raise
                    time.sleep(.2)
            limit=(Decimal(str(quote['ask']))/Decimal(str(contract['tick_size']))).to_integral_value(rounding=ROUND_CEILING)*Decimal(str(contract['tick_size']))
            checked=service.tickets.validate(dict(broker='MOTILAL_OSWAL',account_id=account['id'],mode='LIVE',symbol=contract['symbol'],side='BUY',product='NORMAL',lots=1,limit_price=str(limit),max_notional=str(limit*contract['lot_size']),duration='IOC'))
            print(json.dumps(dict(direction=direction,underlying_price=price,contract=contract['name'],native_parent_token=contract.get('underlying_token'),native_option_token=contract['token'],units=checked['units'],lots=checked['body']['quantityinlot'],bid=quote['bid'],ask=quote['ask'],native_liquidity=native_liquidity(quote,time.time()),validation='PASS',orders_sent=0)),flush=True)
    finally:service.feed.stop()
if __name__=='__main__':main()
