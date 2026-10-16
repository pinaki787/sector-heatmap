import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
from .runner import Runner,configuration,TIMEFRAMES
from .test_runner import FakeBroker
class TimeframeChangeTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.b=FakeBroker();self.r=Runner(self.b,Path(folder.name)/'state.json',lambda:self.b.now);self.addCleanup(self.r.release)
        self.r.state.update(config=configuration(dict(strategy='RENKO_SUPERTREND_V1',underlying='NSE:NIFTY50-INDEX',timeframe='1 minute',lots=1,mode='PAPER',exit_policy='OPPOSITE_CONFIRMED_SIGNAL')),run_id='test',trades_used=2,realized_pnl=-10)
        self.payload=dict(run_id='test',underlying='NSE:NIFTY50-INDEX',mode='PAPER',timeframe='5 minutes')
    def test_flat_preserves_stopped_and_accounting(self):
        self.r.chart_timeframe(self.payload)
        self.assertEqual(self.r.state['config']['timeframe'],'5 minutes')
        self.assertFalse(self.r.state['running'])
        self.assertEqual(self.r.state['trades_used'],2)
        self.assertEqual(self.r.state['realized_pnl'],-10)
        self.assertGreater(self.r.state['eligible_since'],self.b.now)
        self.assertEqual(self.b.sent,[])
    def test_position_and_pending_defer(self):
        self.r.state.update(running=True,position={'symbol':'TEST'})
        self.r.chart_timeframe(self.payload)
        self.assertEqual(self.r.state['config']['timeframe'],'1 minute')
        self.r.state.update(position=None,pending={'order':{}})
        self.assertFalse(self.r.apply_pending_timeframe())
        self.r.state['pending']=None
        self.assertTrue(self.r.apply_pending_timeframe())
        self.assertTrue(self.r.state['running'])
        self.assertEqual(self.b.sent,[])
    def test_identity_and_failed_history_do_not_change_active_config(self):
        with self.assertRaises(ValueError):self.r.chart_timeframe({**self.payload,'run_id':'other'})
        with patch.object(self.b,'candles',side_effect=ValueError('History unavailable')):
            with self.assertRaises(ValueError):self.r.chart_timeframe(self.payload)
        self.assertEqual(self.r.state['config']['timeframe'],'1 minute')
        self.assertEqual(self.b.sent,[])
    def test_higher_timeframe_pair_survives_deferred_change(self):
        self.r.state['config'].update(higher_timeframe_enabled=True,supertrend_timeframe='5 minutes')
        self.r.state['position']={'symbol':'TEST'}
        self.r.chart_timeframe(self.payload)
        self.assertEqual(self.r.state['config']['supertrend_timeframe'],'5 minutes')
        self.assertEqual(self.r.state['pending_timeframe']['supertrend_timeframe'],'15 minutes')
        self.r.state['position']=None
        self.r.apply_pending_timeframe()
        self.assertEqual(self.r.state['config']['supertrend_timeframe'],'15 minutes')
        self.r.chart_timeframe({**self.payload,'timeframe':'1 minute'})
        self.assertEqual(self.r.state['config']['supertrend_timeframe'],'5 minutes')
        self.assertEqual(self.b.sent,[])

    def test_select_current_cancels_queued_change(self):
        self.r.state['position']={'symbol':'TEST'}
        self.r.chart_timeframe(self.payload)
        self.r.chart_timeframe({**self.payload,'timeframe':'1 minute'})
        self.assertNotIn('pending_timeframe',self.r.state)
