import copy,unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory
from pathlib import Path
from sector_heatmap.combined_reports import collect
from datetime import datetime
from sector_heatmap.combined_reports import ACCOUNT,select_handoff_outcome
from sector_heatmap.market_brief_visual import handoff_public,caption
from sector_heatmap.market_calendar import IST
class RetentionTests(unittest.TestCase):
 def row(self,stamp,report,account=ACCOUNT):return ({'id':account,'broker':'FYERS'},str(stamp),stamp,report)
 def report(self,cards=None,code=None):
  r={'cards':cards or [],'source':{'broker':'FYERS'},'generated_at':'2026-10-26T12:00:00+05:30'}
  if code:r['scheduled_status']={'code':code,'message':'Refresh status'}
  return r
 def test_combined_report_reads_only_selected_fyers_account(self):
  account={'id':ACCOUNT,'broker':'FYERS'}
  config={'accounts':[{'id':'unrelated','broker':'DHAN'},account]}
  def owned_jobs(selected,root):
   self.assertEqual(selected['accounts'],[account])
   yield self.row(1,self.report())
  with TemporaryDirectory() as folder, patch('sector_heatmap.combined_reports.completed_jobs',side_effect=owned_jobs):
   value=collect(config,datetime(2026,11,1,10,0,tzinfo=IST),screener={},root=Path(folder),mtf={})
  section=dict(value['sections'])['ANALYSIS HANDOFF']
  self.assertIn('No new eligible recommendations.',section['lines'])
  self.assertEqual(config['accounts'][0]['id'],'unrelated')
 def test_failed_refresh_retains_exact_completed_report_without_mutation(self):
  card={'candidate':{'symbol':'NSE:TEST-EQ','timeframe_states':{'15m':{'last_updated':'2026-10-26T11:45:00+05:30'}}},'analysis':{'kind':'EQUITY','entry':100,'target':110,'recommended_invalidation':{'price':95}}}
  rows=[self.row(1,self.report([card])),self.row(2,self.report(code='DATA_UNAVAILABLE'))];original=copy.deepcopy(rows)
  selected=select_handoff_outcome(rows)
  self.assertEqual(selected[3]['cards'],[card]);self.assertTrue(selected[3]['report_refresh']['retained']);self.assertEqual(rows,original)
  public=handoff_public(selected[3],datetime(2026,10,27,10,0,tzinfo=IST))
  self.assertIn('STALE',public['status']);self.assertTrue(public['retained']);self.assertEqual(public['rows'][0]['horizons'][0]['underlying']['entry'],100)
  self.assertIn('Not current recommendations',caption({'handoff_visual':public}))
 def test_completed_empty_scan_supersedes_older_findings_even_after_failure(self):
  rows=[self.row(1,self.report([{'analysis':{}}])),self.row(2,self.report(code='NO_NEW_SIGNALS')),self.row(3,self.report(code='RATE_LIMITED'))]
  self.assertEqual(select_handoff_outcome(rows)[3]['cards'],[])
 def test_terminal_manual_job_with_incomplete_source_is_not_a_valid_empty_scan(self):
  failed=self.report();failed['scope']={'screener':{'enabled':True,'status':'UNAVAILABLE'}}
  rows=[self.row(1,self.report([{'analysis':{}}])),self.row(2,failed)]
  selected=select_handoff_outcome(rows)
  self.assertTrue(selected[3]['report_refresh']['retained']);self.assertEqual(len(selected[3]['cards']),1)
  only=select_handoff_outcome([rows[-1]])
  self.assertEqual(only[3]['scheduled_status']['code'],'DATA_UNAVAILABLE')
 def test_completed_empty_latest_is_never_replaced(self):
  rows=[self.row(1,self.report([{'analysis':{}}])),self.row(2,self.report())]
  self.assertEqual(select_handoff_outcome(rows),rows[-1])
 def test_foreign_scope_and_broker_cannot_supply_fallback(self):
  rows=[self.row(4,self.report([{'analysis':{}}]),'foreign'),self.row(3,{'cards':[{}],'source':{'broker':'DHAN'}}),self.row(2,self.report(code='DATA_UNAVAILABLE'))]
  self.assertEqual(select_handoff_outcome(rows),rows[-1])
 def test_failure_without_success_explains_unavailable_not_no_signals(self):
  row=self.row(2,self.report(code='DATA_UNAVAILABLE'));self.assertEqual(select_handoff_outcome([row]),row)
  p=handoff_public(row[3],datetime(2026,10,27,10,0,tzinfo=IST));self.assertIn('unavailable',p['empty_reason']);self.assertFalse(p['retained'])
if __name__=='__main__':unittest.main()
