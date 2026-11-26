import unittest
from native_reference import choose_reference
class NativeReferenceTests(unittest.TestCase):
    def ref(self,**kw):return dict(dict(broker_symbol='NSE:RELIANCE-EQ',status='VERIFIED_NATIVE',parent_hours=6,atr_length=5,native_box=120,reference_measure='NATIVE_RENKO_ATR_BOX',renko_method='ATR',source_price='Close',wicks=False,chart_session='Regular trading hours',reference_session='2026-11-19',observed_at='2026-11-20T01:00:00+05:30'),**kw)
    def test_exact_identity_session_parent_and_fresh_date_required(self):
        r=self.ref()
        self.assertEqual(choose_reference([r],'NSE:RELIANCE-EQ','NSE',expected_session='2026-11-19'),r)
        for bad in [self.ref(broker_symbol='NSE:NIFTY50-INDEX'),self.ref(parent_hours=23),self.ref(chart_session='Extended trading hours'),self.ref(reference_session='2026-11-18'),self.ref(status='UNVERIFIED')]:self.assertIsNone(choose_reference([bad],'NSE:RELIANCE-EQ','NSE',expected_session='2026-11-19'))
    def test_continuous_reference_requires_completed_not_future_native_parent(self):
        r=self.ref(broker_symbol='BTCUSD',parent_hours=23,atr_length=7,completed_parent_at=100)
        self.assertEqual(choose_reference([r],'BTCUSD','CRYPTO',now=101),r)
        self.assertIsNone(choose_reference([r],'BTCUSD','CRYPTO',now=99))
        self.assertIsNone(choose_reference([r],'BTCUSD','CRYPTO',now=100+23*3600+1))

    def test_native_method_close_and_no_wicks_are_mandatory(self):
        r=self.ref()
        for changes in ({'renko_method':'Traditional'},{'source_price':'OHLC'},{'wicks':True},{'wicks':0}):
            self.assertIsNone(choose_reference([self.ref(**changes)],'NSE:RELIANCE-EQ','NSE',expected_session='2026-11-19'))
        for key in ('renko_method','source_price','wicks'):
            bad=dict(r);bad.pop(key)
            self.assertIsNone(choose_reference([bad],'NSE:RELIANCE-EQ','NSE',expected_session='2026-11-19'))

    def test_lowercase_market_cannot_bypass_regular_session_validation(self):
        self.assertIsNone(choose_reference([self.ref(chart_session='Extended trading hours',completed_parent_at=100)],'NSE:RELIANCE-EQ','nse',expected_session='2026-11-19',now=101))

    def test_unrelated_malformed_records_do_not_break_valid_lookup(self):
        r=self.ref(completed_parent_at=None)
        self.assertEqual(choose_reference([None,[],r,self.ref(completed_parent_at='bad')],'NSE:RELIANCE-EQ','NSE',expected_session='2026-11-19'),r)

    def test_conflicting_completed_session_values_are_unavailable_in_either_order(self):
        a=self.ref()
        b=self.ref(native_box=121,observed_at='2026-11-20T03:00:00+05:30')
        for records in ([a,b],[b,a]):
            self.assertIsNone(choose_reference(records,'NSE:RELIANCE-EQ','NSE',expected_session='2026-11-19'))

    def test_repeated_identical_observations_remain_usable(self):
        a=self.ref()
        b=self.ref(observed_at='2026-11-20T03:00:00+05:30')
        self.assertEqual(choose_reference([a,b],'NSE:RELIANCE-EQ','NSE',expected_session='2026-11-19'),b)

    def test_continuous_window_rollover_allows_new_size_but_same_window_conflict_blocks(self):
        a=self.ref(broker_symbol='BTCUSD',parent_hours=23,atr_length=7,completed_parent_at=100)
        b=self.ref(broker_symbol='BTCUSD',parent_hours=23,atr_length=7,completed_parent_at=200,native_box=150)
        self.assertEqual(choose_reference([a,b],'BTCUSD','CRYPTO',now=201),b)
        bad=dict(b,native_box=151)
        self.assertIsNone(choose_reference([a,b,bad],'BTCUSD','CRYPTO',now=201))

    def test_reference_measure_cannot_switch_to_atr_over_renko_bars(self):
        bad=self.ref(reference_measure='ATR5_OVER_NATIVE_RENKO_BARS')
        missing=self.ref();missing.pop('reference_measure')
        for r in (bad,missing):
            self.assertIsNone(choose_reference([r],'NSE:RELIANCE-EQ','NSE',expected_session='2026-11-19'))
