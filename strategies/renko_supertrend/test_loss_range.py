import json,unittest
from copy import deepcopy
from . import loss_range as lr
from .runner import Runner,configuration
from . import test_runner as fixtures

def brick(opened,closed,at=101,**extra):
    return dict(open=opened,close=closed,timestamp=at,market_event_at=at,
                has_completed_brick=True,confirmation_basis='ORDERED_LIVE_PRICE',
                brick_direction='BULLISH' if closed>opened else 'BEARISH',
                cross_direction='BULLISH' if closed>opened else 'BEARISH',box=10,**extra)

class Rules(unittest.TestCase):
    def setUp(self):
        self.c=dict(strategy_basis='RENKO',renko_loss_range_enabled=True,renko_loss_range_buffer=0,underlying='BTCUSD')
        self.p=dict(opened_at=100,direction='BULLISH')
        lr.observe(self.p,brick(100,110,99),self.c,100,300,seed=True)
        lr.observe(self.p,brick(110,120,101),self.c,101,300)
        self.exit=brick(110,100,102)
        self.lock=lr.freeze(self.p,self.exit,self.c,-5,102.1,300,'run','trade')
    def test_range_counts_bricks_not_host_candles_and_duplicate_poll_is_inert(self):
        self.assertEqual((self.lock['low'],self.lock['high'],self.lock['brick_count']),(100,120,3))
        p=deepcopy(self.p);lr.observe(p,self.exit,self.c,103,300)
        self.assertEqual(p,self.p)
        lr.observe(p,brick(1,10,98),self.c,103,300);self.assertEqual(p,self.p)
    def test_inside_boundary_ticks_forming_old_wrong_direction_do_not_release(self):
        for s,d,now in [(brick(100,110,103),'BULLISH',103),
                         (brick(110,120,103),'BULLISH',103),
                         (brick(120,130,102),'BULLISH',103),
                         (brick(120,130,103,provisional=True),'BULLISH',103),
                         (brick(120,130,103),'BEARISH',103),
                         (brick(120,130,103),'BULLISH',119),
                         ({'close':140,'market_event_at':103},'BULLISH',103)]:
            self.assertIsNone(lr.breakout(self.lock,s,d,now,300),s)
    def test_both_direction_breakouts_strict_and_same_brick_can_enter(self):
        for s,d in [(brick(120,130,103),'BULLISH'),(brick(100,90,103),'BEARISH')]:
            result=lr.breakout(self.lock,s,d,103,300);self.assertIsNotNone(result)
        self.assertTrue(self.lock['active'])
    def test_frozen_buffer_uses_lock_box_even_after_auto_size_changes(self):
        lock={**self.lock,'buffer_bricks':1}
        self.assertIsNone(lr.breakout(lock,brick(120,130,103),'BULLISH',103,300))
        self.assertIsNotNone(lr.breakout(lock,{**brick(130,140,104),'box':100},'BULLISH',104,300))
    def test_profit_off_nonrenko_and_no_opposite_do_not_lock(self):
        for net in [0,5]:self.assertIsNone(lr.freeze(self.p,self.exit,self.c,net,103,300,'r','t'))
        for c in [{**self.c,'renko_loss_range_enabled':False},{**self.c,'strategy_basis':'CANDLESTICK'}]:
            self.assertIsNone(lr.freeze(self.p,self.exit,c,-1,103,300,'r','t'))
        p=dict(opened_at=100,direction='BULLISH');lr.observe(p,brick(100,110,101),self.c,101,300,seed=True)
        self.assertIsNone(lr.freeze(p,brick(110,120,102),self.c,-1,103,300,'r','t'))
    def test_unknown_net_is_explicit_conservative_protection(self):
        lock=lr.freeze(self.p,self.exit,self.c,None,103,300,'r','t')
        self.assertTrue(lock['active']);self.assertFalse(lock['loss_confirmed']);self.assertEqual(lock['reason'],'REVERSAL_NET_UNAVAILABLE')
    def test_seed_uses_only_entry_brick_and_later_bricks_are_observed(self):
        p=dict(opened_at=100,direction='BULLISH')
        signal={**brick(100,110,99),'brick_events':[brick(1000,990,98),brick(100,110,99)]}
        lr.observe(p,signal,self.c,100,300,seed=True)
        self.assertEqual((p['renko_brick_range']['count'],p['renko_brick_range']['high']),(1,110))
        self.assertFalse(p['renko_brick_range']['opposite'])
    def test_restore_and_malformed_input(self):
        self.assertIsNotNone(lr.breakout(json.loads(json.dumps(self.lock)),brick(120,130,103),'BULLISH',103,300))
        for value in [-1,6,1.2,True,'x',None]:
            with self.assertRaises(ValueError):lr.settings({'renko_loss_range_buffer':value})
        self.assertEqual(lr.settings({}),dict(renko_loss_range_enabled=True,renko_loss_range_buffer=0))

