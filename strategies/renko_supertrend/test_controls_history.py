import tempfile
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import unittest
from .runner import master_session_policy,after_cutoff
from .history import trade_history
from . import preferences,test_runner as fixtures
from .signals import project_lifecycle,ema_setup

class ControlTests(unittest.TestCase):
    setUp=fixtures.RenkoLifecycleTests.setUp
    def test_single_start_keeps_validation_and_blocks_second_click(self):
        payload={**self.c,'configuration_revision':self.r.runtime_revision}
        result=self.r.activate(payload,background=False)
        self.assertTrue(result['running']);self.assertEqual(result['config']['mode'],'PAPER')
        with self.assertRaisesRegex(ValueError,'already active'):self.r.activate(payload,background=False)
        self.assertEqual(self.b.sent,[])
        self.r.stop();self.assertFalse(self.r.state['running'])
    def test_live_gate_and_revision_cannot_be_bypassed(self):
        with self.assertRaisesRegex(ValueError,'revision'):self.r.activate(self.c,background=False)
        self.b.live_enabled=lambda:False
        with self.assertRaisesRegex(ValueError,'gate'):self.r.activate({**self.c,'mode':'LIVE','configuration_revision':self.r.runtime_revision},background=False)
        self.assertFalse(self.r.state['running'])
    def test_simultaneous_start_requests_have_one_owner(self):
        gate=threading.Barrier(2);results=[]
        def call():
            gate.wait()
            try:self.r.activate({**self.c,'configuration_revision':self.r.runtime_revision},background=False);results.append('started')
            except ValueError:results.append('blocked')
        ts=[threading.Thread(target=call) for _ in range(2)]
        for t in ts:t.start()
        for t in ts:t.join()
        self.assertCountEqual(results,['started','blocked'])

