"""Read-only selected-account leverage and size-tier margin preflight."""
from decimal import Decimal,InvalidOperation

def number(v,positive=True):
 try:n=Decimal(str(v))
 except (InvalidOperation,TypeError,ValueError):raise ValueError('Delta margin metadata unavailable') from None
 if not n.is_finite() or (n<=0 if positive else n<0):raise ValueError('Delta margin metadata unavailable')
 return n

def requirement(delta,product,size,quote):
 pid=product['id'];symbol=product['symbol']
 if isinstance(size,bool) or not isinstance(size,int) or size<1 or quote.get('symbol')!=symbol:raise ValueError('Exact Delta margin scope required')
 if not -2<=delta.clock()-quote.get('exchange_at',0)<=15:raise ValueError('Fresh Delta margin quote required')
 if product.get('contract_type')!='perpetual_futures' or product.get('quoting_currency')!=product.get('settlement_currency'):raise ValueError('Verified linear same-currency margin required')
 price=max(number(quote.get('bid')),number(quote.get('ask')))
 notional=number(size)*number(product.get('contract_value'))*price
 threshold=number(product.get('max_leverage_notional'));slope=number(product.get('initial_margin_scaling_factor'),False)
 base=number(product.get('initial_margin'))/100
 tier=base+slope*max(Decimal(0),notional-threshold)/100
 if size>number(product.get('position_size_limit')) or notional>number(product.get('position_notional_limit')):raise ValueError('Delta position size tier exceeded')
 reply=delta._private('GET','/v2/products/'+str(pid)+'/orders/leverage')
 row=reply.get('result')
 if not isinstance(row,dict) or row.get('product_id')!=pid:raise ValueError('Configured Delta leverage scope unavailable')
 leverage=number(row.get('leverage'))
 # Configured leverage governs; never set leverage or assume the maximum is active.
 fraction=max(1/leverage,tier)
 if fraction>1:raise ValueError('Delta margin tier exceeds supported collateral range')
 initial=notional*fraction
 fees=notional*number(product.get('taker_commission_rate'),False)*2*Decimal('1.18')
 reserve=notional*Decimal('.01') # Existing 1% notional reserve, unchanged.
 return dict(policy='BROKER_CONFIGURED_MARGIN',symbol=symbol,product_id=pid,contracts=size,currency=product['settlement_currency'],
   leverage=str(leverage),max_tier_leverage=str(1/tier),notional=str(notional),initial_margin=str(initial),fees_gst=str(fees),reserve=str(reserve),required=str(initial+fees+reserve),checked_at=delta.clock())
