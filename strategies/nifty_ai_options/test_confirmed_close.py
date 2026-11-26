import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from confirmed_close import ConfirmedClose,delta_reader

class ConfirmedCloseTests(unittest.TestCase):
    def test_uses_provider_close_and_records_differing_stream_hint(self):
        with tempfile.TemporaryDirectory() as folder:
            reader=Mock(return_value=({'raw':'preserved'},[[120,99,110,98,105,1]]))
            c=ConfirmedClose(reader,folder)
            event=c.confirm(dict(kind='underlying',timestamp=120,close=104),'EXACT',1,now=180)
            self.assertEqual(event['close'],105);self.assertEqual(event['stream_close_hint'],104)
            self.assertEqual(event['source_basis'],'PROVIDER_CONFIRMED_CLOSE')
            audit=json.loads(next(Path(folder).glob('*-audit.json')).read_text())
            self.assertTrue(audit['stream_hint_differs'])
            c.confirm(dict(kind='sma',timestamp=120,close=104),'EXACT',1,now=181)
            reader.assert_called_once_with('EXACT',1,120)

    def test_body_uses_exact_provider_open_and_cached_availability(self):
        with tempfile.TemporaryDirectory() as folder:
            reader=Mock(return_value=({},[[120,99,110,98,105,1]]))
            c=ConfirmedClose(reader,folder)
            first=c.confirm(dict(timestamp=120,close=104,open=1000),'EXACT',1,now=180)
            cached=c.confirm(dict(timestamp=120,close=106),'EXACT',1,now=185)
            self.assertEqual(first['open'],99);self.assertTrue(first['body_available'])
            self.assertEqual(cached['available_at'],180);reader.assert_called_once()
    def test_missing_or_conflicting_open_disables_body_without_inventing_it(self):
        for rows in ([[120,None,None,None,105,None]],[[120,99,110,98,105,1],[120,100,110,98,105,1]]):
            with self.subTest(rows=rows),tempfile.TemporaryDirectory() as folder:
                c=ConfirmedClose(Mock(return_value=({},rows)),folder)
                event=c.confirm(dict(timestamp=120,close=105,open=999),'EXACT',1,now=180)
                self.assertEqual(event['close'],105);self.assertIsNone(event['open'])
                self.assertFalse(event['body_available'])

    def test_missing_or_conflicting_provider_close_never_uses_tick_fallback(self):
        for rows in [[],[[180,1,1,1,1,1]],[[120,1,2,1,1,1],[120,1,2,1,2,1]]]:
            with self.subTest(rows=rows),tempfile.TemporaryDirectory() as folder:
                c=ConfirmedClose(Mock(return_value=({'fixture':True},rows)),folder)
                with self.assertRaises(ValueError):c.confirm(dict(timestamp=120,close=999),'EXACT',1,now=180)
                self.assertEqual(len(list(Path(folder).glob('*-raw.json'))),1)
                self.assertEqual(json.loads(next(Path(folder).glob('*-audit.json')).read_text())['decisions_made'],0)

    def test_forming_bar_is_rejected_before_network_read(self):
        with tempfile.TemporaryDirectory() as folder:
            reader=Mock();c=ConfirmedClose(reader,folder)
            with self.assertRaisesRegex(ValueError,'not completed'):c.confirm(dict(timestamp=120,close=1),'EXACT',1,now=179)
            reader.assert_not_called()

    def test_exact_symbol_and_frame_have_separate_confirmation_caches(self):
        with tempfile.TemporaryDirectory() as folder:
            reader=Mock(return_value=({},[[120,None,None,None,1,None]]));c=ConfirmedClose(reader,folder)
            for symbol,frame in [('SPOT',1),('PREMIUM',1),('SPOT',5)]:
                c.confirm(dict(timestamp=120,close=1),symbol,frame,now=420)
            self.assertEqual(reader.call_count,3)

    def test_delta_adapter_sends_only_exact_public_history_query(self):
        delta=Mock();delta._get.return_value={'result':[dict(time=120,close=1)]}
        raw,rows=delta_reader(delta)('BTCUSD',5,120)
        self.assertEqual(rows,[[120,None,None,None,1,None]])
        delta._get.assert_called_once_with('/v2/history/candles',dict(symbol='BTCUSD',resolution='5m',start=120,end=420))
        delta.submit.assert_not_called();delta._private.assert_not_called()


class SourceHandoverTests(unittest.TestCase):
    def test_intraday_or_continuous_source_gap_halts_before_provider_read_or_decision(self):
        with tempfile.TemporaryDirectory() as folder:
            reader=Mock();confirmed=ConfirmedClose(reader,folder)
            for continuous in [True,False]:
                with self.assertRaisesRegex(ValueError,'Source gap'):
                    confirmed.confirm(dict(timestamp=240,close=1),'EXACT',1,now=300,previous=120,continuous=continuous,opening_minutes=555)
            reader.assert_not_called()

    def test_next_regular_session_open_can_follow_prior_completed_session(self):
        from datetime import datetime
        from markets import IST
        prior=datetime(2026,11,19,15,15,tzinfo=IST).timestamp()
        current=datetime(2026,11,20,9,15,tzinfo=IST).timestamp()
        with tempfile.TemporaryDirectory() as folder:
            reader=Mock(return_value=({},[[current,None,None,None,1,None]]))
            confirmed=ConfirmedClose(reader,folder)
            value=confirmed.confirm(dict(timestamp=current,close=1),'EXACT',30,now=current+1800,previous=prior,continuous=False,opening_minutes=555)
            self.assertEqual(value['close'],1)
            with self.assertRaisesRegex(ValueError,'Source gap'):
                confirmed.confirm(dict(timestamp=current,close=1),'EXACT',30,now=current+1800,previous=prior,continuous=True)
