"""Projected history must never veto a flat runner's completed Renko entry."""
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from .signals import Engine
from .runner import Runner, configuration
from .test_runner import FakeBroker
from .test_brick_basis import BASE

HOST = 1793206200
CONFIG = {**BASE, 'timeframe':'5 minutes', 'underlying':'MCX:CRUDEOILM26NOVFUT',
          'manual_brick':10.56, 'atr_length':5, 'ema_fast_enabled':False,
          'ema_exit_enabled':False, 'supertrend_slope_enabled':True,
          'supertrend_slope_min_atr':0, 'session_deadline':'23:30',
          'mode':'PAPER', 'lots':1, 'max_trades':2, 'strategy':'RENKO_SUPERTREND_V1', 'exit_policy':'OPPOSITE_CONFIRMED_SIGNAL'}

def six_brick_observation():
    # Controlled completed-brick warmup; exact incident OHLC and six brick prices.
    # This fixture does not claim to reproduce the full historical indicator seed.
    engine = Engine(CONFIG)
    for i in range(81):
        p=(853+i)*10.56
        engine.update(dict(timestamp=1793181900+i*300,open=p,high=p+1,low=p-1,close=p))
    before=deepcopy(engine.state)
    row=engine.update(dict(timestamp=HOST,open=9849,high=9860,low=9760,close=9777))
    return before,row

class ProjectionEntryIsolationTests(unittest.TestCase):
    def test_projected_buy_exit_does_not_suppress_later_passing_bricks(self):
        before,row=six_brick_observation()
        self.assertEqual(before['brick_indicator_state']['projected_position']['direction'],'BULLISH')
        bricks=row['brick_events']
        self.assertEqual(len(bricks),6)
        self.assertEqual(bricks[0]['lifecycle_event'],'BUY EXIT')
        self.assertFalse(bricks[2]['supertrend_slope_filter']['allowed'])
        highlighted=bricks[3]
        self.assertAlmostEqual(highlighted['open'],9810.24)
        self.assertAlmostEqual(highlighted['close'],9799.68)
        self.assertEqual(highlighted['direction'],'BEARISH')
        self.assertTrue(highlighted['supertrend_slope_filter']['allowed'])
        self.assertTrue(highlighted['entry_qualified'])
        self.assertEqual(highlighted['entry_direction'],'BEARISH')
        self.assertTrue(row['entry_qualified'])
        self.assertEqual(row['entry_direction'],'BEARISH')
        # Keep historical display's existing exit-only lifecycle for this host.
        self.assertFalse(any(b['lifecycle_event'] in ('BUY','SELL') for b in bricks[1:]))

    def test_projected_position_presence_cannot_change_any_brick_qualification(self):
        before,_=six_brick_observation()
        flat=deepcopy(before)
        flat['brick_indicator_state']['projected_position']=None
        host=dict(timestamp=HOST,open=9849,high=9860,low=9760,close=9777)
        held_row=Engine(CONFIG,state=before).update(host)
        flat_row=Engine(CONFIG,state=flat).update(host)
        fields=('entry_qualified','entry_direction','entry_diagnostic','supertrend_slope_filter')
        self.assertEqual([{k:b[k] for k in fields} for b in held_row['brick_events']],
                         [{k:b[k] for k in fields} for b in flat_row['brick_events']])

    def make_runner(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        broker=FakeBroker()
        broker.now=HOST+305
        runner=Runner(broker,Path(temp.name)/'state.json',lambda:broker.now)
        self.addCleanup(runner.release)
        runner.state.update(config={**configuration(CONFIG), 'session_deadline':'23:30'},run_id='isolated-six-brick',
                            started_at=HOST-300,eligible_since=HOST-300,
                            position=None,pending=None,trades_used=0,
                            last_processed_bar=HOST-300)
        return runner,broker

    def test_zero_trade_flat_runner_accepts_host_once_without_order_submission(self):
        _,row=six_brick_observation()
        runner,broker=self.make_runner()
        sig={**row,'cross_direction':row['entry_direction']}
        self.assertTrue(runner.fresh_cross(sig))
        assessment=deepcopy(runner.state['latest_entry_assessment'])
        self.assertEqual(assessment['code'],'ELIGIBLE')
        self.assertFalse(runner.fresh_cross(sig))
        self.assertEqual(runner.state['latest_entry_assessment'],assessment)
        self.assertEqual(runner.state['trades_used'],0)
        self.assertIsNone(runner.state['position'])
        self.assertEqual(broker.sent,[])

    def test_actual_held_buy_still_exits_on_opposite_brick(self):
        from .exit_indicators import reason
        _,row=six_brick_observation()
        runner,broker=self.make_runner()
        runner.state['position']={'symbol':'MCX:FAKE','direction':'BULLISH','opened_at':HOST-300}
        self.assertEqual(reason(CONFIG,row,'BULLISH'),'OPPOSITE_RENKO_BRICK_CLOSE')
        self.assertTrue(runner.fresh_cross({**row,'cross_direction':row['entry_direction']}))
        self.assertTrue(runner.state['latest_exit_assessment']['eligible'])
        self.assertNotIn('latest_entry_assessment',runner.state)
        self.assertEqual(broker.sent,[])

if __name__=='__main__':
    unittest.main()
