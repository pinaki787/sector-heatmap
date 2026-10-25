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
