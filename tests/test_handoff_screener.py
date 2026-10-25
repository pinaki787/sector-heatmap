import unittest,tempfile,json,sqlite3
from pathlib import Path
from datetime import datetime
from unittest.mock import patch,Mock
from sector_heatmap import handoff_screener as hs
from sector_heatmap.market_calendar import IST
NOW=datetime(2026,10,23,12,0,tzinfo=IST)
def frames(state=-2,quality="DELAYED"):
 return {tf:dict(state=state,label="Strong Bearish" if state<0 else "Strong Bullish",close=100,ema20=104 if state<0 else 96,atr=5,adx=32,relative_strength_state="Strong Underperformer" if state<0 else "Strong Outperformer",data_quality=quality,reasons=[],last_updated="2026-10-23T11:45:00+05:30" if tf in {"15m","1h"} else "2026-10-23T05:30:00+05:30" if tf=='daily' else "2026-10-19T05:30:00+05:30") for tf in ("15m","1h","daily","weekly")}
class Sectors:
 def __init__(self):self.calls=[]
 def _timeframe_candles(self,symbol):self.calls.append(symbol);return {tf:[{}] for tf in frames()}
 def _quality(self,tf,candles):return 'DELAYED'
class ScreenerTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.folder=Path(self.tmp.name);self.store=hs.Store(self.folder)
  self.selection=dict(enabled=True,auto_enabled=True,symbols=['A','B'],sources=[dict(id='screen1',label='Chosen screen',url='https://chartink.com/screener/chosen',symbols=['A','B'])])
  self.store.save(self.selection);self.sectors=Sectors();self.master=Mock();self.master.lookup.side_effect=lambda symbols:{x:{'tick_size':.05} for x in symbols}
  self.collection=dict(candidates=[],scope={},mode='intraday')
 def fetch(self,url):return dict(status='READY',executed_membership=True,symbols=['A','B','UNSELECTED'],checked_at=NOW.isoformat())
 def merge(self,frame=None,collection=None,fetch=None):
  with patch('sector_heatmap.analysis.calculate_timeframe_state',side_effect=lambda tf,*a:(frame or frames())[tf]):
   return hs.merge(collection or self.collection,self.sectors,self.folder,auto=True,now=NOW,master=self.master,fetcher=fetch or self.fetch)
 def test_only_explicit_selected_members_are_included(self):
  result=self.merge();self.assertEqual({x['symbol'] for x in result['candidates']},{'NSE:A-EQ','NSE:B-EQ'});self.assertEqual(result['scope']['screener']['status'],'COMPLETED')
 def test_source_and_sector_duplicates_merge_provenance_once(self):
  c=dict(key='stock:A',kind='stock',symbol='NSE:A-EQ',name='A',direction='BEARISH',parent_sector='Sector 1')
  value=self.merge(collection=dict(candidates=[c],scope={},mode='intraday'));a=next(x for x in value['candidates'] if x['symbol']=='NSE:A-EQ')
  self.assertEqual(len(a['provenance']),2);self.assertIn('Sector 1',a['source_summary']);self.assertIn('Chosen screen',a['source_summary']);self.assertEqual(value['scope']['screener']['duplicates_merged'],1);self.assertEqual(self.store.status()['latest']['duplicates_merged'],1)
 def test_same_symbol_in_two_screens_has_one_candidate_and_both_sources(self):
  self.selection['sources'].append(dict(id='screen2',label='Second screen',url='https://chartink.com/screener/second',symbols=['A']))
  self.store.save(self.selection);result=self.merge();a=next(x for x in result['candidates'] if x['ticker']=='A');self.assertEqual(len(a['provenance']),2);self.assertEqual(len(result['candidates']),2)
 def test_conflicting_sources_do_not_choose_one_direction(self):
  c=dict(key='stock:A',kind='stock',symbol='NSE:A-EQ',direction='BULLISH',parent_sector='Sector')
  result=self.merge(collection=dict(candidates=[c],scope={},mode='intraday'));self.assertNotIn('NSE:A-EQ',[x['symbol'] for x in result['candidates']]);self.assertTrue(any('conflict' in x['reason'] for x in result['scope']['screener']['exclusions']))
 def test_failed_source_never_reuses_historical_membership_for_live(self):
  result=self.merge(fetch=lambda u:dict(status='UNAVAILABLE'));self.assertEqual(result['candidates'],[]);self.assertEqual(result['scope']['screener']['status'],'UNAVAILABLE')
 def test_empty_executed_source_is_explicit_and_does_not_fail_closed_as_unknown(self):
  result=self.merge(fetch=lambda u:dict(status='READY',executed_membership=True,symbols=[],checked_at=NOW.isoformat()));self.assertEqual(result['candidates'],[]);self.assertEqual(result['scope']['screener']['status'],'COMPLETED');self.assertEqual(result['scope']['screener']['current_selected'],0)
 def test_stale_missing_or_unknown_broker_quality_withheld(self):
  for quality in ('STALE','UNAVAILABLE','UNKNOWN'):
   self.store.save({**self.selection,'selection_origin':quality});result=self.merge(frame=frames(quality=quality));self.assertEqual(result['candidates'],[])
 def test_restart_reuses_only_valid_evidence_without_rescanning(self):
  self.merge();count=len(self.sectors.calls);self.store=hs.Store(self.folder);self.merge();self.assertEqual(len(self.sectors.calls),count)
 def test_selection_revision_invalidates_cached_universe(self):
  self.merge();value={**self.selection,'symbols':['B'],'sources':[{**self.selection['sources'][0],'symbols':['B']}]};self.store.save(value);result=self.merge();self.assertEqual([x['ticker'] for x in result['candidates']],['B'])
 def test_cancelled_scan_persists_partial_evidence_and_resumes(self):
  count=[0]
  def stop(message):
   count[0]+=1
   if count[0]==2:raise RuntimeError('cancelled')
  with patch.object(hs,'checkpoint',side_effect=stop):
   with self.assertRaises(RuntimeError):self.merge()
  calls_before=self.sectors.calls.count('NSE:A-EQ');result=self.merge();self.assertEqual(len(result['candidates']),2);self.assertEqual(self.sectors.calls.count('NSE:A-EQ'),calls_before)
 def test_removed_or_changed_selection_blocks_final_entry(self):
  candidate=self.merge()['candidates'][0];self.store.save({**self.selection,'auto_enabled':False})
  with self.assertRaisesRegex(ValueError,'changed|removed'):hs.guard_entry_source(candidate,self.folder,NOW)
 def test_source_membership_is_rechecked_before_execution(self):
  candidate=self.merge()['candidates'][0]
  with self.store.db() as db:db.execute("DELETE FROM cache WHERE key LIKE 'source:%'")
  with patch.object(hs,'fetch_source',return_value=dict(status='READY',executed_membership=True,symbols=[],checked_at=NOW.isoformat())):
   with self.assertRaisesRegex(ValueError,'left'):hs.guard_entry_source(candidate,self.folder,NOW)
 def test_separate_batch_blocked_only_while_handoff_auto_owns_names(self):
  with sqlite3.connect(self.folder/'handoff-schedule.sqlite3') as db:db.execute('CREATE TABLE policy(id INTEGER,body TEXT)');db.execute('INSERT INTO policy VALUES(1,?)',(json.dumps(dict(enabled=True,mode='AUTO',live_authorized=True)),))
  with patch.object(hs,'owned_folder',return_value=self.folder):
   with self.assertRaisesRegex(ValueError,'owned by Handoff Auto'):hs.guard_separate_submission(['NSE:A-EQ'])
   hs.guard_separate_submission(['NSE:OTHER-EQ'])
 def test_url_and_universe_scope_fail_closed(self):
  for url in ('https://evil.example/screener/a','https://chartink.com.evil/screener/a','https://user@chartink.com/screener/a','https://chartink.com/screener/a?token=x'):
   with self.assertRaises(ValueError):hs.source_url(url)
  with self.assertRaises(ValueError):self.store.save({**self.selection,'symbols':['A']})
 def test_closed_session_requires_near_close_intraday_evidence(self):
  data=frames();self.assertFalse(hs.evidence_current(data,datetime(2026,10,25,12,tzinfo=IST)))
  data['15m']['last_updated']='2026-10-23T15:15:00+05:30';data['1h']['last_updated']='2026-10-23T15:15:00+05:30';self.assertTrue(hs.evidence_current(data,datetime(2026,10,25,12,tzinfo=IST)))
 def test_disabled_auto_inclusion_preserves_sector_only_analysis(self):
  self.store.save({**self.selection,'auto_enabled':False});c=dict(kind='stock',symbol='NSE:Z-EQ',key='stock:Z',direction='BULLISH',parent_sector='Sector')
  value=self.merge(collection=dict(candidates=[c],scope={}));self.assertEqual(len(value['candidates']),1);self.assertEqual(value['scope']['screener']['status'],'DISABLED')

