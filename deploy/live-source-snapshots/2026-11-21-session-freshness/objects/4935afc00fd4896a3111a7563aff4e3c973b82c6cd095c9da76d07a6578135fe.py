"""FYERS adapter used only by explicitly enabled future parser protection."""
import hashlib
from .fyers_execution import _current_client
from .parser_quote import fetch_parser_quote
from .config import load_config

class ParserProtectionBroker:
    def snapshot(self):
        c=_current_client();p=c.get_profile();orders=c.orderbook();positions=c.positions();gtt=c.gtt_orderbook()
        if any(not isinstance(x,dict) or x.get('s')!='ok' for x in [p,orders,positions,gtt]):
            raise ValueError('FYERS account/orders/positions/GTT reconciliation failed.')
        identity=(p.get('data') or {}).get('fy_id')
        if not identity:raise ValueError('FYERS account identity unavailable.')
        for data,key in [(orders,'orderBook'),(positions,'netPositions'),(gtt,'orderBook')]:
            if not isinstance(data.get(key),list):raise ValueError('Incomplete broker reconciliation payload.')
        for rows, required in [(orders['orderBook'], {'id','symbol','status','filledQty','qty','side','productType'}),
                               (positions['netPositions'], {'symbol','productType','netQty'})]:
            if any(not isinstance(row, dict) or not required.issubset(row) for row in rows):
                raise ValueError('Broker reconciliation fields missing; no mutation allowed.')
        return {'account':hashlib.sha256(identity.encode()).hexdigest(),'orders':orders['orderBook'],'positions':positions['netPositions'],'gtt':gtt['orderBook']}
    def fresh_price(self,symbol):
        quote=fetch_parser_quote(symbol,load_config().get('FYERS_ACCESS_TOKEN',''))
        if quote.get('freshness')!='FRESH':raise ValueError('Fresh FYERS price required before protection.')
        return quote['ltp']
    def place_entry(self,order):return _current_client().place_order(order)
    def place_oco(self,order):return _current_client().place_gtt_order(order)
