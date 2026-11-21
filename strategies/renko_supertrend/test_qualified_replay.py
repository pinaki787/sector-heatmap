import unittest,json,subprocess
from copy import deepcopy
from pathlib import Path
from .entry_qualification import check,events

CONFIG=dict(strategy_basis='RENKO',swing_breakout_bricks=2,supertrend_enabled=True,supertrend_slope_enabled=True,supertrend_slope_bars=1,supertrend_slope_min_atr=0,ema_third_enabled=True)
def signal(side='BULLISH',**kw):
 return dict(timestamp=1,open=100 if side=='BULLISH' else 120,close=110,entry_qualified=True,has_completed_brick=True,brick_direction=side,pine_direction=-1 if side=='BULLISH' else 1,ema100=90 if side=='BULLISH' else 130,supertrend_slope_filter=dict(allowed=True,lookback=1,slope_atr=1 if side=='BULLISH' else -1),swing_breakout={'sides':{side:dict(allowed=True,required=2,count=2,reference={'price':100 if side=='BULLISH' else 120})}},**kw)

class QualifiedReplayTests(unittest.TestCase):
 def test_entry_rejection_has_no_exit_and_valid_exit_needs_no_new_entry_qualification(self):
  rows=[]
  for event,qualified in [('SELL',False),('SELL EXIT',False),('BUY',True),('BUY EXIT',False)]:
   side='BULLISH' if event.startswith('BUY') else 'BEARISH';s=signal(side);s.update(lifecycle_event=event,entry_qualified=qualified)
   rows.append({'timestamp':1,'strategy_basis':'RENKO','brick_events':[s]})
  self.assertEqual([r['lifecycle_event'] for r in events(rows,CONFIG)],['BUY','BUY EXIT'])
 def test_browser_and_shared_engine_core_gate_agree(self):
  cases=[]
  for side in ('BULLISH','BEARISH'):
   good=signal(side);cases.append([CONFIG,good,side])
   for key,value in [('entry_qualified',False),('provisional',True),('has_completed_brick',False),('ema100',110),('pine_direction',1 if side=='BULLISH' else -1),('swing_breakout',None),('supertrend_slope_filter',{'allowed':True,'lookback':1,'slope_atr':0})]:
    s=deepcopy(good);s[key]=value;cases.append([CONFIG,s,side])
   for flag,key in [('market_structure_enabled','market_structure'),('higher_timeframe_enabled','mtf_supertrend'),('anti_chop_enabled','anti_chop'),('zone_entry_enabled','zone_entry_filter')]:
    c={**CONFIG,flag:True};cases.append([c,good,side]);cases.append([c,{**good,key:{'allowed':True}},side])
  code="const fs=require('fs'),m=require('./renko-supertrend.js');process.stdout.write(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(([c,s,d])=>m.strategyEntryCheck(c,s,d))));"
  root=Path(__file__).resolve().parents[2]
  actual=json.loads(subprocess.check_output(['node','-e',code],cwd=root,input=json.dumps(cases).encode()))
  self.assertEqual(actual,[check(c,s,d) for c,s,d in cases])
 def test_shared_engine_records_final_certificate_and_complete_per_brick_values(self):
  from .signals import Engine
  e=Engine({**CONFIG,'brick_mode':'Manual','manual_brick':1,'strategy_basis':'RENKO','ema_fast_enabled':False,'ema_slow_enabled':False,'ema_third_length':2,'ema_widening_enabled':False,'rsi_slope_enabled':False},1)
  for i,p in enumerate([100,103,106,103,100,103,107,110]):row=e.update({'timestamp':100+i*300,'open':p,'high':p,'low':p,'close':p})
  self.assertTrue(row['brick_events'])
  for b in row['brick_events']:
   for key in ('strategy_entry_check','pine_direction','adx','rsi14_slope','ema100','swing_breakout'):self.assertIn(key,b)
   if b.get('lifecycle_event') in ('BUY','SELL'):self.assertTrue(b['strategy_entry_check']['allowed'])
