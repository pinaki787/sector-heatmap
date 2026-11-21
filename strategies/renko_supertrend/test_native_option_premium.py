import unittest,time
from types import SimpleNamespace
from unittest.mock import Mock
from .option_premium import choose_native,settings
from .binding import normalize_settings
from sector_heatmap.dhan_strategy_broker import Broker as Dhan
from sector_heatmap.motilal_strategy_broker import Broker as Motilal

class NativePremiumTests(unittest.TestCase):
 def setUp(self):
  self.now=time.time();self.config=dict(broker='DHAN',underlying='NSE:NIFTY',target_option_premium=40,execution_route='OPTIONS')
  self.contracts=[dict(symbol='ATM',strike=100),dict(symbol='OTM',strike=110)]
  self.quotes={s:dict(bid=p-.2,ask=p,received_at=self.now,exchange_at=self.now) for s,p in [('ATM',100),('OTM',40)]}
  self.adapter=SimpleNamespace(clock=lambda:self.now,premium_quotes=Mock(side_effect=lambda rows:self.quotes))
 def test_reentry_reselects_current_target_instead_of_reusing_atm_or_old_contract(self):
  first=choose_native(self.adapter,self.config,self.contracts,100)
  self.assertEqual(first['symbol'],'OTM')
  self.quotes['ATM']['ask']=40;self.quotes['ATM']['bid']=39.8;self.quotes['OTM']['ask']=70;self.quotes['OTM']['bid']=69.8
  second=choose_native(self.adapter,self.config,self.contracts,100)
  self.assertEqual(second['symbol'],'ATM');self.assertEqual(second['premium_selection']['target_premium'],40)
  self.assertEqual(self.adapter.premium_quotes.call_count,2)
  self.assertEqual(self.adapter.resolved_contracts['ATM']['premium_selection']['selected_ask'],40)
 def test_missing_stale_crossed_or_future_quotes_cannot_fallback(self):
  for invalid in [None,dict(bid=50,ask=40,received_at=self.now,exchange_at=self.now),dict(bid=39,ask=40,received_at=self.now-16,exchange_at=self.now),dict(bid=39,ask=40,received_at=self.now+1,exchange_at=self.now)]:
   self.adapter.premium_quotes.return_value=None;self.adapter.premium_quotes.side_effect=lambda rows:{'ATM':invalid,'OTM':invalid}
   with self.assertRaisesRegex(ValueError,'no ATM fallback'):choose_native(self.adapter,self.config,self.contracts,100)
 def test_scope_and_saved_target(self):
  for broker in ['DHAN','MOTILAL_OSWAL']:
   self.assertEqual(settings({**self.config,'broker':broker})['target_option_premium'],40)
   self.assertEqual(normalize_settings({'symbol':'NSE:NIFTY','target-premium':'40'},broker=broker)['target-premium'],'40')
   with self.assertRaises(ValueError):settings({**self.config,'broker':broker,'execution_route':'CASH_EQUITY'})
 def dhan(self):
  b=Dhan.__new__(Dhan);b.clock=lambda:self.now;b.contracts={};b.entry_spread_filter_enabled=False
  b.underlying=lambda s:dict(SEM_EXM_EXCH_ID='NSE',SEM_SEGMENT='I',SEM_TRADING_SYMBOL='NIFTY')
  b.live_price=lambda c,n:(100,n)
  expiry='2099-01-01'
  rows=[dict(SEM_EXM_EXCH_ID='NSE',SEM_SEGMENT='D',SEM_TRADING_SYMBOL=f'NIFTY-20990101-{strike}-{kind}',SEM_OPTION_TYPE=kind,SEM_EXPIRY_DATE=date,SEM_STRIKE_PRICE=str(strike),id=symbol) for symbol,strike,kind,date in [('ATM',100,'CE',expiry),('OTM',110,'CE',expiry),('WRONG',110,'PE',expiry),('LATER',110,'CE','2099-02-01')]]
  b._rows=lambda:rows;b._meta=lambda row:dict(symbol=row['id'],option_type=row['SEM_OPTION_TYPE'],strike=float(row['SEM_STRIKE_PRICE']),expiry=row['SEM_EXPIRY_DATE'])
  b.premium_quotes=self.adapter.premium_quotes
  return b
 def test_dhan_real_resolver_honors_target_and_blank_keeps_atm(self):
  b=self.dhan();selected=b.resolve(self.config,'BULLISH');self.assertEqual(selected['symbol'],'OTM')
  candidates=b.premium_quotes.call_args.args[0];self.assertEqual({r['symbol'] for r in candidates},{'ATM','OTM'})
  b.premium_quotes.reset_mock();self.assertEqual(b.resolve({**self.config,'target_option_premium':None},'BULLISH')['symbol'],'ATM');b.premium_quotes.assert_not_called()
 def test_dhan_single_batched_request_and_delayed_response_rejected(self):
  b=Dhan.__new__(Dhan);b.clock=lambda:self.now;b.entry_spread_filter_enabled=False
  request=Mock(return_value={'data':{'NSE_FNO':{str(i):{'depth':{'buy':[{'price':39}], 'sell':[{'price':40}]}} for i in (1,2)}}})
  b.service=SimpleNamespace(_client=lambda:SimpleNamespace(request=request))
  contracts=[dict(symbol=str(i),security_id=str(i),exchange_segment='NSE_FNO') for i in (1,2)]
  self.assertEqual(len(b.premium_quotes(contracts)),2);request.assert_called_once_with('POST','/marketfeed/quote',{'NSE_FNO':[1,2]})
  request.return_value['_sector_snapshot_timing']={'received_at':self.now,'elapsed':16}
  with self.assertRaisesRegex(ValueError,'delayed'):b.premium_quotes(contracts)
 def test_motilal_real_resolver_honors_same_target(self):
  b=Motilal.__new__(Motilal);b.clock=lambda:self.now;b.live_price=lambda c,n:(100,n);b.subscribe=Mock()
  b.option_rows=lambda s:[dict(row,option_type='CE',expiry='2099-01-01') for row in self.contracts]
  b.contract=lambda s:next(row for row in b.option_rows('') if row['symbol']==s)
  b.quote=lambda s:self.quotes[s]
  selected=b.resolve({**self.config,'broker':'MOTILAL_OSWAL','underlying':'NSE:NIFTY50-INDEX'},'BULLISH')
  self.assertEqual(selected['symbol'],'OTM');self.assertEqual(selected['premium_selection']['target_premium'],40)
