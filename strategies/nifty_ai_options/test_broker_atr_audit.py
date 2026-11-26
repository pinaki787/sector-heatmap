import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from broker_atr_audit import aggregate,atr

class BrokerATRAuditTests(unittest.TestCase):
    def rows(self):
        t=int(datetime(2026,11,20,9,15,tzinfo=ZoneInfo("Asia/Kolkata")).timestamp())
        return [[t+i*60,100,102,99,101,0] for i in range(375)]
    def test_session_boundaries_and_tail(self):
        rows=self.rows();bars,audit=aggregate(rows,1,rows[-1][0]+60)
        self.assertEqual([(b["bucket"],b["end"]-b["time"]) for b in bars],[(0,21600),(1,900)])
        self.assertEqual(audit["rejected"],[])
    def test_missing_minute_cannot_be_filled(self):
        rows=self.rows();bars,audit=aggregate(rows[:5]+rows[6:],1,rows[-1][0]+60)
        self.assertEqual([b["bucket"] for b in bars],[1])
        self.assertEqual(audit["rejected"][0]["missing"],1)
    def test_forming_parent_is_excluded(self):
        rows=self.rows();bars,audit=aggregate(rows,1,rows[300][0])
        self.assertEqual(bars,[])
        self.assertTrue(all(r["reason"]=="FORMING_PARENT" for r in audit["rejected"]))
    def test_conflicting_ohlc_rejected_even_same_close(self):
        rows=self.rows();other=list(rows[0]);other[2]=103
        with self.assertRaisesRegex(ValueError,"Conflicting"):aggregate(rows+[other],1,rows[-1][0]+60)
    def test_gap_true_range_and_wilder_update(self):
        bars=[dict(time=i,high=102,low=99,close=101) for i in range(5)]
        bars.append(dict(time=5,high=112,low=109,close=111))
        value,timeline=atr(bars)
        self.assertEqual(timeline[-1]["true_range"],11)
        self.assertAlmostEqual(value,4.6)
    def test_prefix_causality(self):
        bars=[dict(time=i,high=102+i,low=99+i,close=101+i) for i in range(20)]
        self.assertEqual(atr(bars[:10])[1],atr(bars)[1][:10])

if __name__=="__main__":unittest.main()
