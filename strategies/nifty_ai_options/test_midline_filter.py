import math,unittest
from unittest.mock import Mock
from direct import DirectStrategy
from core import Strategy
from trend_filter import GaussianMidline

def result(direction,close,line,period=123):
    return dict(direction=direction,flip=True,bar_close=close,midline=line,midline_period=period,st=98 if direction<0 else 102)

class MidlineFilterTests(unittest.TestCase):
    def direct(self,product='MARGIN'):
        return DirectStrategy(dict(underlying='NSE:TEST-EQ',market='NSE',timeframe=5,reference_value=12,product=product,midline_filter_enabled=True,midline_period=123))
    def option(self,side):
        e=Strategy(dict(underlying='NSE:TEST-EQ',market='NSE',timeframe=5,reference_value=12,entry_gate='underlying_flip',exit_supertrend='underlying',midline_filter_enabled=True,midline_period=123))
        e.reset_contract(dict(symbol='CALL' if side=='CE' else 'PUT',option_type=side),.2)
        return e
    def test_direct_long_and_short_strict_close_filter(self):
        for side,close,line,allowed in [('LONG',101,100,True),('LONG',99,100,False),('LONG',100,100,False),('SHORT',99,100,True),('SHORT',101,100,False),('SHORT',100,100,False)]:
            with self.subTest(side=side,close=close):
                e=self.direct();e.under_result=result(-1 if side=='LONG' else 1,close,line);e.pending_direction=(side,100)
                action=e.selected_gate_entry();self.assertEqual(action is not None,allowed)
                if allowed:
                    self.assertEqual(action['action'],'OPEN_'+side)
                    self.assertEqual(action['position']['midline_confirmation']['close'],close)
                else:self.assertIsNone(e.position)
    def test_call_and_put_follow_underlying_not_premium_price(self):
        for side,close,line,allowed in [('CE',101,100,True),('CE',99,100,False),('PE',99,100,True),('PE',101,100,False),('CE',100,100,False),('PE',100,100,False)]:
            with self.subTest(side=side,close=close):
                e=self.option(side);e.under_result=result(-1 if side=='CE' else 1,close,line);e.pending_underlying_flip=100
                e.premium_result=result(-1,500,1)
                action=e.selected_gate_entry();self.assertEqual(action is not None,allowed)
                if allowed:self.assertEqual(action['position']['side'],side)
    def test_missing_nonfinite_or_wrong_period_blocks(self):
        for broken in [dict(direction=-1),result(-1,101,float('nan')),result(-1,True,100),result(-1,101,100,99)]:
            e=self.direct();e.under_result=broken;e.pending_direction=('LONG',100)
            self.assertIsNone(e.selected_gate_entry());self.assertIsNone(e.position)
    def test_full_precision_is_not_display_rounding(self):
        e=self.direct();e.under_result=result(-1,100+1e-10,100);e.pending_direction=('LONG',100)
        self.assertIsNotNone(e.selected_gate_entry())
    def test_blocked_direct_flip_cannot_enter_later_without_new_signal(self):
        e=self.direct();e.under_result=result(-1,99,100);e.pending_direction=('LONG',100)
        self.assertIsNone(e.selected_gate_entry())
        e.under_result=result(-1,101,100)
        self.assertIsNone(e.selected_gate_entry())
    def test_blocked_option_flip_is_consumed(self):
        e=self.option('CE');e.under_result=result(-1,99,100);e.pending_underlying_flip=100
        self.assertIsNone(e.selected_gate_entry());self.assertIsNone(e.pending_underlying_flip)
        e.under_result=result(-1,101,100);self.assertIsNone(e.selected_gate_entry())
    def test_long_exit_is_not_blocked_by_bearish_entry_filter(self):
        e=self.direct();e.position=dict(e.contract,side='LONG',entry_timestamp=1);e.under_result=result(-1,100,100)
        e.under_renko.update=Mock(return_value=[dict(open=100,high=100,low=99,close=99)])
        e.under_ai.update=Mock(return_value=result(1,99,98))
        actions=e.update(dict(kind='underlying',timestamp=100,close=99))
        self.assertEqual(actions[0]['action'],'CLOSE_LONG');self.assertIsNone(e.pending_direction)
    def test_option_exit_is_not_blocked(self):
        e=self.option('CE');e.position=dict(e.contract,side='CE',entry_timestamp=1);e.under_result=result(-1,100,100)
        e.under_renko.update=Mock(return_value=[dict(open=100,high=100,low=99,close=99)])
        e.under_ai.update=Mock(return_value=result(1,99,98))
        actions=e.update(dict(kind='underlying',timestamp=100,close=99));self.assertEqual(actions[0]['action'],'SELL')
    def test_delivery_equity_short_remains_disallowed(self):
        e=self.direct('CNC');e.under_result=result(1,99,100);e.pending_direction=('SHORT',100)
        self.assertIsNone(e.selected_gate_entry())
    def test_legacy_captured_configuration_keeps_previous_entry_policy(self):
        e=DirectStrategy(dict(underlying='NSE:TEST-EQ',market='NSE',timeframe=5,reference_value=12))
        e.under_result=dict(direction=-1);e.pending_direction=('LONG',100)
        self.assertIsNotNone(e.selected_gate_entry())
    def test_gaussian_seed_constant_and_incremental_append(self):
        a=GaussianMidline(123)
        for _ in range(100):self.assertAlmostEqual(a.update(100),100,places=10)
        values=[100+math.sin(i/3)*5 for i in range(200)]
        a=GaussianMidline(123);prefix=[a.update(v) for v in values[:100]];tail=[a.update(v) for v in values[100:]]
        b=GaussianMidline(123);full=[b.update(v) for v in values]
        self.assertEqual(prefix+tail,full)
    def test_retained_direct_reversal_is_cancelled_after_midline_rejection(self):
        from types import SimpleNamespace
        from reversal import advance
        e=self.direct();e.config.update(account='owner',runtime_session='session');e.under_result=result(-1,99,100)
        row=dict(runtime_session='session',account='owner',symbol=e.contract['symbol'],direction='LONG',signal_at=100,phase='WAITING_FOR_ENTRY')
        executor=SimpleNamespace(state=dict(position=None,pending=None,pending_reversal=row),save=Mock())
        send=Mock()
        self.assertIsNone(advance(e,executor,send));self.assertIsNone(executor.state['pending_reversal'])
        self.assertEqual(executor.state['reversal_history'][-1]['phase'],'CANCELLED')
        e.under_result=result(-1,101,100);self.assertIsNone(advance(e,executor,send));send.assert_not_called()
    def test_retained_option_entry_rechecks_underlying_midline(self):
        from option_legs import entry_valid
        e=self.option('CE');e.under_result=result(-1,99,100)
        action=dict(action='BUY',timestamp=100,position=dict(e.contract,side='CE'))
        self.assertFalse(entry_valid(e,action))
    def test_period_validation(self):
        for period in (True,0,4,501,12.3,'123'):
            with self.assertRaises(ValueError):GaussianMidline(period)

if __name__=='__main__':unittest.main()
