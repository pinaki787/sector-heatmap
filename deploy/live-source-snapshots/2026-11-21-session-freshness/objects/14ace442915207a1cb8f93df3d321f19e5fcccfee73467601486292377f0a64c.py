import tempfile,time,unittest,json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from .option_premium import choose,settings
from .runner import configuration
from .test_runner import RenkoLifecycleTests

class SelectionTests(unittest.TestCase):
 def setUp(self):
  self.now=time.time();self.expiry=int(self.now+86400)
  self.config={'underlying':'NSE:NIFTY50-INDEX','execution_route':'OPTIONS','target_option_premium':100}
  self.atm={'symbol':'ATM','strike':100,'option_type':'CE','expiry_epoch':self.expiry,'lot_size':1}
  def row(symbol,strike,kind='CE',expiry=None):
   r=['']*17;r[3]='1';r[4]='.05';r[8]=str(expiry or self.expiry);r[9]=symbol;r[13]='NIFTY';r[15]=str(strike);r[16]=kind;return r
  self.rows=[row('ATM',100),row('NEAR',110),row('FAR',120),row('WRONG_SIDE',110,'PE'),row('LATER',110,expiry=self.expiry+86400)]
  self.quotes={symbol:{'bid':ask-1,'ask':ask,'received_at':self.now,'exchange_at':self.now} for symbol,ask in [('ATM',160),('NEAR',102),('FAR',90),('WRONG_SIDE',100),('LATER',100)]}
  host=['']*17;host[13]='NIFTY'
  self.b=SimpleNamespace(underlying=lambda symbol:host,rows=lambda segment:self.rows,quote=lambda symbol:self.quotes[symbol],contract=lambda symbol:{'symbol':symbol,'quantity_multiplier':1,'lot_size':1,'tick_size':.05})
 def test_closest_ask_uses_same_direction_and_nearest_expiry(self):
  r=choose(self.b,self.config,self.atm)
  self.assertEqual(r['symbol'],'NEAR');self.assertEqual(r['premium_selection']['selected_ask'],102)
  self.assertEqual(r['premium_selection']['candidate_count'],3)
 def test_blank_keeps_atm_without_extra_quote_requests(self):
  self.b.quote=Mock(side_effect=AssertionError('Blank must not scan quotes'))
  self.assertIs(choose(self.b,{**self.config,'target_option_premium':''},self.atm),self.atm)
 def test_stale_or_missing_quotes_never_become_zero_or_fallback_atm(self):
  for q in self.quotes.values():q['received_at']=self.now-30
  with self.assertRaisesRegex(ValueError,'warming'):choose(self.b,self.config,self.atm)
 def test_bad_or_crossed_quote_is_excluded(self):
  self.quotes['NEAR']['bid']=500
  self.assertEqual(choose(self.b,self.config,self.atm)['symbol'],'FAR')
 def test_tie_is_deterministic_by_distance_to_atm(self):
  self.quotes['ATM']['ask']=110;self.quotes['ATM']['bid']=109
  self.quotes['NEAR']['ask']=90;self.quotes['NEAR']['bid']=89
  self.assertEqual(choose(self.b,self.config,self.atm)['symbol'],'ATM')
 def test_positive_finite_optional_and_index_only_validation(self):
  for value in [0,-1,True,'nan','inf','bad']:
   with self.assertRaises(ValueError):settings({**self.config,'target_option_premium':value})
  for symbol in ['NSE:LAURUSLABS-EQ','MCX:GOLD26DECFUT','BTCUSD']:
   with self.assertRaisesRegex(ValueError,'index options'):settings({**self.config,'underlying':symbol})
  for broker in ['DHAN','MOTILAL_OSWAL','DELTA_INDIA']:
   with self.assertRaises(ValueError):settings({**self.config,'broker':broker})
  self.assertEqual(settings({**self.config,'underlying':'BSE:SENSEX-INDEX','target_option_premium':'125.50'})['target_option_premium'],125.5)
 def test_non_index_saved_preferences_do_not_carry_hidden_target(self):
  from .binding import normalize_settings
  self.assertNotIn('target-premium',normalize_settings({'symbol':'NSE:TEST-EQ','target-premium':'100'},broker='FYERS'))
 def test_preferences_roundtrip_and_configuration_keep_optional_target(self):
  from .preferences import write,read
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'settings.json'
   write(p,{'settings':{'symbol':'NSE:NIFTY50-INDEX','target-premium':'100'}},self.now,scope={'broker':'FYERS','instrument':'NSE:NIFTY50-INDEX'})
   self.assertEqual(read(p)['settings']['target-premium'],'100')

class ConfigTests(RenkoLifecycleTests):
 def test_target_premium_reaches_active_configuration(self):
  self.c.update(target_option_premium='123.45')
  self.start()
  self.assertEqual(self.r.state['config']['target_option_premium'],123.45)
