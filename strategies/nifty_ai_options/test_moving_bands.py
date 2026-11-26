import unittest,tempfile,json
from pathlib import Path
from sma_band import MovingBand,BandPolicy,retain_broker_ohlc
from direct import DirectStrategy
from core import Strategy
from chart_source import ChartSource,read_source

class MovingBandTests(unittest.TestCase):
 def config(self,**extra):
  return dict(reference_value=12,market='NSE',underlying='NSE:TEST-EQ',timeframe=1,product='INTRADAY',sma_band_period=3,sma_band_entry=True,sma_band_exit=True,**extra)
 def event(self,i,close=100,high=110,low=90):
  return dict(kind='underlying',timestamp=1000+i*60,open=close,high=high,low=low,close=close,closed=True,closed_at=1060+i*60,available_at=1061+i*60,body_available=True,source_basis='PROVIDER_CONFIRMED_CLOSE')
 def test_sma_uses_high_low_not_body_or_close(self):
  b=MovingBand('SMA',3)
  for i,(high,low) in enumerate([(110,90),(120,80),(130,70)]):value=b.update(100+i,high,low,100)
  self.assertEqual((value['upper'],value['lower']),(120,80))
  value=b.update(103,140,60,100);self.assertEqual((value['upper'],value['lower']),(130,70))
 def test_ema_seed_and_recursion(self):
  b=MovingBand('EMA',3)
  for i in range(3):v=b.update(100+i,110,90,100)
  self.assertEqual(v['upper'],110)
  v=b.update(103,150,50,100);self.assertEqual((v['upper'],v['lower']),(130,70))
 def test_window_required_and_filters_use_both_bands_when_enabled(self):
  c=self.config(ema_band_period=3,ema_band_entry=True);p=BandPolicy(c)
  self.assertFalse(p.allows('LONG',c))
  for i in range(3):p.observe(self.event(i),c)
  self.assertFalse(p.allows('LONG',c));self.assertFalse(p.allows('SHORT',c))
  p.observe(dict(kind='price',series='underlying',timestamp=1300,close=120),c)
  self.assertFalse(p.allows('LONG',c));self.assertFalse(p.allows('CE',c));self.assertFalse(p.allows('PE',c))
  p.observe(dict(kind='price',timestamp=1301,close=80),c);self.assertFalse(p.allows('SHORT',c));self.assertFalse(p.allows('PE',c))
 def test_frame_change_clears_old_window_and_disabled_never_needs_ohlc(self):
  c=self.config();p=BandPolicy(c)
  for i in range(3):p.observe(self.event(i),c)
  self.assertTrue(p.snapshot(c)['bands'][0]['ready'])
  c=dict(c,timeframe=5);self.assertFalse(p.snapshot(c)['bands'][0]['ready'])
  p=BandPolicy(dict(timeframe=1));self.assertFalse(p.observe(dict(kind='underlying',timestamp=100,close=1),dict(timeframe=1)));self.assertTrue(p.allows('LONG',{}))
 def test_manual_direct_entry_bypasses_filter_but_band_exit_still_applies(self):
  for side,close,high,low,action in [('LONG',50,60,40,'CLOSE_LONG'),('SHORT',150,160,140,'CLOSE_SHORT')]:
   e=DirectStrategy(self.config())
   for i in range(3):e.update(self.event(i));e.position=None
   e.manual_entry(side,1200)
   actions=e.update_hybrid(self.event(4,close,high,low))
   self.assertEqual(actions[0]['action'],action);self.assertEqual(actions[0]['reason'],'OPTIONAL_UNDERLYING_SMA_BAND');self.assertIsNone(e.position)
 def test_old_pre_fill_candle_cannot_exit_new_manual_position(self):
  e=DirectStrategy(self.config())
  for i in range(3):e.update(self.event(i));e.position=None
  e.manual_entry('LONG',2000)
  self.assertEqual(e.update_hybrid(self.event(4,50,60,40)),[]);self.assertIsNotNone(e.position)
 def test_manual_call_and_put_are_exited_by_underlying_band(self):
  for side,close,high,low in [('CE',50,60,40),('PE',150,160,140)]:
   c=self.config();e=Strategy(c)
   for i in range(3):e.update(self.event(i));e.position=None
   e.reset_contract(dict(symbol=side,option_type=side,underlying=c['underlying']),.4 if side=='CE' else -.4)
   e.manual_entry(side,1200)
   actions=e.update_hybrid(self.event(4,close,high,low))
   self.assertEqual(actions[0]['action'],'SELL');self.assertEqual(actions[0]['position']['symbol'],side);self.assertIsNone(e.position)
 def test_invalid_or_missing_wicks_do_not_fabricate_band(self):
  p=BandPolicy(self.config())
  for i in range(3):p.observe(self.event(i),self.config())
  p.observe(dict(kind='underlying',timestamp=1300,close=100),self.config())
  self.assertFalse(p.allows('LONG',self.config()));self.assertIsNotNone(p.error)
  raw=[[100,100,110,90,101,1],[100,100,120,90,101,1]]
  self.assertIsNone(retain_broker_ohlc([[100,None,None,None,101,None]],raw)[0][2])
 def test_period_validation(self):
  for value in [True,0,501,2.5,'30']:
   with self.assertRaises(ValueError):BandPolicy(self.config(ema_band_period=value))
 def test_incremental_owned_band_source(self):
  with tempfile.TemporaryDirectory() as temp:
   data=Path(temp);owner='a'*32;run='test';directory=data/'runs'/owner/run;directory.mkdir(parents=True)
   config=dict(self.config(),account=owner);(directory/'config.json').write_text(json.dumps(config))
   e=DirectStrategy(config)
   rows=[]
   for i in range(3):
    event=self.event(i);e.update(event);e.position=None;rows.append([event['timestamp'],None,None,None,event['close'],None])
   source=ChartSource(directory/'chart-source');source.seed(config['underlying'],1,rows,1);source.seed_bands(e)
   first=read_source(data,owner,run,config['underlying'],1)
   self.assertEqual(first['moving_bands'][0]['bands'][0]['points'][-1]['upper'],110)
   event=self.event(3);e.update(event);source.append_bands(e,event)
   tail=read_source(data,owner,run,config['underlying'],1,after=first['confirmed_through'])
   self.assertEqual(len(tail['moving_bands']),1)
   self.assertNotIn('points',tail['moving_bands'][0]['bands'][0])
   empty=read_source(data,owner,run,config['underlying'],1,after=event['available_at'])
   self.assertEqual(empty['moving_bands'],[])
