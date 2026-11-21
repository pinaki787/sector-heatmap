import math,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from indicator import AIRenko,Traditional
from core import Strategy,SMAExit,sizes,select_contract
from run import normalize,six_hour
BASE=dict(reference_value=400,timeframe=5,entry_gate='underlying_flip',exit_supertrend='underlying')
class Tests(unittest.TestCase):
    def test_sizing(self):
        spot,option=sizes(400,-.23)
        self.assertEqual(spot,400/12)
        self.assertEqual(option,(400/12)*.23)
    def test_invalid_sizing(self):
        for value in (0,float('nan'),float('inf'),-1):
            with self.assertRaises(ValueError):sizes(value,.23)
        for delta in (0,2,float('nan'),True):
            with self.assertRaises(ValueError):sizes(400,delta)
    def test_close_source_conflicts_audit_unused_fields_but_reject_close_changes(self):
        from run import normalize_closes
        first=[100,10.15,10.7,10.15,10.6,29250];second=[100,10.2,10.7,10.15,10.6,29250]
        before=[list(first),list(second)]
        rows,audit=normalize_closes([first,second])
        self.assertEqual(rows,[[100,None,None,None,10.6,None]])
        self.assertEqual(audit['unused_ohlcv_conflict_timestamps'],[100]);self.assertFalse(audit['ohlc_available'])
        self.assertEqual([first,second],before)
        with self.assertRaisesRegex(ValueError,'CLOSE'):normalize_closes([first,[100,10.2,10.7,10.15,10.65,29250]])

    def test_selection_side_expiry(self):
        rows=[dict(symbol='a',ltp=39,option_type='CE',expiry='x'),dict(symbol='b',ltp=40,option_type='PE',expiry='x'),dict(symbol='c',ltp=40,option_type='CE',expiry='y')]
        self.assertEqual(select_contract(rows,'CE','x')['symbol'],'a')
    def test_selection_missing(self):
        with self.assertRaises(ValueError):select_contract([],'PE','x')
    def test_two_box_reversal(self):
        r=Traditional(10)
        self.assertEqual(r.update(100),[])
        self.assertEqual([b['close'] for b in r.update(130)],[110,120,130])
        self.assertEqual(r.update(119),[])
        self.assertEqual([b['close'] for b in r.update(100)],[110,100])
    def test_multi_brick(self):
        r=Traditional(1);r.update(100)
        self.assertEqual(len(r.update(110)),10)
    def test_manual_indicator_initialization(self):
        a=AIRenko(manual_brick=10)
        first=a.update(dict(high=100,low=100,close=100))
        self.assertEqual(first['direction'],1);self.assertEqual(first['synthetic_atr'],0)
        row=a.update(dict(high=120,low=100,close=120))
        self.assertEqual(row['synthetic_close'],120)
        self.assertEqual(row['synthetic_atr'],4)
        self.assertEqual(row['st'],100)
        self.assertEqual(row['direction'],-1)
    def test_pine_recurrence_matches_existing_port(self):
        # Disable additions; non-NSE host avoids project's /12 Auto override.
        from strategies.renko_supertrend.signals import Engine
        engine=Engine(dict(underlying='REFERENCE',session_deadline=None,rsi_slope_enabled=False,trend_reentry_enabled=False))
        own=AIRenko()
        for i in range(250):
            c=1000+80*math.sin(i*.13)+i*.2
            bar=dict(timestamp=1700000000+i*60,open=c-1,high=c+4,low=c-5,close=c,volume=1)
            expected=engine.update(bar);actual=own.update(bar)
            for key in ('synthetic_close','synthetic_open','synthetic_atr','effective_factor','host_atr'):
                if expected[key] is None:self.assertIsNone(actual[key])
                else:self.assertAlmostEqual(actual[key],expected[key],places=10)
            self.assertEqual('BULLISH' if actual['direction']<0 else 'BEARISH',expected['direction'])
    def test_optional_sma_default_off(self):
        s=Strategy(BASE)
        s.position=dict(side='CE')
        for i in range(40):self.assertEqual(s.update(dict(kind='sma',timestamp=i,close=100 if i<35 else 1)),[])
        self.assertIsNotNone(s.position)
    def test_optional_sma_independent(self):
        s=Strategy(dict(BASE,timeframe=30,sma_exit_enabled=True,sma_price_basis='underlying'))
        s.position=dict(side='CE')
        for i in range(30):self.assertEqual(s.update(dict(kind='sma',timestamp=i*60,close=100)),[])
        result=s.update(dict(kind='sma',timestamp=30*60,close=99))
        self.assertEqual(result[0]['action'],'SELL')
    def test_optional_sma_bearish(self):
        s=Strategy(dict(BASE,sma_exit_enabled=True,sma_price_basis='underlying'))
        s.position=dict(side='PE')
        for i in range(30):s.update(dict(kind='sma',timestamp=i*60,close=100))
        self.assertEqual(s.update(dict(kind='sma',timestamp=1800,close=101))[0]['action'],'SELL')
    def test_sma_requires_explicit_basis(self):
        with self.assertRaises(ValueError):Strategy(dict(BASE,sma_exit_enabled=True))
    def test_selected_underlying_flip_gate(self):
        s=Strategy(dict(BASE,entry_gate='underlying_flip_premium_bullish',exit_supertrend='premium'))
        s.reset_contract(dict(symbol='CE',option_type='CE'),.23)
        s.under_result=dict(direction=-1);s.premium_result=dict(direction=-1)
        self.assertIsNone(s.selected_gate_entry())
        s.pending_underlying_flip=123;s.last_time['premium']=123
        action=s.selected_gate_entry();self.assertEqual(action['action'],'BUY')
        self.assertIsNone(s.selected_gate_entry())
    def test_underlying_flip_waits_for_premium_confirmation_through_same_bar(self):
        s=Strategy(dict(BASE,entry_gate='underlying_flip_premium_bullish',exit_supertrend='premium'))
        s.reset_contract(dict(symbol='CE',option_type='CE'),.23)
        s.under_result=dict(direction=-1);s.premium_result=dict(direction=-1)
        s.pending_underlying_flip=300;s.last_time['premium']=240
        self.assertIsNone(s.selected_gate_entry());self.assertEqual(s.pending_underlying_flip,300)
        s.last_time['premium']=300
        self.assertEqual(s.selected_gate_entry()['action'],'BUY')

    def test_delayed_premium_gate_records_actual_confirming_bar_not_old_flip_bar(self):
        s=Strategy(dict(BASE,entry_gate='underlying_flip_premium_bullish',exit_supertrend='premium'))
        s.reset_contract(dict(symbol='CE',option_type='CE'),.23)
        s.under_result=dict(direction=-1);s.premium_result=dict(direction=-1)
        s.pending_underlying_flip=300;s.last_time['premium']=600
        action=s.selected_gate_entry()
        self.assertEqual(action['timestamp'],600)
        self.assertEqual(action['position']['entry_timestamp'],600)
        self.assertEqual(action['position']['underlying_flip_timestamp'],300)

    def test_premium_bearish_does_not_enter(self):
        s=Strategy(dict(BASE,entry_gate='underlying_flip_premium_bullish'))
        s.reset_contract(dict(symbol='CE',option_type='CE'),.23)
        s.under_result=dict(direction=-1);s.premium_result=dict(direction=1);s.pending_underlying_flip=123
        self.assertIsNone(s.selected_gate_entry())
    def test_contract_frozen(self):
        s=Strategy(BASE);contract=dict(symbol='verified',option_type='CE')
        s.reset_contract(contract,.23);s.position=dict(s.contract,side='CE')
        with self.assertRaises(ValueError):s.reset_contract(contract,.7)
        self.assertEqual(s.contract['option_brick'],400/12*.23)
    def test_timeframe_validation(self):
        for tf in (1,5,30):Strategy(dict(BASE,timeframe=tf))
        with self.assertRaises(ValueError):Strategy(dict(BASE,timeframe=15))
    def test_reject_duplicates(self):
        s=Strategy(BASE);event=dict(kind='underlying',timestamp=1,close=100)
        s.update(event)
        with self.assertRaises(ValueError):s.update(event)
    def test_history_dedup(self):
        row=[1,10,11,9,10,1]
        self.assertEqual(normalize([row,row]),([row],1))
        with self.assertRaises(ValueError):normalize([row,[1,10,12,9,10,1]])
    def test_volume_only_conflict_unavailable(self):
        rows,count=normalize([[1,10,11,9,10,3],[1,10,11,9,10,4]],price_only=True)
        self.assertIsNone(rows[0][5]);self.assertEqual(count,1)
    def test_no_plain_sma_entry(self):
        s=Strategy(BASE)
        s.reset_contract(dict(symbol='CE',option_type='CE'),.23)
        actions=[]
        for i,close in enumerate([1000,1100,1200,1300,1400]):
            actions.extend(s.update(dict(kind='underlying',timestamp=i,close=close)))
        self.assertTrue(any(a['action']=='BUY' for a in actions))
if __name__=='__main__':unittest.main(verbosity=2)
