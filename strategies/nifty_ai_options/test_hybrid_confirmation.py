import unittest
from hybrid_confirmation import HybridConfirmation
class HybridConfirmationTests(unittest.TestCase):
    def gate(self):
        gate=HybridConfirmation(10);gate.arm('LONG',100,'flip1');return gate
    def test_completed_aligned_brick_qualifies_without_waiting_for_host_close(self):
        gate=self.gate();result=gate.confirm(dict(kind='brick',closed=True,open=100,close=110,available_at=100),'LONG',95)
        self.assertEqual(result['confirmation_basis'],'COMPLETED_RENKO_BRICK');self.assertIsNone(gate.pending)
    def test_smaller_body_qualifies_even_with_large_wicks_and_uses_only_closed_unit(self):
        gate=self.gate();unit=dict(kind='candle',closed=False,open=110,close=105,high=130,low=90,available_at=160)
        self.assertIsNone(gate.confirm(unit,'LONG',100));unit['closed']=True
        result=gate.confirm(unit,'LONG',100);self.assertEqual(result['body'],5);self.assertEqual(result['confirmation_basis'],'COMPLETED_SMALL_CANDLE_BODY')
    def test_large_or_exact_one_brick_candle_requires_real_brick_confirmation(self):
        for close in [110,111]:
            self.assertIsNone(self.gate().confirm(dict(kind='candle',closed=True,open=100,close=close,available_at=160),'LONG',95))
    def test_partial_brick_wrong_side_or_earlier_unit_cannot_confirm(self):
        for unit,line in [(dict(kind='brick',closed=True,open=100,close=109,available_at=101),95),(dict(kind='brick',closed=True,open=110,close=100,available_at=101),95),(dict(kind='candle',closed=True,open=100,close=105,available_at=99),95),(dict(kind='candle',closed=True,open=100,close=105,available_at=101),106)]:self.assertIsNone(self.gate().confirm(unit,'LONG',line))
    def test_flip_is_consumed_once_and_opposite_flip_supersedes_unconfirmed_signal(self):
        gate=self.gate();gate.arm('SHORT',101,'flip2');self.assertIsNone(gate.confirm(dict(kind='brick',closed=True,open=100,close=110,available_at=102),'LONG',95))
        unit=dict(kind='brick',closed=True,open=110,close=100,available_at=102)
        self.assertEqual(gate.confirm(unit,'SHORT',115)['direction'],'SHORT');gate.arm('SHORT',101,'flip2');self.assertIsNone(gate.confirm(unit,'SHORT',115))
    def test_already_aligned_trend_without_fresh_flip_does_not_enter(self):
        self.assertIsNone(HybridConfirmation(10).confirm(dict(kind='candle',closed=True,open=100,close=105,available_at=101),'LONG',95))

    def test_finite_negative_supertrend_is_a_valid_indicator_level(self):
        self.assertIsNotNone(self.gate().confirm(dict(kind='brick',closed=True,open=100,close=110,available_at=101),'LONG',-1))

    def test_manual_position_exit_also_requires_opposite_direction_and_completed_hybrid_unit(self):
        from hybrid_confirmation import confirm_exit
        position=dict(symbol='BTCUSD',side='LONG',entry_timestamp=50,entry_confirmed_at=100,manual_override=True)
        unit=dict(kind='candle',closed=True,open=110,close=105,available_at=160)
        self.assertIsNone(confirm_exit(unit,position,'LONG',115,10))
        self.assertIsNone(confirm_exit(dict(unit,closed=False),position,'SHORT',115,10))
        self.assertIsNone(confirm_exit(dict(unit,open=120),position,'SHORT',115,10))
        self.assertEqual(confirm_exit(unit,position,'SHORT',115,10)['confirmation_basis'],'COMPLETED_SMALL_CANDLE_BODY')
    def test_bought_put_exits_on_bearish_premium_not_bullish_premium(self):
        from hybrid_confirmation import confirm_exit
        position=dict(symbol='PUT',side='PE',entry_timestamp=100)
        unit=dict(kind='brick',closed=True,open=110,close=100,available_at=101)
        self.assertIsNone(confirm_exit(unit,position,'LONG',95,10,premium=True))
        self.assertIsNotNone(confirm_exit(unit,position,'SHORT',115,10,premium=True))
    def test_pre_entry_or_same_observation_unit_cannot_retroactively_exit_manual_position(self):
        from hybrid_confirmation import confirm_exit
        position=dict(symbol='EXACT',side='LONG',entry_timestamp=50,entry_confirmed_at=100)
        for at in [99,100]:self.assertIsNone(confirm_exit(dict(kind='brick',closed=True,open=110,close=100,available_at=at),position,'SHORT',115,10))


class DelayedExitUnitTests(unittest.TestCase):
    def test_old_closed_candle_received_after_entry_never_exits(self):
        from hybrid_confirmation import confirm_exit
        position=dict(side='LONG',symbol='OWNED',entry_timestamp=100,entry_confirmed_at=110)
        unit=dict(kind='candle',closed=True,open=100.2,close=100,closed_at=105,available_at=115)
        self.assertIsNone(confirm_exit(unit,position,'SHORT',101,1))
        unit['closed_at']=112
        self.assertIsNotNone(confirm_exit(unit,position,'SHORT',101,1))
    def test_queued_pre_entry_price_brick_never_exits_even_if_processed_later(self):
        from hybrid_confirmation import confirm_exit
        unit=dict(kind='brick',closed=True,open=101,close=100,closed_at=105,available_at=115)
        self.assertIsNone(confirm_exit(unit,dict(side='LONG',entry_confirmed_at=110),'SHORT',102,1))

class DelayedEntryUnitTests(unittest.TestCase):
    def test_delayed_pre_flip_body_cannot_confirm_entry(self):
        gate=HybridConfirmation(10);gate.arm('LONG',110,'new-flip',source_at=109.5)
        unit=dict(kind='candle',closed=True,open=101,close=105,closed_at=109,available_at=115)
        self.assertIsNone(gate.confirm(unit,'LONG',100))
        unit['closed_at']=112
        self.assertIsNotNone(gate.confirm(unit,'LONG',100))
    def test_flip_producing_brick_keeps_transport_delay_and_qualifies(self):
        gate=HybridConfirmation(10);gate.arm('LONG',110,'new-flip',source_at=109.5)
        unit=dict(kind='brick',closed=True,open=100,close=110,closed_at=109.5,available_at=110)
        self.assertIsNotNone(gate.confirm(unit,'LONG',95))
