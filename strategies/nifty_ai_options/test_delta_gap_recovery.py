import unittest,tempfile
from pathlib import Path
from types import SimpleNamespace
from .delta_gap_recovery import missing_events,apply_recovered
from .confirmed_close import ConfirmedClose
from .markets import SourceBars
class RecoveryTest(unittest.TestCase):
 def fixture(self,missing=False):
  directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
  def reader(symbol,frame,at):
   rows=[] if missing and at==120 else [[at,100,100,100,100,0]]
   return {'result':rows},rows
  return ConfirmedClose(reader,Path(directory.name)),SimpleNamespace(last_time={'underlying':0}),SimpleNamespace(bucket=60)
 def test_quiet_minute_is_provider_confirmed_in_order(self):
  c,e,b=self.fixture();events=missing_events(c,e,b,'PAXGUSD','underlying',1,181,101,182)
  self.assertEqual([x['timestamp'] for x in events],[60,120]);self.assertTrue(all(x['source_basis']=='PROVIDER_CONFIRMED_CLOSE' for x in events));self.assertEqual(e.last_time,{'underlying':0})
 def test_missing_actual_provider_candle_halts_before_any_application(self):
  c,e,b=self.fixture(True)
  with self.assertRaisesRegex(ValueError,'Exact completed provider close unavailable'):missing_events(c,e,b,'PAXGUSD','underlying',1,181,101,182)
 def test_startup_gap_is_reconciled_before_first_live_decision(self):
  c,e,b=self.fixture();b.bucket=None
  self.assertEqual([r["timestamp"] for r in missing_events(c,e,b,"PAXGUSD","underlying",1,121,101,122)],[60])
 def test_normal_tick_reads_no_history_and_large_gap_halts(self):
  c,e,b=self.fixture();self.assertEqual(missing_events(c,e,b,'PAXGUSD','underlying',1,61,101,62),[])
  with self.assertRaisesRegex(ValueError,'bounded recovery'):missing_events(c,e,b,'PAXGUSD','underlying',1,6000,101,6001)
 def test_historical_entry_never_submitted_and_owned_exit_does_not_reverse(self):
  for action,position in [('OPEN_LONG',None),('CLOSE_LONG',{'symbol':'PAXGUSD','side':'LONG'})]:
   engine=SimpleNamespace(position=position,config={'timeframe':1},entry_confirmation=SimpleNamespace(clear=lambda:None),band=SimpleNamespace(consume_entry=lambda:None),pending_direction=('LONG',1))
   def decide(engine,event):engine.position={'new':True} if action=='OPEN_LONG' else None;return [{'action':action}]
   chart=SimpleNamespace(append=lambda *a:None,decide=decide,append_bands=lambda *a:None);sent=[]
   apply_recovered([{'available_at':182}],engine,chart,sent.append,lambda row:None)
   self.assertEqual([a['action'] for a in sent],[] if action=='OPEN_LONG' else ['CLOSE_LONG']);self.assertIsNone(engine.position);self.assertIsNone(engine.pending_direction)
if __name__=='__main__':unittest.main()
