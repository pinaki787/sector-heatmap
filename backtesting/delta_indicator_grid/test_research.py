import unittest
from backtesting.delta_indicator_grid.research import indicators,run_sim

class ResearchTests(unittest.TestCase):
    def rows(self,values):
        return [dict(timestamp=i*60,open=o,high=h,low=l,close=c,volume=1) for i,(o,h,l,c) in enumerate(values)]
    def simulate(self,rows,stop=2):
        signals=[dict(cross_direction='BULLISH' if i==0 else None,entry_direction='BULLISH' if i==0 else None) for i in range(len(rows))]
        return run_sim(rows,signals,[dict(expanding=False,release=False) for r in rows],[dict(atr=1,ema=100,supertrend=1) for r in rows],dict(resolution='1m',entry_rule='CROSS_ONLY',bb='BASELINE',trend='NONE',atr_exit=stop),dict(capital=10000,contracts=1,fee_bps=0,slippage_bps=0,half_spread_bps=0,funding_bps_day=0),1,.01,0,len(rows)*60,True)
    def test_wilder_seed(self):
        rows=self.rows([(10,12,9,11),(11,13,10,12),(12,14,11,13),(13,17,12,16)])
        result=indicators(rows,3,3,3)
        self.assertIsNone(result[1]['atr']);self.assertEqual(result[2]['atr'],3)
        self.assertAlmostEqual(result[3]['atr'],11/3);self.assertEqual(result[2]['ema'],12);self.assertEqual(result[3]['ema'],14)
    def test_indicators_causal(self):
        rows=self.rows([(100+i,102+i,99+i,101+i) for i in range(80)])
        self.assertEqual(indicators(rows[:55]),indicators(rows)[:55])
    def test_supertrend_changes_both_directions(self):
        rows=self.rows([(100,101,99,100),(100,101,99,100),(110,111,109,110),(90,91,89,90)])
        self.assertEqual([r['supertrend'] for r in indicators(rows,2,1,2)],[None,-1,1,-1])
    def test_gap_stop(self):
        result=self.simulate(self.rows([(100,101,99,100),(100,101,99,100),(95,96,94,95)]))
        trade=result['trades'][0]
        self.assertEqual(trade['entry_time'],60);self.assertEqual(trade['exit'],95);self.assertEqual(trade['exit_reason'],'ATR_STOP')
    def test_trail_not_retroactive(self):
        result=self.simulate(self.rows([(100,101,99,100),(100,110,99,109),(109,110,108,109)]))
        self.assertEqual(result['trades'][0]['exit_reason'],'PERIOD_END')
        self.assertEqual(result['trades'][0]['net_pnl'],9)
    def test_entry_candle_stop(self):
        result=self.simulate(self.rows([(100,101,99,100),(100,101,97,100),(100,101,99,100)]))
        self.assertEqual(result['trades'][0]['exit'],98);self.assertEqual(result['metrics']['trades'],1)
    def test_no_stop_baseline(self):
        result=self.simulate(self.rows([(100,101,99,100),(100,101,90,100),(100,101,99,100)]),0)
        self.assertEqual(result['trades'][0]['exit_reason'],'PERIOD_END')
    def test_missing_candle_rejected(self):
        rows=self.rows([(100,101,99,100)]*3);rows[1]['timestamp']=61
        with self.assertRaises(ValueError):self.simulate(rows)

if __name__=='__main__':unittest.main()
