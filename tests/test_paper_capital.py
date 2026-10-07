import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from sector_heatmap.paper_wallet import wallet,reserve,release,capital
from sector_heatmap.delta_currency import policy,SOURCE
from strategies.ema_crossover.paper_capital import balance,preflight

class WalletTests(unittest.TestCase):
    def test_shared_paper_bypasses_live_funds_but_live_keeps_broker_preflight(self):
        from strategies.ema_crossover.runner import Runner
        r=object.__new__(Runner)
        calls=[]
        r.adapter=SimpleNamespace(preflight=lambda order,c:calls.append(c['mode']) or 'LIVE_CHECK',delta=SimpleNamespace(_inr_conversion=lambda:dict(rate=85)))
        for broker in ('FYERS','DELTA_INDIA'):
            r.state=dict(config=dict(mode='PAPER',broker=broker,paper_capital_inr=100000),order_history=[],realized_pnl=0)
            r.entry_preflight(dict(qty=100),dict(quantity_multiplier=.001),dict(bid=99,ask=100))
        self.assertEqual(calls,[])
        r.state['config']['mode']='LIVE'
        self.assertEqual(r.entry_preflight({}, {}, {}),'LIVE_CHECK');self.assertEqual(calls,['LIVE'])

    def test_delta_paper_activation_uses_public_data_without_wallet_authentication(self):
        from strategies.renko_supertrend.delta_broker import Broker
        b=object.__new__(Broker)
        b.session_policy=lambda c:None
        b.route_availability=lambda c:dict(available=True)
        b.subscribe=lambda *a:None;b.warm_options=lambda c:None
        def forbidden(*a):raise AssertionError('Paper must not access live account')
        b.execution=SimpleNamespace(authenticate=forbidden)
        b.positions=forbidden;b.orders=forbidden
        result=b.validate_config(dict(mode='PAPER',underlying='BTCUSD',timeframe='1 minute'))
        self.assertEqual(result['account_identity'],'PAPER-PUBLIC-DELTA-INDIA')

    def test_commitment_realized_and_fees(self):
        w=reserve(wallet(10000),1000)
        self.assertEqual(w['available_inr'],8995)
        w=release(w,1100,100)
        self.assertEqual(w['available_inr'],10089.5)
        with self.assertRaisesRegex(ValueError,'quantity unchanged'):reserve(w,20000)

    def test_invalid_capital(self):
        for value in (True,None,0,-1,float('nan'),float('inf'),1e10):
            with self.assertRaises(ValueError):capital(value)

    def test_quantity_multiplier_across_cash_index_mcx_and_delta(self):
        for broker,rate,multiplier,qty,ask in [('FYERS',1,1,20,100),('FYERS',1,1,65,100),('FYERS',1,100,1,100),('DELTA_INDIA',85,.001,100,100)]:
            state=dict(config=dict(mode='PAPER',broker=broker,paper_capital_inr=100000),realized_pnl=0,order_history=[])
            funds=preflight(state,dict(qty=qty),dict(quantity_multiplier=multiplier),dict(bid=ask*.99,ask=ask),rate)
            self.assertEqual(funds['available_inr'],100000)
            state['config']['paper_capital_inr']=1
            with self.assertRaisesRegex(ValueError,'Virtual Paper capital insufficient'):preflight(state,dict(qty=qty),dict(quantity_multiplier=multiplier),dict(bid=ask*.99,ask=ask),rate)

    def test_partial_pending_reserved_once_and_prior_run_fees_excluded(self):
        state=dict(config=dict(mode='PAPER',broker='DELTA_INDIA',paper_capital_inr=100000),run_id='new',realized_pnl=5,
                   position=dict(quantity=4,entry_price=100,quantity_multiplier=.001),
                   pending=dict(order=dict(side=1),position=dict(quantity=10,entry_price=100,entry_side=1,quantity_multiplier=.001)),
                   order_history=[dict(mode='PAPER',run_id='old',filled=100,average_price=100,quantity_multiplier=.001),dict(mode='PAPER',run_id='new',filled=4,average_price=100,quantity_multiplier=.001)])
        f=balance(state,85)
        self.assertEqual(f['reserved_inr'],85)
        self.assertAlmostEqual(f['fee_provision_inr'],.4*.035*1.18*85)
        self.assertAlmostEqual(f['available_inr'],100000+425-85-f['fee_provision_inr'])

    def test_live_and_invalid_quotes_refused(self):
        state=dict(config=dict(mode='LIVE'))
        with self.assertRaisesRegex(ValueError,'Paper only'):preflight(state,{}, {}, {})
        state['config']['mode']='PAPER'
        for q in ({},{'bid':100,'ask':90},{'bid':90,'ask':100},{'bid':float('nan'),'ask':100}):
            with self.assertRaisesRegex(ValueError,'quote'):preflight(state,{}, {}, q)

class ConversionTests(unittest.TestCase):
    def test_verified_cache_stale_refresh_and_failure(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'policy.json';calls=[]
            def fetch(url,timeout):
                calls.append(url)
                return SimpleNamespace(url=SOURCE,text='USD-INR rate on the platform is fixed at 85, i.e. 1 USD = 85 INR',raise_for_status=lambda:None)
            self.assertEqual(policy(p,100000,fetch)['rate'],85)
            self.assertEqual(policy(p,100001,fetch)['rate'],85);self.assertEqual(len(calls),1)
            def bad(*a,**k):return SimpleNamespace(url=SOURCE,text='Unsupported changed policy',raise_for_status=lambda:None)
            self.assertIsNone(policy(p,200000,bad))
            self.assertIsNone(policy(p,200001,fetch));self.assertEqual(len(calls),1)
            self.assertEqual(policy(p,201000,fetch)['verified_at'],201000)

    def test_wrong_source_and_mismatched_rate_fail(self):
        for url,text in [('https://example.com','USD-INR rate on the platform is fixed at 85, i.e. 1 USD = 85 INR'),(SOURCE,'USD-INR rate on the platform is fixed at 85, i.e. 1 USD = 86 INR')]:
            with tempfile.TemporaryDirectory() as d:
                self.assertIsNone(policy(Path(d)/'p',100000,lambda *a,**k:SimpleNamespace(url=url,text=text,raise_for_status=lambda:None)))
