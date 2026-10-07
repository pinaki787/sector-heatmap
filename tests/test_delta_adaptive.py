import copy,json, tempfile, unittest
from pathlib import Path
from sector_heatmap.delta_adaptive import regimes,evidence,select_candidate,walk_forward,digest,DEFAULTS,AdaptiveResearch
from sector_heatmap.delta_research_ai import ResearchAI
from tests.test_delta_backtest import candles,CFG,SETTINGS

class AdaptiveTests(unittest.TestCase):
 def test_regime_prefix_is_causal(self):
  rows=candles(1500);self.assertEqual(regimes(rows)[:800],regimes(rows[:800]))
 def test_future_validation_never_counts(self):
  records=[dict(end=i,regime='R',metrics={'trades':10,'net_pnl':1},score=1) for i in (100,200,300,900)]
  self.assertEqual(evidence(records,300,'R',20)['windows'],3);self.assertFalse(evidence(records,200,'R',20)['eligible']);self.assertFalse(evidence(records,1000,'OTHER',20)['eligible'])
 def test_selection_persistence_cooldown_and_margin(self):
  cfg=dict(DEFAULTS,resolution='1m',persistence=2,cooldown_bars=100);rank=[dict(id='B',score=2,metrics={'trades':20}),dict(id='A',score=1,metrics={'trades':20})];lib={'B':[dict(end=i,regime='R',metrics={'trades':10,'net_pnl':1},score=1) for i in (1,2,3)]};guard={}
  self.assertEqual(select_candidate(rank,'A',guard,10000,'R',lib,cfg)['selected'],'A');self.assertEqual(select_candidate(rank,'A',guard,10060,'R',lib,cfg)['selected'],'B')
  guard.update(pending='B',streak=1,last_switch=10000);self.assertIn('cooldown',select_candidate(rank,'A',guard,10120,'R',lib,cfg)['reason'])
  rank[0]['score']=1.01;self.assertIn('margin',select_candidate(rank,'A',guard,30000,'R',lib,cfg)['reason'])
 def test_walk_forward_future_perturbation_and_dedup(self):
  rows=candles(1600,start=1705000020);configs=[dict(CFG,rsi_length=14,ma_length=14,ma_type='EMA'),dict(CFG,rsi_length=10,ma_length=14,ma_type='EMA')];cfg=dict(DEFAULTS,resolution='1m',warmup=300,train_bars=300,validation_bars=100,min_train_trades=5,min_validation_trades=10)
  for r in rows:r['timestamp']=float(r['timestamp'])
  a=walk_forward(rows,configs,SETTINGS,1,.1,cfg);modified=copy.deepcopy(rows);cut=a['folds'][3]['end']
  for r in modified:
   if r['timestamp']>=cut:
    for k in ('open','close','high','low'):r[k]*=1.5
  b=walk_forward(modified,configs,SETTINGS,1,.1,cfg);self.assertEqual(a['folds'][:4],b['folds'][:4]);repeat=walk_forward(rows,configs,SETTINGS,1,.1,cfg,a['library']);self.assertEqual([len(v) for v in a['library'].values()],[len(v) for v in repeat['library'].values()])
 def test_loop_initially_stopped_and_holdout_frozen(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=AdaptiveResearch(tmp,None,None,tmp,ai=ResearchAI(Path(tmp)/'ai.json',tmp,key_reader=lambda:''));self.addCleanup(a.shutdown.set);self.assertFalse(a.status()['loop_running']);a.state['holdout']={'start':1,'end':2,'result':{'candidate_id':'A'}}
   with self.assertRaisesRegex(ValueError,'fixes'):a.configure({'symbol':'ETHUSD'})
 def test_holdout_one_shot(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=AdaptiveResearch(tmp,None,None,tmp,ai=ResearchAI(Path(tmp)/'ai.json',tmp,key_reader=lambda:''));self.addCleanup(a.shutdown.set);a.state['library']['A']={'config':{}};a.state['holdout']={'result':{'candidate_id':'A'}}
   with self.assertRaisesRegex(ValueError,'already scored'):a.holdout_once({'candidate_id':'A'})

class BudgetTests(unittest.TestCase):
 def test_reservations_cache_daily_reset_and_no_secret(self):
  with tempfile.TemporaryDirectory() as tmp:
   calls=[];clock=[1791018000];ai=ResearchAI(Path(tmp)/'usage.json',tmp,clock=lambda:clock[0],key_reader=lambda:'secret-not-persisted',sender=lambda *args:(calls.append(args) or (json.dumps({'review':'Unvalidated.','experiments':[]}),100)))
   limits=dict(enabled=True,model='gpt-4.1-mini',calls_per_day=1,tokens_per_day=12000,max_output_tokens=400)
   self.assertEqual(ai.review({'n':1},limits)['state'],'COMPLETE');self.assertEqual(ai.review({'n':1},limits)['state'],'CACHED');self.assertEqual(ai.review({'n':2},limits)['state'],'BUDGET_LIMIT');self.assertEqual(len(calls),1);self.assertIn('JSON',calls[0][2]);self.assertNotIn('secret-not-persisted',ai.path.read_text());clock[0]+=86400;self.assertEqual(ai.review({'n':2},limits)['state'],'COMPLETE')
 def test_failure_charged_and_small_budget_blocks(self):
  with tempfile.TemporaryDirectory() as tmp:
   def fail(*args):raise RuntimeError('SECRET')
   ai=ResearchAI(Path(tmp)/'usage.json',tmp,key_reader=lambda:'x',sender=fail);limits=dict(enabled=True,model='gpt-4.1-mini',calls_per_day=2,tokens_per_day=10,max_output_tokens=400)
   self.assertEqual(ai.review({},limits)['state'],'BUDGET_LIMIT');limits['tokens_per_day']=12000;out=ai.review({},limits);self.assertEqual(out['state'],'ERROR');self.assertNotIn('SECRET',str(out));self.assertEqual(ai.status(limits)['usage']['calls'],1);self.assertGreater(ai.status(limits)['usage']['charged_tokens'],400)
 def test_schema_clips_invalid_proposals(self):
  with tempfile.TemporaryDirectory() as tmp:
   ai=ResearchAI(Path(tmp)/'usage.json',tmp,key_reader=lambda:'x',sender=lambda *a:(json.dumps({'review':'Review','experiments':[{'rsi_length':True,'ma_length':14,'ma_type':'EMA','filter':'BASELINE'},{'rsi_length':10,'ma_length':14,'ma_type':'EMA','filter':'BASELINE'}]}),100));out=ai.review({},dict(enabled=True,model='gpt-4.1-mini',calls_per_day=2,tokens_per_day=12000,max_output_tokens=400));self.assertEqual(len(out['experiments']),1)

class EvidenceBoundaryTests(unittest.TestCase):
 def make(self,tmp):
  a=AdaptiveResearch(tmp,None,None,tmp,ai=ResearchAI(Path(tmp)/'ai.json',tmp,key_reader=lambda:''));self.addCleanup(a.shutdown.set);return a
 def test_optimization_does_not_read_sealed_rows(self):
  from unittest.mock import patch
  import threading
  with tempfile.TemporaryDirectory() as tmp:
   a=self.make(tmp);c=dict(DEFAULTS,ai_enabled=False,resolution='1m',history_bars=1800,train_bars=300,validation_bars=100,holdout_bars=200,min_train_trades=5,min_validation_trades=10);rows=candles(1800);end=rows[-1]['timestamp']+60;product=dict(id=1,symbol='BTCUSD',contract_type='perpetual_futures',contract_value=1,tick_size=.1,notional_type='vanilla',is_quanto=False,quoting_currency='USD',settlement_currency='USD',contract_unit_currency='BTC',underlying='BTC');candidate=dict(CFG,rsi_length=14,ma_length=14,ma_type='EMA',symbol='BTCUSD');p=dict(settings=SETTINGS,combinations=[candidate],warmup=300);a.state['config']=c;a.state['job']={'id':'test','state':'RUNNING'};a.metadata=lambda _:product;a._data=lambda *_:(rows,p,{'coverage':{}},{'end':end});original=walk_forward;observed=[]
   def inspect(data,*args,**kwargs):observed.extend(r['timestamp'] for r in data);return original(data,*args,**kwargs)
   with patch('sector_heatmap.delta_adaptive.walk_forward',side_effect=inspect):a._cycle(c,threading.Event())
   self.assertEqual(a.state['job']['state'],'COMPLETE');seal=a.state['holdout'];self.assertTrue(all(t<seal['start'] for t in observed));self.assertIsNone(seal['result']);self.assertGreaterEqual(a.state['pending_forward']['start'],seal['end']+300*60)
 def test_prospective_requires_matching_cost_context(self):
  with tempfile.TemporaryDirectory() as tmp:
   a=self.make(tmp);cfg=dict(CFG,rsi_length=14,ma_length=14,ma_type='EMA');ident=digest(cfg);a.state['library'][ident]=dict(config=cfg,settings=SETTINGS,product={},context='new',evidence={'eligible':True});a.state['holdout']={'result':dict(candidate_id=ident,context='old',metrics={'trades':20,'net_pnl':10})};a.state['prospective']=[dict(config=cfg,context='old',adaptive={'trades':50,'net_pnl':20})];proposal=a.proposal(ident);self.assertEqual(proposal['prospective_trades'],0);self.assertEqual(proposal['status'],'INSUFFICIENT_EVIDENCE')
 def test_forward_uses_frozen_costs_and_contract_specs(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as tmp:
   a=self.make(tmp);rows=candles(1400);start=rows[600]['timestamp'];cfg=dict(CFG,rsi_length=14,ma_length=14,ma_type='EMA');a.state['pending_forward']=dict(created_at=start-60,start=start,end=start+6000,config=cfg,baseline=cfg,settings=SETTINGS,units=2,tick=.25,warmup=300,context='frozen');result=dict(warmup=300,selected_config=cfg,baseline_config=cfg);calls=[]
   def simulate_stub(*args):calls.append(args);return {'metrics':{'trades':2,'net_pnl':1}}
   with patch('sector_heatmap.delta_adaptive.simulate',side_effect=simulate_stub):a._forward(rows,{},dict(DEFAULTS,resolution='1m'),dict(SETTINGS,fee_bps=100),{'end':rows[0]['timestamp']},result,99,9)
   self.assertEqual(len(calls),2);self.assertEqual(calls[0][4:7],(SETTINGS,2,.25));self.assertEqual(a.state['prospective'][0]['context'],'frozen')