class ExecutedSourceTests(unittest.TestCase):
 def session(self,rows,total):
  page=Mock(text='<meta name="csrf-token" content="PRIVATE_TOKEN"><div>&quot;atlas_query&quot;:&quot;( close > 1 )&quot;</div>',is_redirect=False);page.raise_for_status.return_value=None
  scan=Mock();scan.raise_for_status.return_value=None;scan.json.return_value=dict(recordsTotal=total,data=rows)
  session=Mock();session.get.return_value=page;session.post.return_value=scan;return session
 def test_page_symbols_are_never_substituted_for_executed_rows(self):
  session=self.session([],0);session.get.return_value.text='NSE:TEST /stocks/TEST'
  with self.assertRaisesRegex(ValueError,'Executable'):hs.fetch_source('https://chartink.com/screener/test',lambda:session)
  session.post.assert_not_called()
 def test_executed_membership_is_bounded_and_exact(self):
  session=self.session([dict(nsecode='A')],1);result=hs.fetch_source('https://chartink.com/screener/test',lambda:session);self.assertEqual(result['symbols'],['A']);self.assertTrue(result['executed_membership']);self.assertNotIn('PRIVATE_TOKEN',json.dumps(result))
 def test_incomplete_response_retried_read_only_once_then_withheld(self):
  session=self.session([dict(nsecode='A')],2)
  with self.assertRaisesRegex(ValueError,'incomplete'):hs.fetch_source('https://chartink.com/screener/test',lambda:session)
  self.assertEqual(session.post.call_count,2)

