"""Perpetual direction, collateral and recovery tests. No real broker calls."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from .delta_contracts import configuration, perpetual_contract, position, order_intent, owned_order
from .delta_broker import Broker
from .delta_execution import Execution
from .delta_runner import DeltaRunner
from .runner import Runner, configuration as fyers_configuration
from .test_delta_execution import FakeDelta
from .test_delta_contracts import NOW
from .test_delta_integration import config
from .test_runner import FakeBroker
from .test_signals import candle
from .trailing_stop import advance


def product():
    return dict(id=123006,symbol='PAXGUSD',contract_type='perpetual_futures',
                state='live',trading_status='operational',underlying='PAXG',
                contract_value='0.001',contract_unit_currency='PAXG',tick_size='0.1',
                quoting_currency='USD',settlement_currency='USD',notional_type='vanilla',
                is_quanto=False,initial_margin='1',maintenance_margin='0.5',
                taker_commission_rate='0.0001',product_specs={'only_reduce_only_orders_allowed':False})


class FuturesFake(FakeBroker):
    def __init__(self):
        super().__init__()
        self.delta=SimpleNamespace(live={'orders':{}},product=lambda s:product(),_inr_conversion=lambda:dict(rate=85))
        self.resolved_contracts={};self.bid=4100;self.ask=4101
    def contract(self,symbol):return perpetual_contract(product())
    def resolve(self,c,d):
        meta={**self.contract(c['underlying']),'entry_side':1 if d=='BULLISH' else -1}
        self.resolved_contracts[meta['symbol']]=meta;return meta
    def quote(self,s):return dict(bid=self.bid,ask=self.ask,exchange_at=self.now,received_at=self.now)
    def order(self,s,q,side,quote):return dict(symbol=s,qty=q,side=side,type=1,productType='DELTA_PERPETUAL')


class PerpetualBoundaryTests(unittest.TestCase):
    def setUp(self):self.quote=dict(bid=4100,ask=4101,exchange_at=NOW,received_at=NOW)
    def test_explicit_route_and_fyers_scope(self):
        cfg=config('PAXGUSD')
        self.assertEqual(configuration(cfg)['execution_route'],'OPTIONS')
        self.assertEqual(configuration({**cfg,'execution_route':'DELTA_PERPETUAL'})['collateral_policy'],'FULL_NOTIONAL')
        for route in ('FUTURES','CASH_EQUITY',''):
            with self.assertRaises(ValueError):configuration({**cfg,'execution_route':route})
        with self.assertRaises(ValueError):fyers_configuration({**cfg,'underlying':'NSE:TEST','execution_route':'DELTA_PERPETUAL'})
        with self.assertRaises(ValueError):configuration({**cfg,'execution_route':'DELTA_PERPETUAL','sideways_enabled':True})
    def test_exact_paxg_route_without_options_and_signed_units(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Broker(SimpleNamespace(clock=lambda:NOW,product=lambda s:product(),catalog=lambda:dict(instruments=[product()])),Path(tmp))
            self.assertFalse(b.route_availability(config('PAXGUSD'))['available'])
            cfg={**config('PAXGUSD'),'execution_route':'DELTA_PERPETUAL'}
            self.assertTrue(b.route_availability(cfg)['available'])
            self.assertEqual(b.resolve(cfg,'BEARISH')['entry_side'],-1)
        row=position(dict(product_id=123006,product_symbol='PAXGUSD',size=-100,entry_price=4100),product(),NOW)
        self.assertEqual((row['netQty'],row['side'],row['quantity_multiplier']),(-100,-1,.001))
    def test_invalid_units_margin_permissions_and_status_fail_closed(self):
        for change in [dict(contract_value=0),dict(initial_margin=None),dict(maintenance_margin=2),dict(is_quanto=True),dict(settlement_currency='INR'),dict(contract_type='futures'),dict(trading_status='disrupted_post_only'),dict(product_specs={'only_reduce_only_orders_allowed':True})]:
            with self.subTest(change=change),self.assertRaises(ValueError):perpetual_contract({**product(),**change})
    def test_short_entry_and_buy_exit_have_explicit_reduce_intent(self):
        for side,reduce in [(-1,False),(1,False),(1,True),(-1,True)]:
            intent=order_intent('PAXGUSD',100,side,self.quote,product(),NOW,reduce_only=reduce)
            self.assertIs(intent['reduce_only'],reduce)
            self.assertEqual(intent['side'],'buy' if side==1 else 'sell')
        with self.assertRaises(ValueError):order_intent('PAXGUSD',100,-1,self.quote,product(),NOW)
    def test_short_entry_external_ownership_and_unknown_ack(self):
        d=FakeDelta();d.product=lambda s:product();d.size=-100
        d.pages=[dict(result=[dict(asset_symbol='USD',available_balance='1000')]),dict(result=[],meta={})]
        with self.assertRaises(ValueError):Execution(d).submit('PAXGUSD',100,-1,self.quote,'ECfutures123','PAXGUSD','ENTRY',reduce_only=False)
        self.assertFalse(any(isinstance(x,tuple) and x[0]=='submit' for x in d.calls))
        d.size=0;d.pages=[dict(result=[dict(asset_symbol='USD',available_balance='1000')]),dict(result=[],meta={})]
        intent=Execution(d).submit('PAXGUSD',100,-1,self.quote,'ECfutures123','PAXGUSD','ENTRY',reduce_only=False)
        self.assertFalse(intent['reduce_only'])
        owned=dict(account_identity='account-a',symbol='PAXGUSD',product=product(),request_id='ECfutures123',client_order_id='native123',order_id=7,status='cancelled',filled_contracts=40,average_fill_price=4100,request=dict(product_id=123006,size=100,side='sell',reduce_only=False,order_type='limit_order',time_in_force='ioc',limit_price='4099.9'))
        row=owned_order(owned,'account-a')
        self.assertEqual((row['side'],row['filledQty'],row['productType']),(-1,40,'DELTA_PERPETUAL'))
        self.assertEqual(owned_order({**owned,'status':'UNKNOWN','filled_contracts':0,'average_fill_price':None},'account-a')['status'],6)
    def test_live_collateral_uses_exact_wallet_and_notional(self):
        with tempfile.TemporaryDirectory() as tmp:
            delta=SimpleNamespace(clock=lambda:NOW,product=lambda s:product(),_private=lambda *a,**k:dict(result=[dict(asset_symbol='USD',available_balance='10')]))
            b=Broker(delta,Path(tmp));b.authenticated_client=lambda:None;b.quote=lambda s:self.quote;b.orders=lambda:[];b.reconcile_position=lambda s,q:None
            order=b.order('PAXGUSD',100,-1,self.quote)
            with self.assertRaisesRegex(ValueError,'full premium/notional'):b.preflight(order,config())
            delta._private=lambda *a,**k:dict(result=[dict(asset_symbol='USD',available_balance='1000')])
            b.preflight(order,config())
            delta._private=lambda *a,**k:dict(result=[dict(asset_symbol='BTC',available_balance='1000')])
            with self.assertRaises(ValueError):b.preflight(order,config())


class PerpetualLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.b=FuturesFake();self.r=DeltaRunner(self.b,Path(self.tmp.name)/'state.json',lambda:self.b.now);self.addCleanup(self.r.release)
        self.c={**config('PAXGUSD'),'execution_route':'DELTA_PERPETUAL','carry_policy':'CONTINUOUS','ema_exit_enabled':True,'paper_capital_inr':100000,'lots':100}
        p=patch.object(Runner,'supertrend_agreement',return_value=dict(allowed=True,reason='fixture agrees'));p.start();self.addCleanup(p.stop)
    def arm(self,bearish=False):
        if bearish:
            for i,price in enumerate([120,110,100]):self.b.rows[i].update({k:v for k,v in candle(i,price).items() if k!='timestamp'})
        self.r.activate(dict(self.c,configuration_revision=self.r.runtime_revision),background=False)
        self.r.state['eligible_since']=self.b.now-10;self.r.step()
    def test_short_fill_signed_pnl_buy_exit_and_restart(self):
        self.arm(True);p=self.r.state['position'];self.assertIsNotNone(p,self.r.state['message'])
        self.assertEqual((p['entry_side'],p['symbol'],p['quantity'],p['entry_price']),(-1,'PAXGUSD',100,4100))
        self.assertTrue(self.r.state['order_history'][0]['is_entry'])
        self.assertEqual(self.r.state['order_history'][0]['side'],'SELL')
        self.b.ask=4001;self.b.bid=4000
        self.assertAlmostEqual(self.r.snapshot()['pnl']['unrealized'],9.9)
        self.assertAlmostEqual(self.r.paper_funds()['reserved_inr'],34850)
        self.assertIsNone(self.r.snapshot()['cost_pnl']['realized_net'])
        held=deepcopy(p);self.r.release();other=DeltaRunner(self.b,self.r.path,lambda:self.b.now);self.addCleanup(other.release)
        self.assertFalse(other.state['running']);self.assertEqual(other.state['position'],held)
        self.b.now+=60;self.b.rows.append({**candle(3,140),'timestamp':self.b.rows[-1]['timestamp']+60});self.r.step()
        self.assertIsNone(self.r.state['position']);self.assertAlmostEqual(self.r.state['realized_pnl'],9.9)
        self.assertEqual(self.r.state['order_history'][-1]['side'],'BUY')
        self.assertFalse(self.r.state['order_history'][-1]['is_entry'])
        self.assertEqual(self.r.snapshot()['trade_history'][0]['row_type'],'PAPER PERPETUAL FUTURES TRADE')
        self.assertEqual(self.b.sent,[])
    def test_long_fill_and_insufficient_paper_notional(self):
        self.arm();self.assertEqual(self.r.state['position']['entry_side'],1)
        self.assertEqual(self.r.state['position']['entry_price'],4101)
        self.assertAlmostEqual(self.r.paper_funds()['fee_provision_inr'],410.1*.0001*1.18*85)
    def test_low_paper_capital_blocks_without_quantity_reduction(self):
        self.c['paper_capital_inr']=1000
        with self.assertRaisesRegex(ValueError,'capital insufficient'):self.arm(True)
        self.assertIsNone(self.r.state['position']);self.assertEqual(self.b.sent,[])
    def test_short_percent_trailing_tracks_low_and_hits_rebound(self):
        c={**self.c,'trailing_enabled':True,'trailing_basis':'OPTION_PREMIUM_PERCENT','trailing_distance':10}
        state,hit=advance(None,c,'BEARISH',100,NOW,NOW,NOW,NOW-1)
        self.assertFalse(hit);self.assertEqual(state['stop'],110)
        state,hit=advance(state,c,'BEARISH',90,NOW+1,NOW+1,NOW+1,NOW-1)
        self.assertEqual(state['stop'],99)
        state,hit=advance(state,c,'BEARISH',100,NOW+2,NOW+2,NOW+2,NOW-1)
        self.assertTrue(hit)

    def test_live_partial_short_reconciles_signed_remainder_and_buy_reduction(self):
        self.c['mode']='LIVE';self.arm(True)
        entry=self.b.sent[0]
        self.assertEqual(entry['side'],-1);self.assertFalse(entry['reduce_only'])
        self.assertIsNone(self.r.state['position'])
        self.b.qty=-40
        self.b.book=[dict(id='O1',orderTag=entry['orderTag'],symbol='PAXGUSD',side=-1,qty=100,
                          productType='DELTA_PERPETUAL',status=1,filledQty=40,tradedPrice=4100)]
        self.r.reconcile()
        self.assertEqual(self.r.state['position']['quantity'],40)
        self.r.stop();self.r.step()
        exit=self.b.sent[-1]
        self.assertEqual((exit['side'],exit['qty'],exit['reduce_only']),(1,40,True))
        self.b.qty=-20
        self.b.book.append(dict(id='O2',orderTag=exit['orderTag'],symbol='PAXGUSD',side=1,qty=40,
                                productType='DELTA_PERPETUAL',status=1,filledQty=20,tradedPrice=4000))
        self.r.reconcile()
        self.assertEqual(self.r.state['position']['quantity'],20)
        self.assertAlmostEqual(self.r.state['realized_pnl'],2)
        self.assertTrue(self.r.state['position']['exit_requested'])

    def test_live_unknown_short_ack_is_not_replayed(self):
        self.c['mode']='LIVE';self.b.fail=True;self.arm(True)
        self.assertEqual(len(self.b.sent),1)
        self.assertIsNotNone(self.r.state['pending'])
        with self.assertRaisesRegex(ValueError,'uniquely reconciled'):self.r.step()
        self.assertEqual(len(self.b.sent),1)

    def test_active_product_cannot_be_changed_or_overridden_as_options(self):
        self.arm(True)
        with self.assertRaises(ValueError):self.r.activate({**self.c,'execution_route':'OPTIONS','configuration_revision':self.r.runtime_revision},background=False)
        with self.assertRaisesRegex(ValueError,'trade product differs'):self.r.override_entry({'execution_route':'OPTIONS'})

    def test_remaining_daily_notional_budget_blocks_entry(self):
        self.c['daily_budget']=400
        with self.assertRaises(ValueError):self.arm(True)
        self.assertIsNone(self.r.state['position']);self.assertEqual(self.b.sent,[])


if __name__=='__main__':unittest.main()
