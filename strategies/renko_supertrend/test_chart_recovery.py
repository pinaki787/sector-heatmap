from copy import deepcopy
import unittest
from .chart_recovery import analyze_chart
from .runner import analysis, HistoryRevision
from .test_brick_basis import BASE,candles
from .test_live_chart import LiveChartTests

class ChartRecoveryTests(unittest.TestCase):
    def test_revised_completed_history_recovers_once_without_mutating_saved(self):
        config={**BASE,'manual_brick':10,'underlying':'TEST','timeframe':'5 minutes'}
        rows=candles([100+i*3 for i in range(1100)])
        saved=analysis(rows,config,.05,retain=5000); original=deepcopy(saved)
        rows[1]['close']+=1
        with self.assertRaises(HistoryRevision):analysis(rows,config,.05,saved=saved)
        rebuilt,recovery=analyze_chart(rows,config,.05,saved=saved)
        self.assertEqual(rebuilt,analysis(rows,config,.05,retain=5000))
        self.assertEqual(rebuilt['anchor'],saved['anchor'])
        self.assertEqual(recovery['scope'],'DISPLAY_ONLY')
        self.assertEqual(saved,original)
        again,recovery=analyze_chart(rows,config,.05,saved=rebuilt)
        self.assertIsNone(recovery)
        self.assertEqual(again,rebuilt)

class ChartReseedTests(LiveChartTests):
    def test_explicit_reseed_discards_invalid_display_and_changes_revision(self):
        self.price(self.start+35)
        before=self.chart.apply('a')
        self.chart.seed('a',self.engine,self.config,.05,replace=True)
        after=self.chart.apply('a',self.response)
        self.assertNotEqual(before['live_chart_revision'],after['live_chart_revision'])
        self.assertEqual(after['rows'],self.engine['rows'])
