import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from .directional_research import RecoveryLocks, simulate
from .signals import Engine
from .research_replay import replay
import math


class RecoveryTests(unittest.TestCase):
    def test_call_requires_strict_high_recovery_not_downside_or_equality(self):
        locks=RecoveryLocks('directional');locks.loss('BULLISH',110,95,1)
        self.assertTrue(locks.allows('BEARISH'))
        for price in (94,110):
            self.assertEqual(locks.observe(price,2),[]);self.assertFalse(locks.allows('BULLISH'))
        self.assertEqual(locks.observe(111,3),['BULLISH'])
        self.assertTrue(locks.allows('BULLISH'))

    def test_put_requires_strict_low_and_locks_can_coexist(self):
        locks=RecoveryLocks('directional');locks.loss('BULLISH',110,95,1);locks.loss('BEARISH',120,90,1)
        self.assertEqual(locks.observe(121,2),['BULLISH'])
        self.assertFalse(locks.allows('BEARISH'));self.assertEqual(locks.observe(90,3),[])
        self.assertEqual(locks.observe(89,4),['BEARISH'])

    def test_no_same_observation_release_and_baseline_either_boundary(self):
        locks=RecoveryLocks('either');locks.loss('BULLISH',110,95,2)
        self.assertEqual(locks.observe(94,2),[])
        self.assertFalse(locks.allows('BEARISH'))
        self.assertEqual(set(locks.observe(94,3)),{'BULLISH','BEARISH'})

    def rows(self):
        at=int(datetime(2026,9,1,10,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp())
        values=[(100,101,99,100,90,True),(105,110,95,96,100,False),
                (94,112,92,93,90,True),(94,105,93,100,90,True),
                (111,113,109,111,100,True),(112,114,110,113,100,True)]
        return [dict(timestamp=at+i*60,open=o,high=h,low=l,close=c,ema10=e,
                     entry_qualified=q,direction='BULLISH',cross_direction=None)
                for i,(o,h,l,c,e,q) in enumerate(values)]

    def test_downside_unlocks_baseline_but_candidate_waits_for_close_high(self):
        baseline=simulate(self.rows(),'either',0)
        candidate=simulate(self.rows(),'directional',0)
        self.assertEqual(baseline['open_position']['entry_time'],self.rows()[3]['timestamp'])
        self.assertEqual(candidate['open_position']['entry_time'],self.rows()[5]['timestamp'])
        self.assertEqual(candidate['trades'][0]['high'],110)
        self.assertEqual(candidate['skipped'][0]['reason'],'RECOVERY_LOCK')
        # The112 wick in the exit-fill candle must not unlock at its93 close.
        self.assertEqual(candidate['releases'][0]['at'],self.rows()[4]['timestamp']+60)

    def test_long_loss_outside_quick_window_does_not_add_new_lock(self):
        result=simulate(self.rows(),'directional',0,max_candles=1)
        self.assertEqual(result['lock_triggers'],0)

    def test_costs_affect_loss_trigger_without_double_spread_deduction(self):
        rows=self.rows();rows[2]['open']=106
        free=simulate(rows,'directional',0)
        costly=simulate(rows,'directional',100)
        self.assertEqual(free['lock_triggers'],0)
        self.assertEqual(costly['lock_triggers'],1)
        self.assertAlmostEqual(costly['trades'][0]['modeled_cost_points'],2.11)

    def test_no_lock_control_matches_existing_completed_replay(self):
        at=int(datetime(2026,9,1,9,15,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp())
        engine=Engine(dict(timeframe='1 minute'),.05);rows=[]
        for i in range(375):
            o=1000+30*math.sin(i/12);c=1000+30*math.sin((i+1)/12)
            rows.append(engine.update(dict(timestamp=at+i*60,open=o,high=max(o,c)+2,
                                          low=min(o,c)-2,close=c,volume=100)))
        original=replay(rows,2)['trades'];control=simulate(rows,'none',2)['trades']
        self.assertGreater(len(original),0)
        self.assertEqual([(t['entry_time'],t['exit_time']) for t in original],
                         [(t['entry_time'],t['exit_time']) for t in control])
        self.assertAlmostEqual(sum(t['net_points'] for t in original),sum(t['net_points'] for t in control))


if __name__=='__main__':unittest.main()
