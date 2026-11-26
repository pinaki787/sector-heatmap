"""MCX contract selection, sessions and no-submit execution regressions."""
import tempfile,unittest
from datetime import datetime
from unittest.mock import Mock,patch
from pathlib import Path
import live
from markets import IST,SourceBars
from execution import Execution
from session_wait import SessionWait
class MCXTests(unittest.TestCase):
 def test_chain_delivery_strike_and_exchange_validation(self):
  expiry='4102444800';under='MCX:CRUDEOILM26DECFUT'
  config=dict(underlying=under,market='MCX',reference_value=280,option_moneyness='ATM')
  api=Mock();api.optionchain.return_value=dict(s='ok',data=dict(expiryData=[dict(expiry=expiry)],optionsChain=[dict(symbol=under,ex_symbol='CRUDEOILM',ltp=7565),dict(symbol='MCX:CALL',option_type='CE',strike_price=7550,ltp=400,greeks=dict(delta=.5))]))
  meta=dict(expiry_epoch=expiry,option_type='CE',underlying_asset='CRUDEOILM',underlying_token='576265',lot_size=1,strike_price=7550)
  with patch('markets.FyersInstrumentMaster',return_value=lambda s:dict(instrument_token='576265')):
   contract,_=live.choose(api,lambda s:meta,config,'CE')
   self.assertEqual(contract['lot_size'],1);self.assertEqual(contract['strike_price'],7550)
   for changes,message in [(dict(underlying_token='OTHER'),'another MCX future'),(dict(strike_price=7600),'strike mismatch')]:
    with self.assertRaisesRegex(ValueError,message):live.choose(api,lambda s:dict(meta,**changes),config,'CE')
 def test_equity_and_mcx_evening_and_midnight_sessions(self):
  for opening,closing,expected in [(555,930,False),(540,1435,True),(540,1410,True)]:
   at=datetime(2026,11,25,20,tzinfo=IST).timestamp();check=Mock(return_value=True)
   session=SessionWait(check,opening,closing,clock=lambda:at)
   self.assertEqual(session.poll(),expected)
  for hour,minute in [(0,0),(8,59),(23,55)]:
   at=datetime(2026,11,25,hour,minute,tzinfo=IST).timestamp()
   self.assertFalse(SessionWait(lambda:True,540,1435,clock=lambda:at).poll())
 def test_holiday_status_and_short_session_override(self):
  at=datetime(2026,11,25,20,tzinfo=IST).timestamp()
  self.assertFalse(SessionWait(lambda:False,540,1435,clock=lambda:at).poll())
  self.assertFalse(SessionWait(lambda:True,540,1435,clock=lambda:at,bounds=lambda:dict(opening_minutes=540,closing_minutes=1100)).poll())
 def test_master_seasonal_hours_parser(self):
  self.assertEqual(live.regular_session('0900-2355|1815-1915:'),(540,1435))
  self.assertEqual(live.regular_session('0900-2330|1815-1915:'),(540,1410))
  with self.assertRaises(ValueError):live.regular_session('missing')
 def test_mcx_evening_history_retained_equity_history_excluded(self):
  at=datetime(2026,11,25,20,tzinfo=IST).timestamp();reply=dict(s='ok',candles=[[at,100,101,99,100,1]])
  with patch('sector_heatmap.fyers_history.history',return_value=reply),patch('live.time.time',return_value=at+3600),patch('live.session_bounds',return_value=(540,1435)):
   self.assertEqual(len(live.history(Mock(),'MCX:CALL',5,'2026-11-25','2026-11-25')),1)
  with patch('sector_heatmap.fyers_history.history',return_value=reply),patch('live.time.time',return_value=at+3600):
   self.assertEqual(live.history(Mock(),'NSE:CALL',5,'2026-11-25','2026-11-25'),[])
 def test_no_overnight_mcx_candle_but_crypto_crosses_midnight(self):
  at=datetime(2026,11,25,23,50,tzinfo=IST).timestamp()
  source=SourceBars(5,opening_minutes=540,closing_minutes=1435,confirmed_closes=True)
  source.update(at,100)
  next_day=datetime(2026,11,26,9,tzinfo=IST).timestamp()
  self.assertIsNone(source.update(next_day,101))
  crypto=SourceBars(5,continuous=True,confirmed_closes=True)
  crypto.update(at+300,100);self.assertEqual(crypto.update(at+600,101),(at+300,100))
 def test_dry_payloads_all_fyers_option_exchanges(self):
  now=1800000000
  for exchange,lot in [('NSE',65),('BSE',20),('MCX',1)]:
   with self.subTest(exchange=exchange),tempfile.TemporaryDirectory() as folder:
    api=Mock();symbol=exchange+':CALL'
    meta=dict(lot_size=lot,tick_size=.05,expiry_epoch=str(now+86400),option_type='CE')
    execution=Execution(api,'offline',folder,lots=2,product='MARGIN',master=lambda s:meta)
    try:
     position=dict(symbol=symbol,option_type='CE',expiry=meta['expiry_epoch'],entry_timestamp=now)
     buy=execution.submit(dict(action='BUY',timestamp=now,position=position),dict(timestamp=now,ltp=40),now)
     sell=execution.submit(dict(action='SELL',timestamp=now+1,position=position),dict(timestamp=now+1,ltp=41),now+1)
     self.assertEqual(buy['payload']['qty'],2*lot);self.assertEqual(buy['payload']['type'],1);self.assertEqual(sell['payload']['side'],-1)
     api.place_order.assert_not_called()
    finally:execution.close()
if __name__=='__main__':unittest.main()


class MCXMarginTests(unittest.TestCase):
 def test_mcx_buy_uses_broker_margin_and_blocks_underfunding_before_submit(self):
  now=1800000000
  for required,allowed in [(4000,False),(500,True)]:
   with tempfile.TemporaryDirectory() as folder:
    api=Mock();api.positions.return_value=dict(s='ok',netPositions=[]);api.orderbook.return_value=dict(s='ok',orderBook=[])
    api.funds.return_value=dict(s='ok',fund_limit=[dict(id=10,equityAmount=100000,commodityAmount=1000)])
    api.place_order.side_effect=TimeoutError('offline sentinel')
    meta=dict(lot_size=1,tick_size=.05,expiry_epoch=str(now+86400),option_type='CE')
    execution=Execution(api,'offline',folder,live=True,lots=1,product='MARGIN',master=lambda s:meta,account_folder=Path(folder))
    action=dict(action='BUY',timestamp=now,position=dict(symbol='MCX:CALL',option_type='CE',expiry=meta['expiry_epoch'],entry_timestamp=now))
    try:
     with patch('markets.margin_reader',return_value=lambda payload:required):
      with self.assertRaises(RuntimeError if allowed else ValueError):execution.submit(action,dict(timestamp=now,ltp=40),now)
     self.assertEqual(api.place_order.call_count,int(allowed))
    finally:execution.close()
