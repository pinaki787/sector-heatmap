import unittest
from datetime import datetime,timezone
from sector_heatmap.handoff_freshness import report_freshness

class Freshness(unittest.TestCase):
    def result(self,age=0,state='COMPLETED',source='latest',generated=True):
        now=1800000000
        output={'report':{'generated_at':datetime.fromtimestamp(now-age,timezone.utc).isoformat()}} if generated else {}
        return report_freshness(output,source,dict(slot='latest',state=state),now)
    def test_current_completed_report_can_be_selected(self):
        self.assertTrue(self.result(age=30)['selectable'])
    def test_old_report_is_retained_but_not_selectable(self):
        self.assertEqual(self.result(age=901)['state'],'STALE')
    def test_newer_failure_cannot_make_old_output_current(self):
        self.assertFalse(self.result(age=30,source='earlier',state='REVIEW')['selectable'])
    def test_partial_report_never_becomes_executable(self):
        self.assertEqual(self.result(age=30,state='REVIEW')['state'],'PARTIAL')
    def test_missing_or_future_generation_time_is_not_current(self):
        self.assertFalse(self.result(generated=False)['selectable'])
        self.assertFalse(self.result(age=-30)['selectable'])
    def test_no_output_is_empty(self):
        self.assertEqual(report_freshness({},None,None,1800000000)['state'],'EMPTY')
