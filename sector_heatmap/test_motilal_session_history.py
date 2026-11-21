import tempfile,unittest
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from .motilal_history import History

class SessionHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.start=int(datetime(2025,1,1,9,15,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp())
        self.history=History(Path(self.tmp.name)/'history.db',clock=lambda:self.start+400*86400)
    def add_sessions(self,count):
        with self.history.db() as db:
            db.executemany('INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)',
                [('NSE:1',self.start+d*86400+m*60,100+m,102+m,99+m,101+m,3,1,5,1)
                 for d in range(count) for m in range(375)])
    def test_older_complete_sessions_survive_minute_tail_limit(self):
        self.add_sessions(270)
        rows=self.history.session_candles('NSE:1')
        self.assertEqual(len(rows),270);self.assertEqual(rows[0]['timestamp'],self.start)
        self.assertEqual((rows[0]['open'],rows[0]['close'],rows[0]['volume']),(100,475,1875))
    def test_gap_interruption_and_missing_volume_are_distinct(self):
        self.add_sessions(4)
        with self.history.db() as db:
            db.execute('DELETE FROM candles WHERE timestamp=?',(self.start+60,))
            db.execute('UPDATE candles SET open_verified=0 WHERE timestamp=?',(self.start+86400+60,))
            db.execute('UPDATE candles SET volume_verified=0 WHERE timestamp=?',(self.start+2*86400+60,))
        rows=self.history.session_candles('NSE:1')
        self.assertEqual(len(rows),2);self.assertIsNone(rows[0]['volume'])
        self.assertFalse(rows[0]['volume_available']);self.assertTrue(rows[1]['volume_available'])
    def test_unfinished_session_stays_unavailable(self):
        self.add_sessions(1);self.history.clock=lambda:self.start+374*60
        self.assertEqual(self.history.session_candles('NSE:1'),[])
    def test_invalid_inputs(self):
        for kwargs in ({'minutes':True},{'minutes':0},{'limit':0},{'limit':True},{'session_open':'25:00'}):
            with self.assertRaises(ValueError):self.history.session_candles('NSE:1',**kwargs)

    def test_mcx_evening_session_uses_exchange_open_and_close(self):
        from .motilal_calendar import trading_bounds

        start = int(datetime(2026, 11, 10, 17, tzinfo=ZoneInfo("Asia/Kolkata")).timestamp())
        first, last = trading_bounds(start)
        self.assertEqual((first, last), (17 * 60, 23 * 60 + 55))
        with self.history.db() as db:
            db.executemany("INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)", [
                ("MO:MCX:1", start + minute * 60, 100, 102, 99, 101, 3, 1, 5, 1)
                for minute in range(last - first)
            ])
        close = start + (last - first) * 60
        self.history.clock = lambda: close - 1
        self.assertEqual(self.history.candles("MO:MCX:1", 840, session_bounds=trading_bounds), [])
        self.history.clock = lambda: close
        rows = self.history.candles("MO:MCX:1", 840, session_bounds=trading_bounds)
        self.assertEqual([(row["timestamp"], row["volume"]) for row in rows],
                         [(start, (last - first) * 5)])

    def test_ncdex_broker_daily_snapshots_build_only_complete_weeks(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from .chart_workspace import motilal_chart

        ist = ZoneInfo("Asia/Kolkata")

        def stamp(day, hour=0, minute=0):
            return int(datetime(2026, 11, day, hour, minute, tzinfo=ist).timestamp())

        symbol = "MO:NCDEX:101"
        now = stamp(9, 23, 54)
        row = dict(exchange="NCDEX", scripcode=101, date="09-11-2026",
                   open=100, high=120, low=99, close=109, volume=10)
        client = Mock()
        client.request.return_value = {"data": [row]}
        self.history.clock = lambda: now
        service = SimpleNamespace(
            clock=lambda: now, ready=lambda: None, history=self.history,
            eod_snapshot=lambda exchange: client.request("eod", {"exchangename": exchange}),
            feed=Mock(), master=Mock(exact=Mock(return_value=dict(
                exchange="NCDEX", token=101, underlying="RAINCHNNAI"))),
        )
        self.assertEqual(motilal_chart(service, "1D", symbol=symbol)["rows"], [])
        self.assertEqual(self.history.daily_snapshots(symbol), [])
        for day in (9, 11, 12, 13):
            now = stamp(day, 23, 55)
            row.update(date=f"{day:02d}-11-2026", close=100 + day)
            motilal_chart(service, "1W", symbol=symbol)

        now = stamp(13, 23, 54)
        self.assertEqual(motilal_chart(service, "1W", symbol=symbol)["rows"], [])
        # The next calendar week has not started, but the final session has closed.
        now = stamp(13, 23, 55)
        service.history = History(self.history.path, clock=lambda: now)
        client.request.reset_mock()
        weekly = motilal_chart(service, "1W", symbol=symbol)
        self.assertEqual(weekly["rows"], [[stamp(9), 100, 120, 99, 113, 40]])
        client.request.assert_called_once_with("eod", {"exchangename": "NCDEX"})

        with service.history.db() as db:
            db.execute("DELETE FROM daily_snapshots WHERE symbol=? AND timestamp=?", (symbol, stamp(11)))
        self.assertEqual(motilal_chart(service, "1W", symbol=symbol)["rows"], [])

    def test_equity_calendar_uses_archived_broker_eod_snapshots(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from .chart_workspace import motilal_chart

        ist = ZoneInfo("Asia/Kolkata")
        monday = datetime(2026, 10, 5, tzinfo=ist)
        now = int((monday + timedelta(hours=15, minutes=29)).timestamp())
        symbol = "MO:NSE:101"
        client = Mock()
        service = SimpleNamespace(
            clock=lambda: now, ready=lambda: None, history=self.history,
            eod_snapshot=lambda exchange: client.request("eod", {"exchangename": exchange}),
            feed=Mock(), master=Mock(exact=Mock(return_value={"exchange": "NSE", "token": 101})),
        )
        for day in range(5):
            session = monday + timedelta(days=day)
            client.request.return_value = {"data": [{
                "exchange": "NSE", "scripcode": 101, "date": session.strftime("%d-%m-%Y"),
                "open": 100, "high": 110, "low": 98, "close": 101 + day, "volume": 50,
            }]}
            if day == 0:
                motilal_chart(service, "1W", symbol=symbol)
                self.assertEqual(self.history.daily_snapshots(symbol), [])
            now = int((session + timedelta(hours=15, minutes=30)).timestamp())
            motilal_chart(service, "1W", symbol=symbol)
        now = int((monday + timedelta(days=7)).timestamp())
        client.request.return_value = {"data": []}
        self.assertEqual(motilal_chart(service, "1W", symbol=symbol)["rows"],
                         [[int(monday.timestamp()), 100, 110, 98, 105, 250]])
