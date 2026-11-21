import datetime,unittest
from zoneinfo import ZoneInfo
from expiry_calendar import expected_weekly_expiry
from replay import aggregate,atm_strike,fixed_quote,simulate
Z=ZoneInfo('Asia/Kolkata')
class ReplayTests(unittest.TestCase):
 def test_aggregate_never_exposes_forming_or_gapped_higher_bar(self):
  start=int(datetime.datetime(2026,10,8,9,15,tzinfo=Z).timestamp())
  rows=[dict(timestamp=start+i*300,open=100,high=102,low=99,close=101,volume=1) for i in range(6)]
  self.assertEqual(len(aggregate(rows[:2],15)),0)
  self.assertEqual(len(aggregate(rows[:3],15)),1)
  self.assertEqual(aggregate(rows[:4],15),aggregate(rows[:3],15))
  self.assertEqual(aggregate([rows[0],rows[2],rows[3]],15),[])
 def fixture(self,bearish=False,missing=False,trailing=False,current_volume=10,mtf_future=False,contraction=False,proximity=False,far_ema=False,quick_loss=False):
  start=int(datetime.datetime(2026,10,8,9,15,tzinfo=Z).timestamp());rows=[];signals=[];quotes={}
  direction='BEARISH' if bearish else 'BULLISH';side='PUT' if bearish else 'CALL'
  for i in range(75):
   t=start+i*300;price=22500 if i<2 else 22560
   rows.append(dict(timestamp=t,open=price,high=price+5,low=price-5,close=price,volume=1))
   signals.append(dict(direction=direction,entry_direction=direction if i==0 or quick_loss and i==3 else None,entry_qualified=i==0 or quick_loss and i==3,raw_supertrend_cross_direction=('BULLISH' if bearish else 'BEARISH') if ((i in (1,4) if quick_loss else i==2) and not trailing) else None,ema10=price-100 if far_ema else price,ema30=price,ema_gap=.5 if contraction and i==2 else 1,host_atr=10))
   premium=([100,105,90,95,100,105][min(i,5)] if quick_loss else [100,105,130,110,110][min(i,4)] if trailing else 100+i*5)
   quotes[t,side,22500.]=dict(open=premium,close=premium,buy=premium,sell=premium,buy_fee=2,sell_fee=2,volume=10 if i==0 else current_volume)
   quotes[t,side,22550.]=dict(open=500,close=500,buy=500,sell=500,buy_fee=2,sell_fee=2,volume=10)
  if missing:quotes.pop((start+900,side,22500.))
  risk=dict(exit='EMA30' if contraction else 'ST',sideways=quick_loss,trailing=trailing,proximity=proximity,contraction=contraction,zones=False,rsi_mtf=mtf_future)
  context=([start+1800],[{'rsi14':90,'rsi14_slope':10}]) if mtf_future else ([],[])
  return simulate(rows,signals,quotes,{},risk,[],context,{'test':{'2026-10-08'}},True)
 def test_contract_is_fixed_when_atm_moves(self):
  r=self.fixture();self.assertTrue(r['valid']);t=r['trades']['test'][0]
  self.assertEqual(t['strike'],22500);self.assertEqual(t['sell'],115);self.assertEqual(t['net'],646)
 def test_bearish_signal_buys_put_and_gains_when_premium_rises(self):
  t=self.fixture(True)['trades']['test'][0];self.assertEqual(t['side'],'PUT');self.assertGreater(t['net'],0)
 def test_missing_held_contract_invalidates_instead_of_rolling(self):
  r=self.fixture(missing=True);self.assertFalse(r['valid']);self.assertEqual(r['problems'][0]['type'],'MISSING_HELD_CONTRACT')
 def test_current_candle_future_volume_does_not_gate_open_fill(self):
  r=self.fixture(current_volume=0);self.assertEqual(r['metrics']['test']['trades'],1)
 def test_bought_put_trails_premium_upward(self):
  r=self.fixture(bearish=True,trailing=True);self.assertTrue(r['valid']);t=r['trades']['test'][0];self.assertEqual(t['exit_reason'],'SAMPLED_PREMIUM_TRAILING');self.assertEqual(t['sell'],110)
 def test_forming_higher_timeframe_rsi_cannot_authorize_entry(self):
  r=self.fixture(mtf_future=True);self.assertTrue(r['valid']);self.assertEqual(r['metrics']['test']['trades'],0)
 def test_holiday_expiry_moves_to_previous_trading_day(self):
  self.assertEqual(expected_weekly_expiry(datetime.date(2026,4,13)),'2026-04-13')
  self.assertEqual(expected_weekly_expiry(datetime.date(2026,4,15)),'2026-04-21')
 def test_unverified_calendar_year_is_rejected(self):
  with self.assertRaises(ValueError):expected_weekly_expiry(datetime.date(2027,1,1))
 def test_contraction_exit_works_without_ema_breach(self):
  r=self.fixture(contraction=True);self.assertTrue(r['valid']);self.assertEqual(r['trades']['test'][0]['exit_reason'],'EMA_GAP_CONTRACTION')
 def test_disabled_proximity_does_not_gate_entry(self):
  self.assertEqual(self.fixture(far_ema=True)['metrics']['test']['trades'],1)
  self.assertEqual(self.fixture(far_ema=True,proximity=True)['metrics']['test']['trades'],0)
 def test_quick_losing_trade_locks_subsequent_inside_range_entry(self):
  r=self.fixture(quick_loss=True);self.assertTrue(r['valid']);self.assertEqual(r['metrics']['test']['trades'],1);self.assertLess(r['trades']['test'][0]['net'],0)
 def test_atm_uses_entry_observation(self):self.assertEqual(atm_strike(22526),22550)
if __name__=='__main__':unittest.main()
