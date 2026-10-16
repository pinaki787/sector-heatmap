import unittest
from unittest.mock import Mock
from .handoff import build_long_option_proposals
from .motilal_analysis import Handoff

class AtmOptionTests(unittest.TestCase):
    def setUp(self):
        self.expiry=dict(date='27-10-2026',expiry='1793100000')
        self.rows=[dict(option_type='',ltp=100)]+[dict(symbol='MO:NSEFO:'+kind,option_type=kind,strike_price=100,bid=10,ask=10.05,ltp=10,oi=1000,volume=100,greeks={}) for kind in ('CE','PE')]
        self.master={r['symbol']:dict(exchange_token=str(i+1),lot_size=10,tick_size=.05,expiry_epoch=self.expiry['expiry']) for i,r in enumerate(self.rows[1:])}
    def proposal(self,direction,**kwargs):
        return build_long_option_proposals(dict(data=dict(optionsChain=self.rows)),self.expiry,self.master,direction,dict(invalidation=95 if direction=='BULLISH' else 105,minimum_reward_to_risk=2),**kwargs)
    def test_native_bought_atm_call_and_put_do_not_require_greeks(self):
        for direction,kind in [('BULLISH','CE'),('BEARISH','PE')]:
            result=self.proposal(direction,require_greeks=False);self.assertEqual(result['status'],'READY')
            p=result['proposals'][0];self.assertFalse(p['greeks_required']);self.assertEqual(len(p['legs']),1)
            self.assertEqual((p['legs'][0]['action'],p['legs'][0]['option_type']),('BUY',kind))
            self.assertEqual(p['max_loss_per_lot'],100.5)
            self.assertTrue(all(v is None for v in p['legs'][0]['greeks'].values()))
    def test_default_other_broker_gate_still_requires_greeks(self):
        self.assertEqual(self.proposal('BULLISH')['status'],'UNAVAILABLE')
    def test_native_liquidity_and_contract_gates_remain_required(self):
        for field,value in [('oi',0),('volume',None),('bid',None),('ask',20)]:
            original=self.rows[1][field];self.rows[1][field]=value
            self.assertEqual(self.proposal('BULLISH',require_greeks=False)['status'],'UNAVAILABLE')
            self.rows[1][field]=original
    def test_missing_native_atm_quote_does_not_select_nearby_strike(self):
        h=Handoff.__new__(Handoff);h.adapter=Mock();h.quote=lambda symbol:(100,1000)
        h.adapter.clock.return_value=1000
        h.adapter.option_rows.return_value=[dict(symbol=f'MO:NSEFO:{strike}{kind}',expiry='2026-10-27',strike=strike,option_type=kind,token=strike,lot_size=10,tick_size=.05) for strike in (100,110) for kind in ('CE','PE')]
        def quote(symbol):
            if symbol.endswith('100CE'):raise ValueError('Missing exact ATM quote')
            return dict(bid=10,ask=10.05,ltp=10,open_interest=1000,cumulative_volume=100,ltp_exchange_at=1000,ltp_received_at=1000)
        h.adapter.quote.side_effect=quote
        chain,expiry,masters=h.chain('NSE:TEST-EQ','BULLISH')
        self.assertFalse(any('110' in r.get('symbol','') for r in chain['data']['optionsChain']))
        result=build_long_option_proposals(chain,expiry,masters,'BULLISH',dict(invalidation=95),require_greeks=False)
        self.assertEqual(result['status'],'UNAVAILABLE')

    def test_runner_uses_nearest_eligible_expiry_before_choosing_atm(self):
        from .motilal_strategy_broker import Broker
        broker=Broker.__new__(Broker);broker.clock=lambda:1000
        broker.live_price=lambda config,now:(105,1000)
        broker.subscribe=Mock();broker.contract=lambda symbol:dict(symbol=symbol)
        broker.option_rows=lambda symbol:[dict(symbol=f'MO:NSEFO:{expiry}{strike}{kind}',expiry=expiry,strike=strike,option_type=kind) for expiry in ('2026-10-20','2026-10-27') for strike in (100,110) for kind in ('CE','PE')]
        for direction,kind in [('BULLISH','CE'),('BEARISH','PE')]:
            row=broker.resolve(dict(underlying='NSE:TEST-EQ',execution_route='OPTIONS'),direction)
            self.assertEqual(row['symbol'],f'MO:NSEFO:2026-10-20100{kind}')
