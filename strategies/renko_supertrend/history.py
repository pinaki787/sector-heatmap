"""Actual owned option-trade reporting; never turn signal rows into fills."""
import math
from strategies.ema_crossover.history import position_history
from .costs import ledger_costs,trade_costs

def trade_history(orders,position=None,unrealized=None,valuation=None):
    result=[]
    ledger=ledger_costs(orders)
    for trade in position_history(orders):
        rows=trade['orders'];entries=[r for r in rows if r.get('is_entry',r.get('side')=='BUY')];exits=[r for r in rows if not r.get('is_entry',r.get('side')=='BUY')]
        meta=next((r for r in entries if r.get('option_type')),rows[0])
        def spot(rs):
            observations=[o for r in rs for o in r.get('spot_fill_observations',[])]
            qty=sum(r.get('filled',0) or 0 for r in rs)
            known=sum(o['quantity'] for o in observations if isinstance(o.get('price'),(int,float)) and math.isfinite(o['price']))
            value=sum(o['quantity']*o['price'] for o in observations if isinstance(o.get('price'),(int,float)) and math.isfinite(o['price']))/known if qty and known==qty else None
            return value,observations
        entry_spot,entry_obs=spot(entries);exit_spot,exit_obs=spot(exits)
        paper=trade['mode']=='PAPER'
        remaining=trade['remaining_quantity']
        owns=position and position.get('lifecycle_id')==trade['lifecycle_id']
        def ids(rs):return [r['paper_order_id'] for r in rs if r.get('paper_order_id')] if paper else [r['order_id'] for r in rs if r.get('order_id')]
        result.append({**trade,'row_type':('PAPER ' if paper else 'LIVE ')+('CASH EQUITY TRADE' if meta.get('execution_route')=='CASH_EQUITY' else 'OPTION TRADE'), 'execution_route':meta.get('execution_route','OPTIONS'),
            'trade_id':('PAPER-TRADE-' if paper else 'LIVE-TRADE-')+trade['lifecycle_id'],'run_id':meta.get('run_id'),
            'underlying_symbol':meta.get('underlying_symbol'),'option_type':meta.get('option_type'),'strike':meta.get('strike'),'expiry_epoch':meta.get('expiry_epoch'),
            'entry_order_ids':ids(entries),'exit_order_ids':ids(exits),
            'spot_entry':entry_spot,'spot_exit':exit_spot,'spot_entry_observations':entry_obs,'spot_exit_observations':exit_obs,
            'spot_basis':'Quantity-weighted fresh underlying observations at local fill confirmation; exact exchange-fill spot unavailable.',
            'entry_time':min((r.get('first_fill_confirmed_at',r.get('filled_at')) for r in entries if r.get('filled')),default=None),
            'end_time':trade['exit_time'] if remaining==0 and trade['entry_filled'] else None,
            'unrealized_pnl':unrealized if owns and remaining else None,
            'pnl_basis':'Confirmed entry/exit fills × quantity × signed entry side × verified multiplier; executable ask for short / bid for long; before fees.',
            'quantity_multiplier':meta.get('quantity_multiplier'),'lot_size':meta.get('lot_size')})
        result[-1].update(journal_schema_version=1,entry_indicator_snapshot=next((r.get('indicator_snapshot') for r in entries if r.get('indicator_snapshot')),None),exit_indicator_snapshots=[r.get('indicator_snapshot') for r in exits],reconciliation_events=[{**e,'order_tag':r.get('tag')} for r in rows for e in r.get('reconciliation_events',[])],snapshot_provenance='Persisted strategy-event snapshots; older rows without snapshots remain unknown. Historical chart simulation is excluded.')
        result[-1].update(exposure_range=next((r.get('exposure_range') for r in reversed(rows) if r.get('exposure_range')),None),exposure_host_candles=next((r.get('exposure_host_candles') for r in reversed(rows) if r.get('exposure_host_candles') is not None),None),sideways_lock_trigger=next((r.get('sideways_lock_trigger') for r in reversed(rows) if r.get('sideways_lock_trigger')),None))
        snapshot=result[-1].get('entry_indicator_snapshot') or {}
        settings=snapshot.get('settings') or {}
        result[-1].update(entry_side=entries[0].get('side') if entries else None,configured_lots=settings.get('lots'),spot_target=settings.get('spot_target'),spot_stop=settings.get('spot_stop'),trailing_enabled=settings.get('trailing_enabled'),trailing_mode=settings.get('trailing_mode'),trailing_step=settings.get('trailing_step'),ema_exit_enabled=settings.get('ema_exit_enabled',True),ema_exit_length=settings.get('ema_exit_length',10),valuation=(valuation if owns and remaining else None))
        result[-1]['costs']=trade_costs(result[-1],ledger)
    return result