class PaperLifecycle(unittest.TestCase):
    def setUp(self):
        fixtures.RenkoLifecycleTests.setUp(self)
        self.c.update(ema_proximity_enabled=False,ema_momentum_enabled=False,higher_timeframe_enabled=False)
        self.b.live_price=lambda c,now:(self.b.rows[-1]['close'],now)
    start=fixtures.RenkoLifecycleTests.start
    def test_loss_exit_freezes_actual_bricks_and_exit_is_never_blocked(self):
        self.c.update(underlying='BSE:SENSEX-INDEX',ema_exit_enabled=False,higher_timeframe_enabled=False)
        self.b.resolve=lambda c,d:dict(symbol='BSE:SENSEX26O0872700CE',lot_size=20,tick_size=.05,quantity_multiplier=1)
        self.start();self.r.step()
        self.assertIsNotNone(self.r.state.get('position'))
        c=self.r.state['config'];c.update(strategy_basis='RENKO',renko_loss_range_enabled=True,renko_loss_range_buffer=0)
        p=self.r.state['position'];self.b.now+=1
        self.r.state['last_signal']=brick(100,110,self.b.now)
        lr.observe(p,self.r.state['last_signal'],c,self.b.now,60,seed=True)
        self.b.now+=1;self.r.state['last_signal']=brick(110,120,self.b.now);self.r.observe_renko_loss_range(self.r.state['last_signal'])
        self.b.now+=1;self.r.state['last_signal']=brick(110,100,self.b.now);self.r.observe_renko_loss_range(self.r.state['last_signal'])
        # An existing entry lock never blocks the protective SELL order.
        self.r.state['renko_loss_lock']={'active':True,'underlying':c['underlying'],'run_id':self.r.state.get('run_id'),'high':120,'low':100}
        self.b.quote=lambda symbol:dict(bid=8,ask=10)
        self.r.submit(self.b.order(p['symbol'],p['quantity'],-1,{}),p,'OPPOSITE_RENKO_BRICK_CLOSE')
        self.assertIsNone(self.r.state.get('position'))
        lock=self.r.state['renko_loss_lock']
        self.assertEqual((lock['low'],lock['high'],lock['brick_count']),(100,120,3));self.assertTrue(lock['loss_confirmed'])
        self.assertEqual(self.b.sent,[])
        restored=Runner(self.b,self.path,lambda:self.b.now);self.addCleanup(restored.release)
        self.assertEqual(restored.state['renko_loss_lock'],lock)
        self.b.now+=1;inside=brick(100,110,self.b.now)
        self.assertFalse(self.r.renko_loss_entry_gate(inside))
        self.assertTrue(self.r.state['renko_loss_lock']['active'])
        self.b.now+=1;outside=brick(120,130,self.b.now)
        eligibility=self.r.state['eligible_since']
        self.assertTrue(self.r.renko_loss_entry_gate(outside))
        self.assertEqual(self.r.state['eligible_since'],eligibility)
        self.assertFalse(self.r.state['renko_loss_lock']['active'])
    def test_unfilled_pending_entry_cannot_expand_exposure_range(self):
        self.r.state['config']={**self.c,'strategy_basis':'RENKO','renko_loss_range_enabled':True}
        pending_position=dict(direction='BULLISH',symbol='TEST',opened_at=self.b.now-1)
        self.r.state['pending']=dict(order={'side':1},position=pending_position)
        self.r.is_entry_order=lambda *args:True
        self.r.observe_renko_loss_range(brick(100,110,self.b.now))
        self.assertNotIn('renko_brick_range',pending_position)
    def test_scoped_preferences_preserve_toggle_buffer_and_reject_invalid_values(self):
        from . import preferences
        path=self.path.with_name('preferences.json')
        values={'symbol':self.c['underlying'],'renko-loss-range-enabled':False,'renko-loss-range-buffer':2}
        preferences.write(path,{'settings':values},self.b.now,scope={'broker':'FYERS','instrument':self.c['underlying']})
        self.assertEqual(preferences.read(path)['settings'],values)
        for change in [{'renko-loss-range-enabled':'false'},{'renko-loss-range-buffer':-1}]:
            with self.assertRaises(ValueError):preferences.write(path,{'settings':{**values,**change}},self.b.now)
        self.assertEqual(preferences.read(path)['settings'],values)
    def test_scope_mismatch_and_off(self):
        self.start();self.r.state['position']=None
        self.r.state['config'].update(strategy_basis='RENKO',renko_loss_range_enabled=True)
        self.r.state['renko_loss_lock']=dict(active=True,underlying='ETHUSD',run_id=self.r.state.get('run_id'))
        self.assertFalse(self.r.renko_loss_entry_gate(brick(120,130,self.b.now)))
        self.r.state['config']['renko_loss_range_enabled']=False
        self.assertTrue(self.r.renko_loss_entry_gate())

