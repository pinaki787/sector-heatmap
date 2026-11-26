import unittest
from sma_band import BandPolicy
from core import Strategy
from direct import DirectStrategy
class RetestTests(unittest.TestCase):
 def config(self,**extra):
  return dict(reference_value=120,market='NSE',underlying='NSE:TEST-EQ',timeframe=1,product='INTRADAY',sma_band_period=2,sma_band_entry=True,sma_band_exit=True,**extra)
 def event(self,i,o=95,h=100,l=90,c=95):
  return dict(kind='underlying',timestamp=1000+60*i,closed_at=1060+60*i,available_at=1061+60*i,open=o,high=h,low=l,close=c,closed=True,body_available=True,source_basis='PROVIDER_CONFIRMED_CLOSE')
 def setup_band(self):
  c=self.config();b=BandPolicy(c)
  for i in range(2):b.observe(self.event(i),c)
  return c,b
 def observe(self,b,c,event,result,flat=True):
  b.observe(event,c);return b.reentry(event,c,result,flat=flat)
 def test_bullish_retest_requires_next_green_close_above_band(self):
  c,b=self.setup_band();r=dict(direction=-1,st=90)
  self.assertIsNone(self.observe(b,c,self.event(2,105,106,99,100),r))
  self.assertEqual(self.observe(b,c,self.event(3,101,109,100,108),r)['confirmation_basis'],'SMA_RETEST_FOLLOWUP_CANDLE')
  self.assertIsNone(self.observe(b,c,self.event(4,108,112,107,111),r))
 def test_bearish_mirror(self):
  c,b=self.setup_band();r=dict(direction=1,st=110)
  self.assertIsNone(self.observe(b,c,self.event(2,85,91,84,90),r))
  self.assertEqual(self.observe(b,c,self.event(3,88,89,80,81),r)['direction'],'SHORT')
 def test_missing_followup_wrong_color_gap_or_trend_change_reject(self):
  for mode in ['red','gap','trend','forming']:
   c,b=self.setup_band();r=dict(direction=-1,st=90)
   self.observe(b,c,self.event(2,105,106,99,100),r)
   event=self.event(4 if mode=='gap' else 3,101,109,100,108)
   if mode=='red':event.update(open=109,high=110)
   if mode=='forming':event['closed']=False
   self.assertIsNone(self.observe(b,c,event,dict(direction=1,st=120) if mode=='trend' else r))
 def test_position_and_disabled_exit_cannot_reenter(self):
  for flat,exit_enabled in [(False,True),(True,False)]:
   c,b=self.setup_band();c['sma_band_exit']=exit_enabled;r=dict(direction=-1,st=90)
   self.observe(b,c,self.event(2,105,106,99,100),r,flat)
   self.assertIsNone(self.observe(b,c,self.event(3,101,109,100,108),r,flat))
 def test_tick_cannot_replace_followup_candle(self):
  c,b=self.setup_band();r=dict(direction=-1,st=90)
  self.observe(b,c,self.event(2,105,106,99,100),r)
  self.assertIsNone(self.observe(b,c,dict(kind='price',series='underlying',timestamp=1181,close=108),r))
  self.assertEqual(self.observe(b,c,self.event(3,101,109,100,108),r)['direction'],'LONG')
 def test_option_underlying_reentry_without_new_flip_or_premium_bullish(self):
  e=Strategy(self.config(entry_gate='underlying_flip'));e.reset_contract(dict(symbol='CE',option_type='CE'),.2)
  for i in range(2):e.band.observe(self.event(i),e.config)
  e.under_result=dict(direction=-1,st=90);e.premium_result=dict(direction=1,st=200)
  self.assertEqual(e.update_hybrid(self.event(2,105,106,99,100)),[])
  actions=e.update_hybrid(self.event(3,101,109,100,108))
  self.assertEqual(actions[0]['action'],'BUY')
  self.assertEqual(e.update_hybrid(self.event(4,108,112,107,111)),[])
 def test_pre_exit_retest_body_cannot_be_replayed_after_exit(self):
  c,b=self.setup_band();r=dict(direction=-1,st=90)
  event=self.event(2,105,106,99,100);b.observe(event,c)
  self.assertIsNone(b.reentry(event,c,r,not_before=event['closed_at']+1))
  self.assertIsNone(self.observe(b,c,self.event(3,101,109,100,108),r))
 def test_direct_reentry_without_fresh_flip(self):
  e=DirectStrategy(self.config())
  for i in range(2):e.band.observe(self.event(i),e.config)
  e.under_result=dict(direction=-1,st=90)
  self.assertEqual(e.update_hybrid(self.event(2,105,106,99,100)),[])
  actions=e.update_hybrid(self.event(3,101,109,100,108))
  self.assertEqual(actions[0]['action'],'OPEN_LONG')
  self.assertEqual(actions[0]['confirmation']['confirmation_basis'],'SMA_RETEST_FOLLOWUP_CANDLE')
if __name__=='__main__':unittest.main()
