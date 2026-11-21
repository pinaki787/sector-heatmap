import json, subprocess, tempfile, unittest
from pathlib import Path
from .signals import Engine, settings
from .entry_qualification import check, events
from .exit_indicators import reason
from .brick_entry import allowed
from . import preferences
from . import test_loss_range as lock_tests

CONFIG=dict(strategy_mode='SIMPLE_BRICK',strategy_basis='RENKO',brick_mode='Manual',manual_brick=10,
            swing_breakout_enabled=False,session_deadline='',supertrend_enabled=True,ema_fast_enabled=True,
            rsi_slope_enabled=True,supertrend_exit_enabled=True,ema_exit_enabled=True)

class SimpleBrick(unittest.TestCase):
 def test_color_lifecycle_and_no_brick_no_entry(self):
  e=Engine(CONFIG);rows=[]
  for i,price in enumerate([100,110,120,130,125,110,100,90,110,120]):
   rows.append(e.update(dict(timestamp=1793840400+i*300,open=price,high=price,low=price,close=price)))
  self.assertFalse(rows[4]['has_completed_brick'])
  self.assertFalse(rows[4]['entry_qualified'])
  actual=[(b['lifecycle_event'],b['close']) for r in rows for b in r['brick_events'] if b.get('lifecycle_event')]
  self.assertEqual(actual,[('SELL',100),('SELL EXIT',110),('BUY',120)])
  self.assertEqual(rows[1]['entry_diagnostic'],'WAITING_SMA')
  self.assertEqual([b['lifecycle_event'] for b in events(rows,CONFIG)], [x[0] for x in actual])
  for r in rows:
   for b in r['brick_events']:
    sig={**b,'has_completed_brick':True}
    self.assertTrue(allowed(CONFIG,sig,b['brick_direction']))
    sma=b['sma']
    aligned=sma is not None and (b['close'] > sma if b['brick_direction']=='BULLISH' else b['close'] < sma)
    self.assertEqual(check(CONFIG,sig,b['brick_direction'])['allowed'],aligned)
 def test_sma_lifecycle_uses_completed_brick_closes(self):
  config={**CONFIG,'sma_entry_enabled':True,'sma_exit_enabled':True,'sma_length':6}
  engine=Engine(config)
  prices=[100, 160, 159, 140, 130, 120, 110, 100, 120, 130]
  rows=[engine.update(dict(timestamp=1793840400+i*300,open=p,high=p,low=p,close=p))
        for i,p in enumerate(prices)]
  self.assertEqual([brick['sma'] for brick in rows[1]['brick_events']],
                   [None,None,None,None,None,135])
  self.assertEqual(rows[1]['entry_direction'],'BULLISH')
  self.assertFalse(rows[2]['has_completed_brick'])
  self.assertIsNone(reason(config,rows[2],'BULLISH'))
  self.assertEqual(rows[3]['sma'],rows[3]['close'])
  self.assertIsNone(reason(config,rows[3],'BULLISH'))
  self.assertEqual(reason(config,rows[4],'BULLISH'),'SMA6_CONFIRMED_BREACH')
  self.assertIsNone(reason(config,{**rows[4],'provisional':True},'BULLISH'))
  self.assertEqual(reason(config,rows[-1],'BEARISH'),'SMA6_CONFIRMED_BREACH')
  self.assertEqual([(row['lifecycle_event'],row['close']) for row in events(rows,config)],
                   [('BUY',160),('BUY EXIT',130),('SELL',120),('SELL EXIT',130)])

 def test_only_completed_opposite_exits(self):
  sig=dict(has_completed_brick=True,brick_direction='BEARISH',close=90,ema30=100,supertrend_cross_direction='BEARISH')
  for side in ('BULLISH','BEARISH'):
   opposite='BEARISH' if side=='BULLISH' else 'BULLISH'
   s={**sig,'brick_direction':opposite}
   self.assertEqual(reason(CONFIG,s,side),'OPPOSITE_RENKO_BRICK_CLOSE')
   for flag in ('provisional','is_forming'):
    self.assertIsNone(reason(CONFIG,{**s,flag:True},side))
   self.assertIsNone(reason(CONFIG,{**s,'brick_direction':side},side))
   self.assertIsNone(reason(CONFIG,{**s,'has_completed_brick':False},side))
 def test_browser_runtime_gate_parity_and_optional_swing(self):
  sig=dict(open=100,close=110,sma=105,sma_length=5,entry_qualified=True,has_completed_brick=True,brick_direction='BULLISH',pine_direction=1)
  cases=[(CONFIG,sig,'BULLISH'),({**CONFIG,'swing_breakout_enabled':True,'swing_breakout_bricks':2},sig,'BULLISH'),
         (CONFIG,{**sig,'provisional':True},'BULLISH'),
         ({**CONFIG,'strategy_mode':'SUPERTREND','swing_breakout_enabled':False},sig,'BULLISH')]
  disabled={**CONFIG,'sma_entry_enabled':False}
  bearish={**sig,'open':120,'brick_direction':'BEARISH','sma':115}
  cases.extend([(disabled,{**sig,'sma':115},'BULLISH'),
                (disabled,{**sig,'sma':110},'BULLISH'),
                (disabled,{**sig,'sma':None},'BULLISH'),
                (disabled,{**bearish,'sma':105},'BEARISH'),
                (disabled,bearish,'BEARISH')])
  root=Path(__file__).resolve().parents[2]
  code="const m=require('./renko-supertrend.js'),fs=require('fs');process.stdout.write(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(([c,s,d])=>m.strategyEntryCheck(c,s,d))));"
  browser=json.loads(subprocess.check_output(['node','-e',code],cwd=root,input=json.dumps(cases).encode()))
  self.assertEqual(browser,[check(c,s,d) for c,s,d in cases])
  self.assertEqual([item['allowed'] for item in browser],
                   [True,False,False,False,False,False,False,False,True])
 def test_preferences_roundtrip(self):
  values={'symbol':'NSE:NIFTY50-INDEX','strategy-mode':'SIMPLE_BRICK','strategy-basis':'RENKO','swing-breakout-enabled':False,'swing-levels-visible':True,'swing-breakout-bricks':2}
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'settings.json';preferences.write(path,{'settings':values},1)
   self.assertEqual(preferences.read(path)['settings'],values)
 def test_legacy_mode_is_retained(self):
  self.assertEqual(settings({'strategy_basis':'RENKO'})['strategy_mode'],'SUPERTREND')

class SimpleRangeLock(lock_tests.ContinuationLock):
 def scenario(self):
  sig=super().scenario()
  self.r.state['config'].update(strategy_mode='SIMPLE_BRICK',swing_breakout_enabled=False,
    supertrend_enabled=False,supertrend_slope_enabled=False,ema_fast_enabled=False,ema_slow_enabled=False,ema_third_enabled=False,rsi_slope_enabled=False)
  return sig
