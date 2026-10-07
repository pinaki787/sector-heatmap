import unittest
from copy import deepcopy
from .signals import ema_setup, series
from .test_signals import candle
from .runner import Runner

class EmaEntryTests(unittest.TestCase):
    def setup_gap(self, gap, previous, bullish=True, allowed=True):
        # Equal prior EMAs give an exact independently calculated next gap.
        alpha=2/11-2/31
        s=dict(ema10=100.,ema30=100.,ema_gaps=previous)
        return ema_setup(s,100+gap/alpha,-1 if bullish else 1,allowed,3)
    def test_strict_widening_equality_and_narrowing(self):
        self.assertTrue(self.setup_gap(3,[1,2])['entry_buy_signal'])
        self.assertFalse(self.setup_gap(2,[1,2])['entry_buy_signal'])
        self.assertFalse(self.setup_gap(1,[1,2])['entry_buy_signal'])
    def test_bearish_symmetry_and_regime_alignment(self):
        self.assertTrue(self.setup_gap(-3,[-1,-2],False)['entry_sell_signal'])
        self.assertFalse(self.setup_gap(3,[1,2],False)['entry_sell_signal'])
        self.assertFalse(self.setup_gap(-3,[-1,-2],True)['entry_buy_signal'])
    def test_adx_gate_blocks_entry(self):
        self.assertEqual(self.setup_gap(3,[1,2],allowed=False)['entry_diagnostic'],'WAITING_ADX')
    def test_late_qualification_seed_and_no_repeat(self):
        rows=series([candle(i,p) for i,p in enumerate([100,110,120,130,140,150])],dict(atr_length=1,factor=.1,brick_mode='Manual',manual_brick=10,rsi_slope_enabled=False,widening_window=3))
        self.assertEqual(rows[0]['ema10'],100)
        self.assertEqual(rows[1]['ema10'],100+2/11*10)
        self.assertTrue(rows[1]['buy_signal'])
        self.assertFalse(rows[1]['entry_buy_signal'])
        self.assertTrue(rows[3]['entry_buy_signal'])
        self.assertFalse(rows[3]['buy_signal'])
        self.assertEqual(sum(r['entry_buy_signal'] for r in rows),1)
    def test_completed_only_and_serialized_continuity(self):
        from .signals import Engine
        e=Engine();e.update(candle(0,100));before=deepcopy(e.state)
        self.assertIsNone(e.update({**candle(1,200),'is_forming':True}))
        self.assertEqual(e.state,before)
        restored=Engine(state=before)
        self.assertEqual(e.update(candle(1,110)),restored.update(candle(1,110)))
    def test_original_exit_does_not_require_ema_entry(self):
        r=Runner.__new__(Runner)
        self.assertTrue(r.exit_signal(dict(supertrend_cross_direction='BEARISH',cross_direction=None),'BULLISH'))
        self.assertFalse(r.exit_signal(dict(supertrend_cross_direction=None,cross_direction='BEARISH'),'BULLISH'))
        self.assertFalse(r.exit_signal(dict(supertrend_cross_direction='BEARISH',is_forming=True),'BULLISH'))
    def test_rearms_after_setup_break(self):
        s=dict(ema10=100.,ema30=100.,ema_gaps=[1,2],ema_qualified='BULLISH')
        self.assertIsNone(ema_setup(s,130,-1,True,3)['entry_direction'])
        ema_setup(s,130,-1,False,3)
        s.update(ema10=100.,ema30=100.,ema_gaps=[1,2])
        self.assertEqual(ema_setup(s,130,-1,True,3)['entry_direction'],'BULLISH')

    def test_one_increase_default_removes_filter_candle_without_lookahead(self):
        from .signals import settings
        self.assertEqual(settings({})['widening_window'],2)
        self.assertFalse(settings({})['use_adx'])
        prices=[100,110,120,130]
        config=dict(atr_length=1,factor=.1,brick_mode='Manual',manual_brick=10,rsi_slope_enabled=False)
        fast=series([candle(i,p) for i,p in enumerate(prices)],config)
        strict=series([candle(i,p) for i,p in enumerate(prices)],{**config,'widening_window':3})
        self.assertEqual([i for i,r in enumerate(fast) if r['entry_buy_signal']],[2])
        self.assertEqual([i for i,r in enumerate(strict) if r['entry_buy_signal']],[3])
        prefix=series([candle(i,p) for i,p in enumerate(prices[:3])],config)
        self.assertEqual(prefix[-1],fast[2])
