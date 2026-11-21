import unittest,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,Mock
from sector_heatmap import handoff_screener as hs
from sector_heatmap.handoff_broker_read import public_read_error
from sector_heatmap.handoff_allocation import allocate
from tests.test_handoff_screener import NOW,frames,Sectors
from tests.test_handoff_allocation import idea

class DhanSources(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.folder=Path(self.tmp.name)
  self.store=hs.Store(self.folder,'DHAN')
  self.selection=dict(enabled=True,auto_enabled=True,symbols=['A','B'],sources=[dict(id='chosen',label='Chosen Screener',url='https://chartink.com/screener/chosen',symbols=['A','B'])])
  self.store.save(self.selection);self.sectors=Sectors();self.sectors.provider=SimpleNamespace(broker='DHAN')
  self.master=Mock();self.master.lookup.side_effect=lambda symbols:{s:dict(securityId=str(i)) for i,s in enumerate(symbols)}
 def merge(self,master=True):
  sector=dict(key='stock:A',kind='stock',symbol='NSE:A-EQ',name='A',direction='BEARISH',parent_sector='Sector leaders')
  with patch('sector_heatmap.analysis.calculate_timeframe_state',side_effect=lambda tf,*a:frames()[tf]):
   return hs.merge(dict(candidates=[sector],scope={},mode='intraday'),self.sectors,self.folder,auto=True,now=NOW,master=self.master if master else None,fetcher=lambda url:dict(status='READY',executed_membership=True,symbols=['A','B'],checked_at=NOW.isoformat()))
 def test_native_merge_combines_sources_and_deduplicates(self):
  value=self.merge();self.assertEqual(len(value['candidates']),2)
  a=next(r for r in value['candidates'] if r['symbol']=='NSE:A-EQ')
  self.assertEqual({p['kind'] for p in a['provenance']},{'SECTOR','SCREENER'})
  self.assertEqual(value['scope']['screener']['duplicates_merged'],1)
  self.assertEqual(self.store.get()['broker'],'DHAN')
 def test_no_fyers_master_fallback(self):
  with patch('sector_heatmap.handoff.FyersCmMaster') as fyers:
   with self.assertRaisesRegex(ValueError,'native broker master'):self.merge(False)
   fyers.assert_not_called()
 def test_saved_sources_cannot_cross_brokers(self):
  with self.assertRaisesRegex(PermissionError,'another broker'):hs.Store(self.folder,'FYERS').get()
 def test_native_final_preflight_checks_current_selection(self):
  candidate=self.merge()['candidates'][0]
  self.store.save({**self.selection,'auto_enabled':False})
  with self.assertRaisesRegex(ValueError,'changed|removed'):hs.guard_entry_source(candidate,self.folder,NOW,broker='DHAN')
 def test_rank_top_five_across_source_labels_inside_fifty_thousand_pool(self):
  rows=[]
  for i,score in enumerate([7,10,8,9,6,10,5]):
   row=idea('NSE:'+chr(65+i)+'-EQ',score=score,maximum=10,entry=100)
   row['source_rank']=i+1;row['provenance']=[{'kind':'SCREENER' if i%2 else 'SECTOR'}];rows.append(row)
  value=allocate(rows,capital=50000,used=10000,funds=50000,top=5)
  self.assertEqual([r['symbol'] for r in value['plans']],['NSE:B-EQ','NSE:F-EQ','NSE:D-EQ','NSE:C-EQ','NSE:A-EQ'])
  self.assertEqual(float(value['allocated']),40000)
  self.assertLessEqual(sum(float(r['allocation_limit']) for r in value['plans'])+10000,50000)
 def test_unavailable_broker_is_explained_without_leaking_unexpected_errors(self):
  message=public_read_error(RuntimeError('Dhan service is temporarily unavailable. Read/preview failed.'))
  self.assertIn('Auto Live entries withheld',message)
  self.assertNotIn('secret',public_read_error(RuntimeError('secret diagnostic')))
class AnalysisAvailability(unittest.TestCase):
 def test_analysis_survives_missing_positions_without_assuming_flat(self):
  from tests.test_handoff_analysis import Provider,AnalysisTests
  from sector_heatmap.handoff_analysis import opportunities
  provider=Provider()
  provider.positions=lambda:(_ for _ in ()).throw(RuntimeError('Selected account temporarily unavailable'))
  report=opportunities(AnalysisTests().payload(),provider,{})
  self.assertEqual(len(report['cards']),1)
  self.assertFalse(report['exposure_verified']);self.assertTrue(report['execution_blocked'])
  self.assertEqual(report['order_authority'],'NONE')
 def test_schedule_retains_analysis_when_execution_account_is_unavailable(self):
  from sector_heatmap.handoff_schedule import Schedule
  import sqlite3,json
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'schedule.sqlite3';submitted=[]
   def unavailable(p):raise ValueError('Selected broker unavailable')
   schedule=Schedule(path,'owned','FYERS',lambda p:([],{'cards':[{'title':'Completed analysis'}]}),unavailable,execute=lambda *a:submitted.append(a))
   schedule.configure({'enabled':True,'mode':'MANUAL'})
   value=schedule.step(NOW);self.assertEqual(value['state'],'REVIEW');self.assertFalse(submitted)
   with sqlite3.connect(path) as db:saved=json.loads(db.execute('SELECT output FROM runs').fetchone()[0])
   self.assertEqual(saved['report']['cards'][0]['title'],'Completed analysis')
   self.assertEqual(saved['orders_submitted'],0);self.assertTrue(saved['execution_blocked'])
if __name__=='__main__':unittest.main()