class PreferencesAndSessionTests(unittest.TestCase):
    def row(self,exchange,segment,session,symbol):
        r=['']*17;r[10]=exchange;r[11]=segment;r[6]=session;r[9]=symbol;return r
    def test_authoritative_exchange_segment_deadlines(self):
        for ex,seg,symbol,session,deadline in [('10','10','NSE:COMMODITYSTOCK-EQ','0915-1530','15:10'),('12','10','BSE:SENSEX-INDEX','0915-1530','15:10'),('11','20','MCX:CRUDEOIL-FUT','0900-2330','23:30')]:
            p=master_session_policy(self.row(ex,seg,session,symbol));self.assertEqual(p['session_deadline'],deadline)
            now=datetime(2026,10,6,15,15,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
            self.assertEqual(after_cutoff(now,p),ex!='11')
        self.assertEqual(master_session_policy(self.row('11','20','0900-2300','MCX:TEST'))['session_deadline'],'23:00')
        with self.assertRaises(ValueError):master_session_policy(self.row('10','10','0915-1530','MCX:FAKE'))
    def test_mcxeod_boundary_and_next_local_day(self):
        p={'session_deadline':'23:30'}
        def at(day,h,m,s=0):return datetime(2026,10,day,h,m,s,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
        self.assertFalse(after_cutoff(at(6,23,29,59),p));self.assertTrue(after_cutoff(at(6,23,30),p));self.assertFalse(after_cutoff(at(7,0,0),p))
    def test_preferences_roundtrip_false_manual_live_and_window(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'preferences.json';values={'symbol':'MCX:TEST','timeframe':'5 minutes','brick-mode':'Manual','manual-brick':'12.8','use-adx':False,'intrabar-entries':False,'widening-window':'4','mode':'LIVE','lots':'1','max-trades':'5','max-premium':'','daily-budget':'','chart-view':'host'}
            preferences.write(p,{'settings':values},123)
            self.assertEqual(preferences.read(p)['settings'],values)
            self.assertEqual(preferences.read(p)['saved_at'],123)
    def test_flat_state_rearms_after_exit_without_same_bar_flip(self):
        s={'ema_qualified':'BULLISH'}
        self.assertEqual(project_lifecycle(s,0,'BULLISH',None)['lifecycle_event'],'BUY')
        self.assertEqual(project_lifecycle(s,1,'BEARISH','BEARISH')['lifecycle_event'],'BUY EXIT')
        self.assertIsNone(s['ema_qualified'])
        self.assertEqual(project_lifecycle(s,2,'BEARISH',None)['lifecycle_event'],'SELL')
    def test_multiple_cycles_in_same_supertrend_regime(self):
        s={};events=[]
        for i,(entry,price) in enumerate([('BULLISH',110),(None,120),(None,99),('BULLISH',110),(None,99),('BULLISH',110)]):
            events.append(project_lifecycle(s,i,entry,None,60,price,100)['lifecycle_event'])
        self.assertEqual(events,['BUY',None,'BUY EXIT','BUY','BUY EXIT','BUY'])

class TradeHistoryTests(unittest.TestCase):
    def rows(self,mode='LIVE'):
        base=dict(symbol='NSE:TESTCE',mode=mode,strategy='Renko',lifecycle_id='owned-1',lot_size=10,quantity_multiplier=3,option_type='CE',strike=100,expiry_epoch=1800000000,run_id='RUN1',product='MARGIN',requested_type='MARKET')
        return [{**base,'tag':'a','order_id':'BROKER-ENTRY' if mode=='LIVE' else None,'paper_order_id':'PAPER-ORDER-a' if mode=='PAPER' else None,'side':'BUY','requested':20,'filled':20,'average_price':10,'filled_at':100,'first_fill_confirmed_at':99,'updated_at':100,'reason':'RENKO_EMA_ENTRY','spot_fill_observations':[dict(quantity=20,price=100,observed_at=100,exchange_at=99)]},
                {**base,'tag':'b','order_id':'BROKER-EXIT1' if mode=='LIVE' else None,'paper_order_id':'PAPER-ORDER-b' if mode=='PAPER' else None,'side':'SELL','requested':10,'filled':10,'average_price':14,'filled_at':110,'updated_at':110,'reason':'EMA10_INTRABAR_BREACH','spot_fill_observations':[dict(quantity=10,price=99,observed_at=110,exchange_at=109)]}]
    def test_partial_option_pnl_multiplier_and_spot_pairs(self):
        t=trade_history(self.rows(),{'lifecycle_id':'owned-1'},60)[0]
        self.assertEqual(t['realized_pnl'],120);self.assertEqual(t['unrealized_pnl'],60)
        self.assertEqual((t['spot_entry'],t['spot_exit']),(100,99));self.assertEqual(t['remaining_quantity'],10)
        self.assertIsNone(t['end_time']);self.assertEqual(t['entry_time'],99)
        self.assertEqual(t['entry_order_ids'],['BROKER-ENTRY'])
    def test_multiple_exit_ids_closed_end_and_unknown_spot(self):
        rows=self.rows();rows.append({**rows[-1],'tag':'c','order_id':'BROKER-EXIT2','average_price':8,'filled_at':120,'spot_fill_observations':[dict(quantity=10,price=None,observed_at=120)]})
        t=trade_history(rows)[0];self.assertEqual(t['realized_pnl'],60);self.assertEqual(t['end_time'],120)
        self.assertEqual(t['exit_order_ids'],['BROKER-EXIT1','BROKER-EXIT2']);self.assertIsNone(t['spot_exit'])
    def test_stable_paper_ids_never_fabricate_live_broker_ids(self):
        a=trade_history(self.rows('PAPER'))[0];b=trade_history(self.rows('PAPER'))[0]
        self.assertEqual(a['trade_id'],b['trade_id']);self.assertEqual(a['entry_order_ids'],['PAPER-ORDER-a'])
        rows=self.rows();rows[0]['order_id']=None
        self.assertEqual(trade_history(rows)[0]['entry_order_ids'],[])
    def test_accepted_unfilled_is_not_a_trade_fill_or_profit(self):
        rows=self.rows()[:1];rows[0].update(filled=0,average_price=None,spot_fill_observations=[])
        t=trade_history(rows)[0];self.assertEqual(t['status'],'UNFILLED');self.assertIsNone(t['entry_price']);self.assertIsNone(t['realized_pnl'])
