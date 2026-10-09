"""Finite virtual Paper capital. Never reads live funds or submits orders."""
import math
from .valuation import amount

def balance(state,rate=1):
    c=state.get('config') or {}
    from sector_heatmap.paper_wallet import capital
    initial=capital(c.get('paper_capital_inr',100000))
    if not math.isfinite(rate) or rate<=0:raise ValueError('Verified INR settlement conversion required for virtual Paper capital.')
    fee_rate=.035*1.18 if c.get('broker')=='DELTA_INDIA' else .005
    fees=0
    for r in state.get('order_history',[]):
        if r.get('mode')!='PAPER' or not r.get('filled'):continue
        if state.get('run_id'):
            if r.get('run_id')!=state['run_id']:continue
        elif r.get('submitted_at',0)<state.get('started_at',0):continue
        # Conservative provision per filled side, including GST for Delta.
        # Virtual buying power is not represented as an actual broker invoice.
        row_rate=fee_rate
        if r.get('execution_route')=='DELTA_PERPETUAL':
            row_rate=float(r['taker_commission_rate'])*1.18
            if not math.isfinite(row_rate) or not 0<row_rate<1:raise ValueError('Verified perpetual fee provision required.')
        fees+=amount(r,r['filled'],r['average_price'])*row_rate
    held=state.get('position') or {}
    pending=state.get('pending') or {}
    reserved=amount(held,held['quantity'],held['entry_price']) if held else 0
    if pending and pending.get('order',{}).get('side')==pending.get('position',{}).get('entry_side',1):
        p=pending['position'];filled=held.get('quantity',0)
        reserved+=amount(p,max(0,p['quantity']-filled),p['entry_price'])
    if c.get('execution_route')=='DELTA_PERPETUAL':
        fee_rate=None  # Product rate is persisted per fill, not a generic option cap.
    realized=state.get('realized_pnl',0)
    if not all(isinstance(x,(int,float)) and math.isfinite(x) for x in (realized,fees,reserved)):raise ValueError('Verified virtual Paper ledger values required.')
    available=initial/rate+realized-fees-reserved
    return dict(initial_inr=initial,available_inr=available*rate,reserved_inr=reserved*rate,realized_gross_inr=realized*rate,fee_provision_inr=fees*rate,
                available_native=available,rate=rate,fee_rate=fee_rate,basis=('Perpetual: full notional reserved, product taker fees + estimated GST provisioned; funding and liquidation excluded. Broker leverage unchanged. Virtual capital per run; gross realized P&L included. No live broker balance.' if c.get('execution_route')=='DELTA_PERPETUAL' else 'Virtual capital per run; full premium/notional reserved, gross realized P&L included, conservative per-fill fee provision deducted. Delta provision: 3.5% premium cap + 18% GST; FYERS provision: 0.5% notional per filled side. No leverage or live broker balance.'))


def preflight(state,order,contract,quote,rate=1):
    if state.get('config',{}).get('mode')!='PAPER':raise ValueError('Virtual capital is Paper only.')
    bid,ask=quote.get('bid'),quote.get('ask')
    if not all(isinstance(x,(int,float)) and math.isfinite(x) and x>0 for x in (bid,ask)) or ask<bid or (ask-bid)/ask>.03:raise ValueError('Fresh executable Paper quote and spread within 3% required.')
    funds=balance(state,rate)
    commitment=amount(contract,order['qty'],ask)
    fee_rate=funds['fee_rate']
    if contract.get('execution_route')=='DELTA_PERPETUAL':
        fee_rate=float(contract['taker_commission_rate'])*1.18
        if not math.isfinite(fee_rate) or not 0<fee_rate<1:raise ValueError('Verified perpetual fee provision required.')
    needed=commitment*(1+fee_rate+.01)
    if needed>funds['available_native']:raise ValueError(f"Virtual Paper capital insufficient: required INR {needed*rate:.2f}, available INR {funds['available_inr']:.2f}. Requested quantity unchanged.")
    return funds
