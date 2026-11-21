import json,tempfile,unittest
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock
from sector_heatmap.handoff_errors import IncompleteAnalysis
from sector_heatmap.handoff_bridge import OwnedBridge
from sector_heatmap.handoff_schedule import Schedule
from sector_heatmap.market_calendar import IST
from sector_heatmap.handoff_cards import scheduled_report,summary
from sector_heatmap.combined_reports import handoff_section
class Tests(unittest.TestCase):
 def report(self):
  return dict(source=dict(broker='FYERS'),instrument_route='cash_equity',scope=dict(screener=dict(enabled=True,auto_enabled=True,status='UNAVAILABLE')),cards=[dict(candidate=dict(symbol='NSE:TEST-EQ',direction='BULLISH'),analysis=dict(direction='BULLISH',status='REVIEW',kind='EQUITY',conviction=dict(score=7,maximum_score=10)))],exclusions=[])
 def test_bridge_retains_findings_but_never_prepares_or_executes(self):
  b=object.__new__(OwnedBridge);b.account=dict(broker='FYERS');b.account_id='owned';b.analysis=lambda *a:self.report();b.request=Mock()
  with self.assertRaises(IncompleteAnalysis) as caught:b.collect(dict(mode='AUTO'))
  r=caught.exception.report
  self.assertTrue(r['execution_blocked']);self.assertEqual(len(r['cards']),2)
  self.assertEqual(r['scheduled_status']['code'],'DATA_UNAVAILABLE');b.request.assert_not_called()
 def test_schedule_saves_review_report_without_allocating_or_replaying(self):
  with tempfile.TemporaryDirectory()as tmp:
   report=self.report();report.update(generated_at='2026-10-26T10:00:00+05:30',execution_blocked=True,scheduled_status=dict(code='DATA_UNAVAILABLE',message='Screener source incomplete; automatic entries withheld.'))
   def collect(p):raise IncompleteAnalysis('Fresh Screener collection is incomplete',report)
   execute=Mock();s=Schedule(Path(tmp)/'s.db','owned','FYERS',collect,lambda p:dict(positions_verified=True,orders_verified=True,used_capital=0,available_funds=100000,exposed_underlyings=[],daily_loss=0),execute,lambda:True)
   s.configure(dict(enabled=True,mode='AUTO',live_authorized=True))
   now=datetime(2026,10,26,10,0,tzinfo=IST);out=s.step(now)
   self.assertEqual(out['state'],'REVIEW');execute.assert_not_called()
   with s.db()as db:
    stored=json.loads(db.execute('select output from runs').fetchone()[0]);self.assertEqual(db.execute('select count(*) from receipts').fetchone()[0],0)
   self.assertEqual(stored['orders_submitted'],0);self.assertEqual(stored['report'],report)
   self.assertEqual(s.step(now)['state'],'ALREADY_PROCESSED')
   public=scheduled_report(dict(id='owned',broker='FYERS'),'REVIEW',now.timestamp(),stored,'private account detail')
   self.assertTrue(public['cards']);snap=summary(public,'FYERS',now.timestamp())
   self.assertIn('UNAVAILABLE',snap['freshness']);self.assertNotIn('private account detail',json.dumps(snap))
   self.assertTrue(any('automatic entries withheld' in x for x in handoff_section(public,now.timestamp(),now)['lines']))
if __name__=='__main__':unittest.main()
