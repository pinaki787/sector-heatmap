import tempfile,unittest,json
from pathlib import Path
from fyers_history_recovery import verified_fetch
class Recovery(unittest.TestCase):
 def test_conflict_recovery_requires_two_identical_clean_refetches_and_persists_cooldown(self):
  with tempfile.TemporaryDirectory() as d:
   calls=[];now=[100];responses=['conflict',[1],[1]]
   def request(start,end):calls.append((start,end));return responses.pop(0)
   def verify(raw,end):
    if raw=='conflict':raise ValueError('conflicting duplicate OHLC')
    return raw
   def run():return verified_fetch(request=request,verify=verify,scope=dict(account='a',symbol='EXACT',session='today'),folder=d,now=now[0],range_from=0,range_to=100)
   with self.assertRaises(ValueError):run()
   for _ in range(3):
    with self.assertRaisesRegex(ValueError,'cooling'):run()
   self.assertEqual(len(calls),1)
   now[0]=105
   with self.assertRaisesRegex(ValueError,'confirmation'):run()
   now[0]=110;self.assertEqual(run(),[1])
   self.assertEqual(calls,[(0,100)]*3)
   saved=json.loads(next(Path(d).glob('*.json')).read_text());self.assertEqual(saved['state'],'RECOVERED')
 def test_persistent_disagreement_exhausts_budget_and_never_selects_a_value(self):
  with tempfile.TemporaryDirectory() as d:
   calls=[]
   def request(a,b):calls.append(1);return len(calls)
   def verify(raw,end):
    if raw==1:raise ValueError('conflict')
    return [raw]
   for now in (100,105,110):
    with self.assertRaises(ValueError):verified_fetch(request=request,verify=verify,scope={'account':'a'},folder=d,now=now,range_from=0,range_to=100)
   for now in (200,300):
    with self.assertRaisesRegex(ValueError,'exhausted'):verified_fetch(request=request,verify=verify,scope={'account':'a'},folder=d,now=now,range_from=0,range_to=100)
   self.assertEqual(len(calls),3)
 def test_scope_isolation_and_healthy_path_never_retries(self):
  with tempfile.TemporaryDirectory() as d:
   calls=[]
   for account in ('a','b'):
    rows=verified_fetch(request=lambda a,b:calls.append(1) or [1],verify=lambda raw,end:raw,scope={'account':account},folder=d,now=100,range_from=0,range_to=100)
    self.assertEqual(rows,[1])
   self.assertEqual(len(calls),2)
 def test_recovery_budget_is_shared_by_concurrent_processes(self):
  import threading,time
  with tempfile.TemporaryDirectory() as d:
   calls=[];errors=[]
   def request(a,b):calls.append(1);time.sleep(.01);return ['bad']
   def verify(raw,end):raise ValueError('conflict')
   def run():
    try:verified_fetch(request=request,verify=verify,scope={'account':'a'},folder=d,now=100,range_from=0,range_to=100)
    except ValueError as e:errors.append(str(e))
   threads=[threading.Thread(target=run) for _ in range(5)]
   for t in threads:t.start()
   for t in threads:t.join()
   self.assertEqual(len(calls),1);self.assertEqual(len(errors),5)
 def test_committed_candle_survives_duplicate_updates_and_restart(self):
  from sector_heatmap.motilal_history_seed import verified_minutes
  with tempfile.TemporaryDirectory() as d:
   original=[60,10,12,9,11,5]
   args=dict(verify=verified_minutes,scope={'account':'a','symbol':'exact'},folder=d,now=200,range_from=0,range_to=180)
   first=verified_fetch(request=lambda a,b:[original],**args)
   second=verified_fetch(request=lambda a,b:[original,[60,9,12,9,11,5]],**args)
   self.assertEqual(first,second);self.assertEqual(len(second),1)
   self.assertEqual(json.loads(next(Path(d).glob('*.json')).read_text())['quarantine'][0]['retained']['open'],10)
 def test_first_acquisition_conflict_uses_two_consistent_narrow_reads(self):
  from sector_heatmap.motilal_history_seed import verified_minutes
  with tempfile.TemporaryDirectory() as d:
   calls=[];good=[60,9,12,9,11,5];bad=[60,10,12,9,11,5]
   def request(a,b):calls.append((a,b));return [good,bad] if len(calls)==1 else [good]
   args=dict(request=request,verify=verified_minutes,scope={'account':'a'},folder=d,range_from=0,range_to=180)
   with self.assertRaises(ValueError):verified_fetch(now=200,**args)
   with self.assertRaisesRegex(ValueError,'confirmation'):verified_fetch(now=205,**args)
   result=verified_fetch(now=210,**args)
   self.assertEqual(result[0]['open'],9);self.assertEqual(calls,[(0,180),(60,119),(60,119)])
   self.assertEqual(json.loads(next(Path(d).glob('*.json')).read_text())['state'],'RECOVERED')
 def test_actual_captured_sensex_incident_recovers_without_first_last_selection(self):
  from sector_heatmap.motilal_history_seed import verified_minutes
  fixture=json.loads((Path(__file__).resolve().parents[2]/'tests/fixtures/fyers-sensex-duplicate-20261126.json').read_text())
  with tempfile.TemporaryDirectory() as d:
   responses=[fixture['bulk'],*fixture['independent_narrow_responses']];calls=[]
   def request(a,b):calls.append((a,b));return responses.pop(0)
   args=dict(request=request,verify=verified_minutes,scope={'account':'fixture','symbol':fixture['symbol']},folder=d,range_from=fixture['timestamp']-60,range_to=fixture['timestamp']+60)
   with self.assertRaises(ValueError):verified_fetch(now=1795700000,**args)
   with self.assertRaises(ValueError):verified_fetch(now=1795700005,**args)
   result=verified_fetch(now=1795700010,**args)
   self.assertEqual(len(result),1);self.assertEqual(result[0]['open'],59.7)
   self.assertEqual(calls[1:],[(fixture['timestamp'],fixture['timestamp']+59)]*2)
