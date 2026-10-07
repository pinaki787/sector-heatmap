import unittest
from copy import deepcopy
from .retest import evaluate
from .signals import Engine,series,settings
from .runner import provisional
from .test_signals import candle
from . import test_runner as fixtures

CFG=dict(rsi_slope_enabled=False,timeframe='1 minute',atr_length=1,factor=2,brick_mode='Manual',manual_brick=10,retest_enabled=True)
def rows():return [candle(i,p) for i,p in enumerate([100,110,120,130,140])]+[{**candle(5,117,141,114),'open':140},{**candle(6,119,120,116),'open':117.5}]

class RetestTests(unittest.TestCase):
    def test_narrowing_bounce_and_disabled_baseline(self):
        enabled=series(rows(),CFG);disabled=series(rows(),{**CFG,'retest_enabled':False})
        self.assertLess(enabled[-1]['ema_gap'],enabled[-2]['ema_gap'])
        self.assertTrue(enabled[-1]['retest_signal']);self.assertEqual(enabled[-1]['entry_direction'],'BULLISH')
        self.assertFalse(enabled[-1]['ema_widening']);self.assertIsNone(disabled[-1]['entry_direction'])
        self.assertEqual(disabled[-1]['entry_diagnostic'],'WAITING_WIDENING')
        for a,b in zip(enabled,disabled):
            for key in ('supertrend','ema10','ema30','synthetic_close','adx'):self.assertEqual(a[key],b[key])
    def evaluate(self,state=None,bullish=True,allowed=True,**changes):
        side='BULLISH' if bullish else 'BEARISH';direction=-1 if bullish else 1
        state=state if state is not None else dict(retest_direction=side,retest_ready=True,retest_bars=[dict(timestamp=0,open=103 if bullish else 97,close=99 if bullish else 101,high=104,low=96)])
        bar=dict(timestamp=60,open=100,close=102 if bullish else 98,high=103,low=97);bar.update(changes)
        entry=dict(ema10=101 if bullish else 99,ema30=92 if bullish else 108)
        result=evaluate(state,bar,dict(close=110 if bullish else 90),(100,90 if bullish else 110),direction,direction,entry,allowed)
        return state,result
    def test_symmetry_touch_bounce_and_episode_consumption(self):
        for bullish in (True,False):
            state,r=self.evaluate(bullish=bullish);self.assertTrue(r['retest_signal'])
            self.assertFalse(self.evaluate(state,bullish)[1]['retest_signal'])
    def test_touch_without_rejection_or_adx_does_not_signal(self):
        self.assertFalse(self.evaluate(close=100)[1]['retest_signal'])
        self.assertFalse(self.evaluate(allowed=False)[1]['retest_signal'])
        self.assertFalse(self.evaluate(low=100.1)[1]['retest_signal'])
    def test_new_touch_requires_separation_and_alignment(self):
        state,_=self.evaluate();state,r=self.evaluate(state,open=103,close=105,low=102,high=106)
        self.assertFalse(r['retest_signal']);self.assertTrue(state['retest_ready'])
        state['retest_bars']=[dict(timestamp=0,open=103,close=99,high=104,low=96)]
        self.assertTrue(self.evaluate(state)[1]['retest_signal'])
        state=dict(retest_ready=True,retest_direction='BEARISH')
        self.assertFalse(self.evaluate(state)[1]['retest_signal'])
    def test_serialized_engine_and_prefix_have_no_lookahead(self):
        e=Engine(CFG)
        for bar in rows()[:-1]:e.update(bar)
        state=deepcopy(e.state)
        self.assertEqual(e.update(rows()[-1]),Engine(CFG,state=state).update(rows()[-1]))
        self.assertEqual(series(rows()[:-1],CFG)[-1],series(rows(),CFG)[-2])
    def test_forming_retest_does_not_trigger_confirmed_path(self):
        from .runner import analysis
        c={**CFG,'timeframe':'1 minute','underlying':'NSE:NIFTY50-INDEX'};a=analysis(rows()[:-1],c,.05)
        bar={**rows()[-1],'is_forming':True,'stream_exchange_at':rows()[-1]['timestamp']+5}
        r=provisional(a,bar,c,.05,bar['stream_exchange_at'])
        self.assertIsNone(r['entry_direction']);self.assertFalse(r.get('retest_signal',False))
    def test_bearish_engine_mirror_requires_bearish_pattern(self):
        mirrored=[{**r,'open':200-r['open'],'close':200-r['close'],'high':200-r['low'],'low':200-r['high']} for r in rows()]
        r=series(mirrored,CFG)[-1]
        self.assertTrue(r['retest_signal']);self.assertEqual(r['entry_direction'],'BEARISH')
        self.assertIn('BEARISH_HARAMI',r['retest_patterns'])
    def test_no_selected_patterns_is_rejected_when_enabled(self):
        with self.assertRaisesRegex(ValueError,'at least one'):settings(dict(retest_enabled=True,retest_engulfing=False,retest_harami=False,retest_star=False))
    def test_opt_in_is_boolean_default_off(self):
        self.assertFalse(settings({})['retest_enabled'])
        with self.assertRaises(ValueError):settings(dict(retest_enabled='true'))

class RetestLifecycleTests(unittest.TestCase):
    setUp=fixtures.RenkoLifecycleTests.setUp
    def start(self):
        p=self.r.preview(self.c);self.r.start(dict(preview_id=p['id'],confirmation=p['confirmation']),background=False)
    def prepare(self,intrabar=False):
        if intrabar:
            from .test_intrabar import TickBroker
            self.b=TickBroker();self.b.price=119;self.r.adapter=self.b
        self.c.update(CFG,intrabar_entries=intrabar)
        self.b.rows=[{**bar,'timestamp':self.b.now-365+i*60} for i,bar in enumerate(rows()[:-1])]
        self.start();self.r.step();self.assertIsNone(self.r.state['position'])
        self.b.now+=60
        self.b.rows.append({**rows()[-1],'timestamp':self.b.now-65})
    def test_confirmed_retest_paper_entry_and_no_duplicates(self):
        self.prepare();self.r.step()
        self.assertEqual(self.r.state['position']['direction'],'BULLISH')
        self.assertEqual(self.r.state['order_history'][0]['reason'],'EMA10_RETEST_BOUNCE')
        self.assertTrue(self.r.state['position']['entry_indicator_snapshot']['indicators']['retest_signal'])
        self.r.step();self.assertEqual(len(self.r.state['order_history']),1);self.assertEqual(self.b.sent,[])
    def test_confirmed_retest_survives_intrabar_widening_wait(self):
        self.prepare(True);self.r.step()
        self.assertEqual(self.r.state['order_history'][0]['reason'],'EMA10_RETEST_BOUNCE')
        self.assertEqual(self.r.state['position']['entry_mode'],'CONFIRMED')
    def test_pre_activation_retest_not_replayed(self):
        self.c.update(CFG)
        self.b.rows=[{**bar,'timestamp':self.b.now-425+i*60} for i,bar in enumerate(rows())]
        self.start();self.r.step();self.assertIsNone(self.r.state['position']);self.assertEqual(self.b.sent,[])
