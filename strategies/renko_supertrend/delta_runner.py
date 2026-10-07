"""Shared Renko rules with explicit Delta policy and native accounting labels."""
from .runner import Runner
from .adoption import AdoptedRunner
from .delta_contracts import configuration
from . import preferences


class DeltaRunner(Runner):
    configure = staticmethod(configuration)
    runtime_revision = 'renko-delta-paper-capital-v4'

    def read_preferences(self):
        return preferences.read(self.path.with_name('renko-delta-settings.json'))

    def save_preferences(self, payload):
        return preferences.write(self.path.with_name('renko-delta-settings.json'),payload,self.clock())

    def deadline(self):
        c=self.state.get('config') or {}
        if c.get('carry_policy') != 'CONTINUOUS':
            super().deadline()  # Preserve explicitly saved daily risk policies.
        # Perpetual signal candles are continuous, but execution remains dated
        # ATM options. Protect the exact held contract, never a blanket 17:30.
        pending=self.state.get('pending') or {}
        p=self.state.get('position') or (pending.get('position') if pending and self.is_entry_order(pending['order'],pending['position']) else None)
        if self.state.get('running') and p:
            expiry=p.get('expiry_epoch')
            if expiry is not None and self.clock() >= expiry-60 and not p.get('exit_requested'):
                p.update(exit_requested=True,exit_reason='CONTRACT_EXPIRY',contract_expiry_at=expiry)
                self.save()

    def submit(self, order, position, reason):
        self.adapter.signal_symbol=self.state['config']['underlying']
        self.adapter.execution_reason=reason
        if order['side']==1:
            position={**position,**self.adapter.contract(order['symbol'])}
        return super().submit(order,position,reason)

    def record_order(self, pending, status, filled=0, price=None):
        super().record_order(pending,status,filled,price)
        row=next(r for r in self.state['order_history'] if r['tag']==pending['tag'])
        meta=self.adapter.contract(row['symbol'])
        row.update(broker='DELTA_INDIA',quote_currency=meta['quote_currency'],settlement_currency=meta['settlement_currency'],product_id=meta['product_id'])
        owned=self.adapter.delta.live['orders'].get(pending['tag']) or {}
        row['native_commission']=owned.get('commission') if self.state['config']['mode']=='LIVE' else None
        row['requested_type']='LIMIT_IOC' if self.state['config']['mode']=='LIVE' else 'PAPER_EXECUTABLE_QUOTE'
        row['native_order_terms']='MARKETABLE_LIMIT_IOC' if self.state['config']['mode']=='LIVE' else 'SIMULATED_EXECUTABLE_QUOTE'
        if filled and row.get('native_commission') is None and not row.get('native_fee_policy'):
            try:
                quote=self.adapter.delta.ticker(self.state['config']['underlying'])
                product=self.adapter.delta.product(row['symbol'])
                if not 0<=self.clock()-quote['exchange_at']<=15:raise ValueError('Stale index observation.')
                row['native_fee_policy']=dict(taker_rate=product['taker_commission_rate'],index_price=quote['spot_price'],exchange_at=quote['exchange_at'],observed_at=self.clock(),basis='Index observed at local fill confirmation; fee estimate, not exact exchange fill-time index.')
            except (AttributeError,KeyError,TypeError,ValueError):row['native_fee_error']='Native commission/rate/index evidence unavailable.'

    def snapshot(self):
        result=super().snapshot()
        currency=(result.get('position') or {}).get('quote_currency')
        if not currency:
            cfg=result.get('config') or {}
            if cfg.get('underlying'):
                try: currency=self.adapter.delta.product(cfg['underlying'])['quoting_currency']
                except Exception: pass
        result.update(broker='DELTA_INDIA',pnl_currency=currency,inr_conversion=self.adapter.delta._inr_conversion() if hasattr(self.adapter.delta,'_inr_conversion') else None,
                      order_terms='MARKETABLE_LIMIT_IOC',price_source='PERPETUAL_LAST_TRADE')
        from .delta_costs import MODEL
        current=[t for t in result['trade_history'] if t.get('run_id')==self.state.get('run_id') and t.get('entry_filled')]
        realized=sum(t['costs']['realized_net'] for t in current) if all(t['costs'].get('realized_net') is not None for t in current) else None
        result['cost_pnl']=dict(realized_net=realized,unrealized_net=None,total_net=None,
            model=MODEL,basis='Delta native commission/product-rate estimates plus estimated GST; open liquidation costs unavailable. No FYERS charges or INR conversion applied.')
        result['sideways_status']['loss_basis']='AFTER_VERIFIED_NATIVE_COSTS'
        for trade in result.get('trade_history',[]): trade['quote_currency']=currency
        if isinstance(result.get('message'),str):
            result['message']=result['message'].replace('FYERS','Delta India').replace('as MARKET (Delta India MPP)','as a marketable IOC limit')
        return result


class DeltaAdoptedRunner(AdoptedRunner,DeltaRunner):
    """Run adoption's exposure checks before the unchanged shared Renko exits."""
    pass
