import unittest
from core import Strategy
class OptionHybridTests(unittest.TestCase):
    def engine(self):
        e=Strategy(dict(reference_value=12,market='NSE',timeframe=5))
        e.reset_contract(dict(symbol='CALL',option_type='CE'),.2)
        for i,p in enumerate([100,98,96,94,92]):
            e.update(dict(kind='underlying',timestamp=100+i*300,close=p));e.position=None
        for i,p in enumerate([40,41,42,43,44,45]):
            e.update(dict(kind='premium',symbol='CALL',timestamp=100+i*300,close=p));e.position=None
        e.pending_underlying_flip=None
        return e
    def test_underlying_flip_waits_for_new_bullish_premium_confirmation(self):
        e=self.engine();actions=[]
        for i,p in enumerate(range(94,115,2)):
            actions=e.update_hybrid(dict(kind='price',series='underlying',timestamp=2000+i,close=p))
            self.assertFalse(any(a['action']=='BUY' for a in actions))
            if e.pending_underlying_flip is not None:break
        self.assertIsNotNone(e.pending_underlying_flip)
        actions=e.update_hybrid(dict(kind='price',series='premium',symbol='CALL',timestamp=2100,close=46))
        self.assertEqual(actions[0]['action'],'BUY')
    def test_manual_call_exits_only_on_confirmed_adverse_premium(self):
        e=self.engine();e.manual_entry('CE',2000)
        # Underlying movement cannot replace the agreed premium exit.
        self.assertEqual(e.update_hybrid(dict(kind='price',series='underlying',timestamp=2001,close=88)),[])
        exits=[]
        for i,p in enumerate([44,43,42,41,40,39,38]):
            exits=e.update_hybrid(dict(kind='price',series='premium',symbol='CALL',timestamp=2100+i,close=p))
            if exits:break
        self.assertEqual(exits[0]['action'],'SELL')
        self.assertEqual(exits[0]['reason'],'AI_RENKO_SUPERTREND_PREMIUM')
    def test_wrong_premium_contract_rejected(self):
        with self.assertRaisesRegex(ValueError,'Exact selected'):
            self.engine().update_hybrid(dict(kind='price',series='premium',symbol='OTHER',timestamp=2100,close=46))

    def test_contract_quote_cannot_bypass_hybrid_premium_confirmation(self):
        e=self.engine();e.hybrid_active=True;e.pending_underlying_flip=2000
        e.under_result=dict(direction=-1);e.premium_result=dict(direction=-1)
        e.last_time['premium']=2001
        self.assertIsNone(e.selected_gate_entry())

    def test_flip_seen_while_owned_cannot_be_reused_as_a_new_flat_entry(self):
        e=self.engine();e.manual_entry('CE',2000)
        for i,price in enumerate(range(94,115,2)):
            e.update_hybrid(dict(kind='price',series='underlying',timestamp=2100+i,close=price))
        self.assertIsNotNone(e.entry_confirmation.pending)
        for i,price in enumerate([44,43,42,41,40,39,38]):
            actions=e.update_hybrid(dict(kind='price',series='premium',symbol='CALL',timestamp=2200+i,close=price))
            if actions:break
        self.assertEqual(actions[0]['action'],'SELL')
        self.assertIsNone(e.entry_confirmation.pending)
        self.assertIsNone(e.pending_underlying_flip)
        self.assertEqual(e.update_hybrid(dict(kind='price',series='underlying',timestamp=2300,close=116)),[])
        self.assertEqual(e.update_hybrid(dict(kind='price',series='premium',symbol='CALL',timestamp=2301,close=50)),[])

    def test_live_premium_confirmation_does_not_overwrite_candle_cursor(self):
        e=self.engine();previous=e.last_time['premium']
        e.update_hybrid(dict(kind='price',series='premium',symbol='CALL',timestamp=2100,available_at=2100.5,close=46))
        self.assertEqual(e.last_time['premium'],previous)
        self.assertEqual(e.premium_confirmation['available_at'],2100.5)

    def test_delayed_premium_body_closed_before_underlying_flip_cannot_enter(self):
        e=self.engine();e.hybrid_active=True;e.pending_underlying_flip=2000.5;e.pending_underlying_flip_source_at=2000
        e.under_result=dict(direction=-1);e.premium_result=dict(direction=-1)
        e.premium_confirmation=dict(available_at=2001,closed_at=1999)
        self.assertIsNone(e.selected_gate_entry())
        self.assertIsNone(e.position)
        e.premium_confirmation=dict(available_at=2002,closed_at=2001)
        self.assertEqual(e.selected_gate_entry()['action'],'BUY')
