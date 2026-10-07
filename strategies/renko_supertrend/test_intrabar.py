from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo
import unittest
from .runner import provisional,analysis,ema_adverse,ema_exit_observation,after_cutoff,configuration
from . import test_runner as fixtures
FakeBroker=fixtures.FakeBroker
from .test_signals import candle

class TickBroker(FakeBroker):
    def __init__(self):
        super().__init__();self.price=130.;self.cancelled=[]
    def forming(self,c,rows,now):
        opening=int(now)//60*60
        return dict(timestamp=opening,open=120.,high=max(120.,self.price),low=min(120.,self.price),close=self.price,is_forming=True,stream_exchange_at=now)
    def live_price(self,c,now):return self.price,now
    def cancel(self,id):self.cancelled.append(id)

class IntrabarLifecycleTests(unittest.TestCase):
    setUp=fixtures.RenkoLifecycleTests.setUp
    start=fixtures.RenkoLifecycleTests.start
    append=fixtures.RenkoLifecycleTests.append
    # Reuse base lifecycle cases with their original adapter, then add opt-in tick cases.
    def tick_mode(self):
        self.b=TickBroker();self.r.adapter=self.b;self.c['intrabar_entries']=True
    def test_provisional_clone_repeated_ticks_and_stale_tick(self):
        self.tick_mode();c=configuration(self.c);a=analysis(self.b.rows,c,.05);before=deepcopy(a)
        forming=self.b.forming(c,self.b.rows,self.b.now)
        first=provisional(a,forming,c,.05,self.b.now)
        self.assertEqual(first,provisional(a,forming,c,.05,self.b.now))
        self.assertEqual(a,before);self.assertEqual(first['entry_direction'],'BULLISH')
        with self.assertRaisesRegex(ValueError,'Fresh'):provisional(a,{**forming,'stream_exchange_at':self.b.now-16},c,.05,self.b.now)
    def test_intrabar_entry_call_route_duplicate_tick_and_ema_exit(self):
        self.tick_mode();self.start();self.r.step();self.assertEqual(self.r.state['position']['symbol'],'NSE:TESTCE')
        self.r.step();self.assertEqual(len(self.r.state['order_history']),1)
        self.b.price=80;self.r.step();self.assertIsNone(self.r.state['position'])
        self.assertEqual(self.r.state['order_history'][-1]['reason'],'EMA10_INTRABAR_BREACH')
        self.b.price=130;self.r.step();self.assertIsNone(self.r.state['position'])
        self.assertEqual(len(self.r.state['order_history']),2);self.assertEqual(self.b.sent,[])
    def test_bearish_routes_long_put_not_short_option(self):
        self.tick_mode();self.b.rows=[{**candle(i,p),'timestamp':self.b.now-185+i*60} for i,p in enumerate([130,120,110])];self.b.price=100
        self.start();self.r.step();self.assertEqual(self.r.state['position']['symbol'],'NSE:TESTPE')
        self.assertEqual(self.r.state['order_history'][0]['side'],'BUY')
    def test_adverse_breach_symmetry_equality_and_adx_independence(self):
        for allowed in (True,False):
            self.assertTrue(ema_adverse(dict(close=99,ema10=100,signal_allowed=allowed),'BULLISH'))
            self.assertTrue(ema_adverse(dict(close=101,ema10=100,signal_allowed=allowed),'BEARISH'))
        self.assertFalse(ema_adverse(dict(close=100,ema10=100),'BULLISH'))
        self.assertFalse(ema_adverse(dict(close=101,ema10=100),'BULLISH'))
        self.assertFalse(ema_adverse(dict(close=99,ema10=100),'BEARISH'))
    def test_wall_clock_deadline_without_market_signal_and_cutoff(self):
        self.start();self.r.step()
        self.b.now=datetime(2026,10,6,15,10,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
        self.b.candles=lambda c:(_ for _ in ()).throw(AssertionError('Timed exit must not wait for host tick/candle'))
        self.r.step();self.assertIsNone(self.r.state['position'])
        self.assertEqual(self.r.state['order_history'][-1]['reason'],'TIMED_SQUARE_OFF_1510')
        self.assertFalse(self.r.state['accepting_entries']);self.assertFalse(after_cutoff(self.b.now-1));self.assertTrue(after_cutoff(self.b.now))
    def test_pending_partial_entry_cancel_then_exit_only_owned_fill(self):
        self.tick_mode();self.c['mode']='LIVE';self.start();self.r.step();p=self.r.state['pending']
        self.b.book=[dict(p['order'],id=p['id'],status=6,filledQty=7,tradedPrice=10)]
        self.b.now=datetime(2026,10,6,15,10,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
        self.r.step();self.assertEqual(self.b.cancelled,[p['id']]);self.assertEqual(len(self.b.sent),1)
        self.b.book[0]['status']=1;self.b.qty=7;self.r.step();self.assertEqual(self.r.state['position']['quantity'],7)
        self.r.step();self.assertEqual(self.b.sent[-1]['side'],-1);self.assertEqual(self.b.sent[-1]['qty'],7)
        self.assertEqual(self.r.state['pending']['reason'],'TIMED_SQUARE_OFF_1510')
        with self.assertRaisesRegex(ValueError,'uniquely reconciled'):self.r.step()
        self.assertEqual(len(self.b.sent),2)
    def test_submit_rechecks_fresh_regime_and_alignment(self):
        self.tick_mode();self.start()
        def changed(c,d):
            result=FakeBroker.resolve(self.b,c,d);self.b.price=80;return result
        self.b.resolve=changed
        with self.assertRaisesRegex(ValueError,'setup changed'):self.r.step()
        self.assertIsNone(self.r.state['pending']);self.assertEqual(self.b.sent,[])
    def test_ema_exit_uses_underlying_price_and_cloned_confirmed_ema(self):
        self.tick_mode();c=configuration(self.c);a=analysis(self.b.rows,c,.05);before=deepcopy(a)
        s=ema_exit_observation(a,80,self.b.now,c,self.b.now)
        self.assertAlmostEqual(s['ema10'],2/11*80+9/11*a['state']['ema10']);self.assertEqual(a,before)

    def test_overdue_owned_position_drains_next_local_day_without_tick(self):
        self.start();self.r.step();self.b.now+=86400
        self.b.candles=lambda c:(_ for _ in ()).throw(AssertionError('Overdue exit must not wait for tick'))
        self.r.step();self.assertIsNone(self.r.state['position'])
        self.assertEqual(self.r.state['order_history'][-1]['reason'],'TIMED_SQUARE_OFF_1510')

    def test_last_price_moves_after_forming_setup_no_entry_intent(self):
        self.tick_mode();self.start()
        self.b.live_price=lambda c,now:(80,now)
        with self.assertRaisesRegex(ValueError,'already breaches'):self.r.step()
        self.assertIsNone(self.r.state.get('position'))
        self.assertIsNone(self.r.state.get('pending'))
        self.assertEqual(self.r.state.get('order_history',[]),[])
        self.assertEqual(self.b.sent,[])

    def test_disabled_exit_does_not_add_exit_gate(self):
        self.tick_mode();self.c['ema_exit_enabled']=False;self.start()
        self.b.live_price=lambda c,now:(80,now)
        self.r.step();self.assertIsNotNone(self.r.state['position'])
        self.assertEqual(self.b.sent,[])

    def test_stale_pre_submission_tick_blocks_entry(self):
        self.tick_mode();self.start()
        self.b.live_price=lambda c,now:(130,now-16)
        with self.assertRaisesRegex(ValueError,'Fresh underlying'):self.r.step()
        self.assertIsNone(self.r.state.get('pending'))
        self.assertEqual(self.b.sent,[])

    def test_confirmed_entry_checks_current_exit_not_only_closed_signal(self):
        self.tick_mode();self.c['intrabar_entries']=False;self.start()
        self.b.live_price=lambda c,now:(80,now)
        with self.assertRaisesRegex(ValueError,'already breaches'):self.r.step()
        self.assertIsNone(self.r.state.get('pending'))
        self.assertEqual(self.b.sent,[])

    def test_custom_exit_ema_blocks_even_when_ema10_setup_passes(self):
        self.tick_mode();self.c['ema_exit_length']=30;self.start()
        self.r.exit_ema=lambda rows,c:200
        with self.assertRaisesRegex(ValueError,'already breaches'):self.r.step()
        self.assertIsNone(self.r.state.get('pending'))
        self.assertEqual(self.b.sent,[])

    def test_bearish_entry_blocks_adverse_last_price(self):
        self.tick_mode()
        self.b.rows=[{**candle(i,p),'timestamp':self.b.now-185+i*60} for i,p in enumerate([130,120,110])]
        self.b.price=100;self.start()
        self.b.live_price=lambda c,now:(150,now)
        with self.assertRaisesRegex(ValueError,'already breaches'):self.r.step()
        self.assertIsNone(self.r.state.get('pending'))
        self.assertEqual(self.b.sent,[])