class PriorityAndExecution(unittest.TestCase):
 def test_manual_research_retains_source_failure_diagnostics_without_execution(self):
  from sector_heatmap.handoff_bridge import OwnedBridge
  bridge=object.__new__(OwnedBridge);bridge.account={'broker':'FYERS'};bridge.account_id='owned'
  bridge.analysis=lambda *a:dict(source={'broker':'FYERS'},scope={'screener':dict(enabled=True,auto_enabled=True,status='UNAVAILABLE')},cards=[],exclusions=[])
  rows,report=bridge.collect(dict(mode='MANUAL'));self.assertEqual(rows,[]);self.assertEqual(report['analysis_scopes'][0]['scope']['screener']['status'],'UNAVAILABLE')
 def test_auto_requires_completed_combined_source_ranking(self):
  from sector_heatmap.handoff_bridge import OwnedBridge
  bridge=object.__new__(OwnedBridge);bridge.account={'broker':'FYERS'};bridge.account_id='owned'
  bridge.analysis=lambda *a:dict(source={'broker':'FYERS'},scope={'screener':dict(enabled=True,auto_enabled=True,status='UNAVAILABLE')},cards=[],exclusions=[])
  with self.assertRaisesRegex(ValueError,'combined priority'):bridge.collect(dict(mode='AUTO'))
 def test_normalized_score_then_source_rank_wins(self):
  from sector_heatmap.handoff_allocation import rank
  from test_handoff_allocation import idea
  a={**idea('A',score=7,maximum=10),'source_rank':1};b={**idea('B',score=6,maximum=7),'source_rank':9}
  self.assertEqual(rank([a,b])[0][0]['symbol'],'B')
  a={**idea('A'),'source_rank':5};z={**idea('Z'),'source_rank':1};self.assertEqual(rank([a,z])[0][0]['symbol'],'Z')
 def test_sources_do_not_change_execution_identity_or_allow_replay(self):
  from sector_heatmap.handoff_allocation import identity,Claims,allocate
  from test_handoff_allocation import idea
  a=idea('A');b={**a,'provenance':[{'label':'Other screen'}]};self.assertEqual(identity(a),identity(b))
  with tempfile.TemporaryDirectory() as t:
   c=Claims(Path(t)/'c.sqlite');row=allocate([a])['plans'][0];c.reserve('owned',row)
   with self.assertRaises(ValueError):Claims(Path(t)/'c.sqlite').reserve('owned',allocate([b])['plans'][0])
 def test_highest_conviction_executes_before_lower_option_without_overallocating(self):
  from sector_heatmap.handoff_schedule import Schedule
  from test_handoff_allocation import idea
  calls=[]
  with tempfile.TemporaryDirectory() as t:
   rows=[{**idea('OPT','LONG_OPTION',score=5,maximum=7,lot=100),'source_rank':1},{**idea('CASH',score=6,maximum=6),'source_rank':2}]
   s=Schedule(Path(t)/'s.sqlite','owned','FYERS',lambda p:(rows,{'cards':[]}),lambda p:dict(positions_verified=True,orders_verified=True,used_capital=0,available_funds=100000,exposed_underlyings=[],daily_loss=0),execute=lambda plan,p:(calls.append(plan['symbol']) or dict(status='OPEN',protection_confirmed=True)),auto_ready=lambda:True)
   s.configure(dict(enabled=True,mode='AUTO',live_authorized=True));value=s.step(NOW)
   self.assertEqual(value['state'],'COMPLETED');self.assertEqual(calls,['CASH','OPT'])
 def test_old_slot_cannot_be_submitted_after_long_analysis(self):
  from sector_heatmap.handoff_schedule import Schedule
  from test_handoff_allocation import idea
  clock=[0];calls=[]
  with tempfile.TemporaryDirectory() as t:
   def collect(p):clock[0]=901;return [idea()],{'cards':[]}
   s=Schedule(Path(t)/'s.sqlite','owned','FYERS',collect,lambda p:dict(positions_verified=True,orders_verified=True,used_capital=0,available_funds=100000,exposed_underlyings=[],daily_loss=0),execute=lambda *a:calls.append(a),auto_ready=lambda:True,clock=lambda:clock[0]);s.configure(dict(enabled=True,mode='AUTO',live_authorized=True));self.assertEqual(s.step(NOW)['state'],'REVIEW');self.assertFalse(calls)
if __name__=='__main__':unittest.main()