class ContinuationLock(unittest.TestCase):
    setUp=PaperLifecycle.setUp
    start=fixtures.RenkoLifecycleTests.start
    def scenario(self):
        self.c.update(ema_exit_enabled=False,higher_timeframe_enabled=False)
        self.start();self.r.signal();self.b.now+=2
        self.r.state['config'].update(strategy_basis='RENKO',trend_reentry_enabled=True)
        self.b.forming=lambda *args:None
        raw={**self.r.state['renko_engine']['last'],'timestamp':self.b.now-1,'market_event_at':self.b.now-1,
             'has_completed_brick':True,'confirmation_basis':'ORDERED_LIVE_PRICE','entry_qualified':False,
             'entry_diagnostic':'WAITING_SUPERTREND_REVERSAL','direction':'BULLISH','brick_direction':'BULLISH',
             'trend_reentry_direction':'BULLISH','entry_direction':None,'cross_direction':None}
        from .trend_reentry import apply
        sig=apply(self.r.state,raw)
        self.r.state['renko_engine']['last']=raw
        self.r.state['last_processed_bar']=raw['timestamp']-1
        self.r.state['last_signal']=sig
        self.r.signal=lambda:sig
        return sig
    def lock(self,sig,high):
        self.r.state['config'].update(renko_loss_range_enabled=True,renko_loss_range_buffer=0)
        self.r.state['renko_loss_lock']=dict(active=True,underlying=self.c['underlying'],run_id=self.r.state.get('run_id'),
            high=high,low=90,box=10,buffer_bricks=0,triggered_at=sig['market_event_at']-1,exit_brick_at=sig['timestamp']-1)
        sig.update(open=110,close=120,box=10)
        self.r.state['renko_engine']['last'].update(open=110,close=120,box=10)
    def test_inside_continuation_blocked_before_paper_fill(self):
        sig=self.scenario();self.lock(sig,130)
        self.r._candle_step()
        self.assertFalse(self.r.state.get('position'));self.assertFalse(self.r.state.get('order_history'))
        self.assertEqual(self.r.state['latest_entry_assessment']['code'],'RENKO_RANGE_LOCK')
    def test_breakout_continuation_fills_on_that_brick(self):
        sig=self.scenario();self.lock(sig,110)
        self.r._candle_step()
        self.assertIsNotNone(self.r.state.get('position'))
        self.assertEqual(len(self.r.state['order_history']),1)
        self.assertFalse(self.r.state['renko_loss_lock']['active']);self.assertEqual(self.b.sent,[])

if __name__=='__main__':unittest.main()
