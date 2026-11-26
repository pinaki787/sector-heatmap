import unittest
from direct import DirectStrategy
class DirectHybridTests(unittest.TestCase):
    def engine(self):
        e=DirectStrategy(dict(underlying='BTCUSD',market='CRYPTO',timeframe=5,reference_value=46))
        for i,p in enumerate([100,98,96,94,92]):
            e.update(dict(kind='underlying',timestamp=100+i*300,close=p));e.position=None
        e.pending_direction=None
        return e
    def test_live_completed_brick_can_enter_without_time_candle_close(self):
        e=self.engine();actions=[]
        for i,p in enumerate(range(94,115,2)):
            actions=e.update_hybrid(dict(kind='price',timestamp=1600+i,close=p))
            if actions:break
        self.assertEqual(actions[0]['action'],'OPEN_LONG')
        self.assertEqual(actions[0]['confirmation']['confirmation_basis'],'COMPLETED_RENKO_BRICK')
    def test_manual_countertrend_exit_requires_new_completed_body(self):
        e=self.engine();e.manual_entry('LONG',1500);e.position['entry_confirmed_at']=1500
        line=e.under_result['st']
        event=dict(kind='underlying',timestamp=1500,closed_at=1800,available_at=1801,close=min(92,line-.1),open=min(92,line-.1)+.2,source_basis='PROVIDER_CONFIRMED_CLOSE',body_available=True)
        actions=e.update_hybrid(event)
        self.assertEqual(actions[0]['action'],'CLOSE_LONG')
        self.assertIsNone(e.pending_direction)
    def test_unverified_or_large_body_cannot_exit(self):
        for available,body in [(False,.2),(True,2)]:
            e=self.engine();e.manual_entry('LONG',1500)
            self.assertEqual(e.update_hybrid(dict(kind='underlying',timestamp=1600,close=92,open=92+body,source_basis='PROVIDER_CONFIRMED_CLOSE',body_available=available)),[])

    def test_provider_regression_or_duplicate_sequence_never_rewinds_renko(self):
        e=self.engine();event=dict(kind='price',timestamp=1600,available_at=1601,sequence=1,close=94)
        e.update_hybrid(event);level=e.under_renko.level
        for change in [dict(sequence=1,available_at=1602),dict(sequence=2,timestamp=1599,available_at=1602)]:
            with self.subTest(change=change),self.assertRaises(ValueError):e.update_hybrid(dict(event,**change))
            self.assertEqual(e.under_renko.level,level)
