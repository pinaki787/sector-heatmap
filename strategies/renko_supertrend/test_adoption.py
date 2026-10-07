import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from .adoption import Manager, identity
from .runner import Runner
from .test_runner import FakeBroker

class Broker(FakeBroker):
    def __init__(self,shared):
        super().__init__();self.shared=shared;self.now=time.time()
        for i,r in enumerate(self.rows):r['timestamp']=int(self.now)-185+i*60
    def positions(self):return self.shared['positions']
    def orders(self):return self.shared['orders']
    def contract(self,s):return dict(symbol=s,lot_size=20,tick_size=.05,quantity_multiplier=1)
    def underlying(self,s):return ['']*13+['NIFTY']+['']*3
    def rows(self,s):return [['']*9+[p['symbol']]+['']*3+['NIFTY','','100','CE'] for p in self.positions()]
    def authenticated_client(self):return self
    def reconcile_position(self,s,q):
        if sum(p['netQty'] for p in self.positions() if p['symbol']==s)!=q:raise ValueError('Mismatch')

# FakeBroker's candle rows are instance data, while the real broker rows() is master lookup.
class Adapter(Broker):
    def __init__(self,shared):
        super().__init__(shared);self.candle_rows=self.rows;del self.rows
    def candles(self,c):return self.candle_rows

class AdoptionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.shared=dict(positions=[dict(symbol='NSE:TESTCE',netQty=20,netAvg=10,productType='MARGIN',side=1)],orders=[])
        self.factory=lambda:Adapter(self.shared)
        self.m=Manager(Path(self.tmp.name),self.factory,self.factory(),lambda:'TEST')
        self.payload=dict(underlying='NSE:NIFTY50-INDEX',timeframe='1 minute',strategy='RENKO_SUPERTREND_V1',lots=1,max_trades=5,
            exit_policy='OPPOSITE_CONFIRMED_SIGNAL',configuration_revision=Runner.runtime_revision,reentry_enabled=False,
            atr_length=1,factor=.1,brick_mode='Manual',manual_brick=10,ema_exit_enabled=False)
        self.cutoff=patch('strategies.renko_supertrend.adoption.after_cutoff',return_value=False);self.cutoff.start();self.addCleanup(self.cutoff.stop)
        self.addCleanup(lambda:[r.release() for r in self.m.runners.values()])
    def apply(self):
        self.payload['selections']=[p['selection'] for p in self.m.inventory()['positions'] if p['eligible']]
        return self.m.apply(self.payload,background=False)
    def test_adoption_owns_filled_exposure_without_initial_order(self):
        result=self.apply();r=next(iter(self.m.runners.values()))
        self.assertEqual(r.state['position']['quantity'],20);self.assertEqual(r.state['position']['entry_price'],10)
        self.assertEqual(r.adapter.sent,[]);self.assertFalse(r.state['accepting_entries']);self.assertTrue(r.state['running'])
        self.assertEqual(r.state['position']['entry_origin'],'BROKER_POSITION_ADOPTION')
        self.assertFalse(r.state.get('order_history'))
        self.assertEqual(result['managers'][0]['status'],'POSITION_ADOPTED')
    def test_pending_remainder_blocks_even_with_positive_filled_position(self):
        self.shared['orders']=[dict(symbol='NSE:TESTCE',status=6,filledQty=20,qty=40)]
        with self.assertRaisesRegex(ValueError,'Pending'):self.apply()
        self.assertFalse(self.m.runners)
    def test_selection_invalidated_by_quantity_or_average_change(self):
        self.payload['selections']=[self.m.inventory()['positions'][0]['selection']]
        self.shared['positions'][0]['netAvg']=11
        with self.assertRaisesRegex(ValueError,'changed or closed'):self.m.apply(self.payload,False)
    def test_duplicate_claim_and_foreign_strategy_owner_block(self):
        self.apply()
        self.assertFalse(self.m.inventory()['positions'][0]['eligible'])
        with self.assertRaises(ValueError):self.m.apply(self.payload,False)
    def test_external_change_pauses_before_exit_or_new_entry(self):
        self.apply();r=next(iter(self.m.runners.values()));self.shared['positions'][0]['netQty']=10;r.step()
        self.assertFalse(r.state['running']);self.assertEqual(r.adapter.sent,[])
        self.assertEqual(r.state['position']['quantity'],20)
    def test_restart_preserves_claim_stopped_and_external_close_releases_explicitly(self):
        self.apply();r=next(iter(self.m.runners.values()));r.state['running']=False;r.save();r.release()
        recovered=Manager(Path(self.tmp.name),self.factory,self.factory(),lambda:'TEST')
        rr=next(iter(recovered.runners.values()));self.assertFalse(rr.state['running']);self.assertEqual(rr.state['position']['quantity'],20)
        self.shared['positions']=[]
        recovered.control(dict(id=next(iter(recovered.runners)),action='resume'),False)
        self.assertIsNone(rr.state['position']);self.assertFalse(rr.state['running']);self.assertEqual(rr.adapter.sent,[])
    def test_short_nonmargin_and_fractional_positions_not_adoptable(self):
        for changes in ({'netQty':-20},{'netQty':.5},{'productType':'INTRADAY'},{'netAvg':0}):
            with self.assertRaises(ValueError):identity({**self.shared['positions'][0],**changes})

    def test_existing_exit_sells_only_adopted_quantity_and_disables_reentry(self):
        self.apply();r=next(iter(self.m.runners.values()))
        r.state['position'].update(exit_requested=True,exit_reason='EMA10_CONFIRMED_BREACH')
        r.step();self.assertEqual(len(r.adapter.sent),1);order=r.adapter.sent[0]
        self.assertEqual(order['side'],-1);self.assertEqual(order['qty'],20)
        self.shared['positions']=[]
        self.shared['orders']=[dict(order,id='O1',status=2,filledQty=20,tradedPrice=12)]
        r.step();self.assertIsNone(r.state['position']);self.assertEqual(r.state['realized_pnl'],40)
        r.step();self.assertFalse(r.state['running']);self.assertEqual(len(r.adapter.sent),1)
    def test_multiple_positions_get_independent_managers_and_shared_entry_claims(self):
        self.shared['positions'].append(dict(symbol='NSE:SECONDCE',netQty=40,netAvg=15,productType='MARGIN',side=1))
        self.payload['reentry_enabled']=True;self.apply()
        self.assertEqual(len(self.m.runners),2);a,b=list(self.m.runners.values())
        self.assertTrue(a.state['accepting_entries']);self.assertTrue(b.state['accepting_entries'])
        with self.assertRaisesRegex(ValueError,'duplicate entry'):
            a.submit(dict(symbol='NSE:SECONDCE',side=1),{},'TEST')
        self.assertEqual(a.adapter.sent,[])
    def test_account_or_positions_failure_retains_claim_and_sends_no_order(self):
        self.apply();r=next(iter(self.m.runners.values()))
        def unavailable():raise ValueError('Unavailable')
        r.adapter.positions=unavailable;r.step()
        self.assertFalse(r.state['running']);self.assertEqual(r.state['position']['quantity'],20);self.assertEqual(r.adapter.sent,[])

    def test_saved_partial_exit_recovers_original_order_without_resubmission(self):
        self.apply();r=next(iter(self.m.runners.values()));r.state['position'].update(exit_requested=True,exit_reason='EMA10_CONFIRMED_BREACH');r.step()
        order=r.adapter.sent[0];self.shared['orders']=[dict(order,id='O1',status=6,filledQty=10,tradedPrice=12)]
        self.shared['positions'][0]['netQty']=10
        r.state['running']=False;r.save();r.release()
        recovered=Manager(Path(self.tmp.name),self.factory,self.factory(),lambda:'TEST')
        key=next(iter(recovered.runners));rr=recovered.runners[key];self.addCleanup(rr.release)
        recovered.control(dict(id=key,action='resume'),False);rr.step()
        self.assertEqual(rr.state['pending']['id'],'O1');self.assertEqual(rr.adapter.sent,[])
        self.shared['orders'][0]['status']=1;rr.step()
        self.assertIsNone(rr.state['pending']);self.assertEqual(rr.state['position']['quantity'],10)
        self.assertEqual(rr.state['realized_pnl'],20);self.assertEqual(rr.adapter.sent,[])

    def test_batch_initialization_failure_preserves_claims_without_starting_loops(self):
        self.shared['positions'].append(dict(symbol='NSE:SECONDCE',netQty=20,netAvg=15,productType='MARGIN',side=1))
        self.payload['selections']=[p['selection'] for p in self.m.inventory()['positions']]
        original=Adapter.start;calls=[]
        def fail_second(adapter):
            calls.append(adapter)
            if len(calls)==2:raise ValueError('Disconnected during initialization')
            return original(adapter)
        with patch.object(Adapter,'start',fail_second):
            with self.assertRaisesRegex(ValueError,'Disconnected'):self.m.apply(self.payload,True)
        self.assertEqual(len(self.m.runners),2)
        for r in self.m.runners.values():
            self.assertFalse(r.state['running']);self.assertIsNone(r.thread);self.assertEqual(r.adapter.sent,[])
            self.assertIsNotNone(r.state['position'])
    def test_master_underlying_mismatch_does_not_create_claim(self):
        self.payload['selections']=[p['selection'] for p in self.m.inventory()['positions']]
        with patch.object(Adapter,'underlying',return_value=['']*13+['OTHER']+['']*3):
            with self.assertRaisesRegex(ValueError,'selected underlying'):self.m.apply(self.payload,False)
        self.assertFalse(self.m.runners)

    def test_ownership_outage_preserves_inventory_but_disables_adoption(self):
        def unavailable():raise ValueError('Protective book unavailable')
        self.m.owners=unavailable
        d=self.m.inventory();self.assertEqual(len(d['positions']),1);self.assertFalse(d['positions'][0]['eligible'])
        self.assertIsNotNone(d['ownership_error'])
