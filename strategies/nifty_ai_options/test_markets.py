import unittest
from datetime import datetime
from markets import SourceBars,IST,margin_reader
from unittest.mock import Mock
class MarketTests(unittest.TestCase):
    def test_regular_anchor_discards_initial_partial_source_bar(self):
        at=datetime(2026,11,19,9,15,tzinfo=IST).timestamp();s=SourceBars(5,opening_minutes=555,closing_minutes=930)
        self.assertIsNone(s.update(at+15,100));self.assertIsNone(s.update(at+300,101))
        self.assertEqual(s.update(at+600,102),(at+300,101))
    def test_continuous_source_crosses_midnight(self):
        at=datetime(2026,11,19,23,59,tzinfo=IST).timestamp();s=SourceBars(1,continuous=True)
        self.assertIsNone(s.update(at,100));self.assertEqual(s.update(at+60,101),(at,100))
    def test_missing_source_intervals_halt(self):
        at=datetime(2026,11,19,9,15,tzinfo=IST).timestamp();s=SourceBars(5,opening_minutes=555,closing_minutes=930)
        s.update(at,100)
        with self.assertRaises(ValueError):s.update(at+600,105)
    def test_broker_additional_margin_uses_total_not_existing_position_total(self):
        raw=Mock();raw.header='FAKE_TEST_ONLY'
        response=raw._sector_pulse_ipv4_session.post.return_value;response.json.return_value={'s':'ok','data':{'margin_total':500,'margin_new_order':2000,'margin_avail':1000}}
        self.assertEqual(margin_reader(raw)({'symbol':'FAKE'}),500)
        response.json.return_value={'s':'ok','data':{'margin_new_order':2000}}
        with self.assertRaises(ValueError):margin_reader(raw)({'symbol':'FAKE'})


class ProviderConfirmedSourceTests(unittest.TestCase):
    def test_partial_tick_coverage_is_only_accepted_with_mandatory_provider_confirmation_path(self):
        at=datetime(2026,11,19,9,15,tzinfo=IST).timestamp()
        source=SourceBars(5,opening_minutes=555,closing_minutes=930,confirmed_closes=True)
        self.assertIsNone(source.update(at+15,100))
        self.assertEqual(source.update(at+300,101),(at,100))
