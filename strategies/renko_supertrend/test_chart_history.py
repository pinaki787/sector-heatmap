import tempfile
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from .chart_history import ChartHistory,selected_range
from .signals import project_lifecycle

class Client:
    def __init__(self):self.calls=[];self.fail=False;self.offset=0
    def history(self,q):
        self.calls.append(q)
        if self.fail:return {'s':'error','message':'fixture outage'}
        start=datetime.fromisoformat(q['range_from']).replace(tzinfo=ZoneInfo('Asia/Kolkata'))
        end=datetime.fromisoformat(q['range_to']).replace(tzinfo=ZoneInfo('Asia/Kolkata'))
        rows=[]
        for day in range((end-start).days+1):
            opening=start.timestamp()+day*86400+9*3600
            for n in range(100):
                value=100+n+self.offset
                rows.append([opening+n*int(q['resolution'])*60,value,value+2,value-1,value+1,1])
        return {'s':'ok','candles':rows}

class HistoryTests(unittest.TestCase):
    def test_chunks_full_display_cache_and_revision_replay(self):
        now=datetime(2026,10,6,10,0,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
        c=Client();config={'underlying':'MCX:TEST','timeframe':'1 minute','session_deadline':'23:30'}
        with tempfile.TemporaryDirectory() as root:
            h=ChartHistory(root,min_interval=0)
            a,rows,forming,m=h.load(c,'MCX:TEST','1 minute','custom','2026-09-01','2026-09-15',config,.05,now)
            self.assertEqual(len(rows),1500);self.assertGreater(len(a['rows']),500)
            self.assertEqual(m['initialization_bars'],700)
            self.assertTrue(all((datetime.fromisoformat(q['range_to'])-datetime.fromisoformat(q['range_from'])).days<=2 for q in c.calls))
            calls=len(c.calls)
            h2=ChartHistory(root,min_interval=0);b,again,_,m2=h2.load(c,'MCX:TEST','1 minute','custom','2026-09-01','2026-09-15',config,.05,now)
            self.assertEqual(len(c.calls),calls);self.assertEqual(again,rows);self.assertEqual(a['anchor'],b['anchor']);self.assertEqual(m['analysis_revision'],m2['analysis_revision'])
            other={**config,'factor':4};_,_,_,changed=h2.load(c,'MCX:TEST','1 minute','custom','2026-09-01','2026-09-15',other,.05,now)
            self.assertNotEqual(m['analysis_revision'],changed['analysis_revision'])
    def test_current_refresh_outage_preserves_provenance_and_completed_data(self):
        now=datetime(2026,10,6,23,45,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp();c=Client()
        config={'underlying':'MCX:TEST','timeframe':'5 minutes','session_deadline':'23:30'}
        with tempfile.TemporaryDirectory() as root:
            h=ChartHistory(root,min_interval=0);a,rows,_,m=h.load(c,'MCX:TEST','5 minutes','7',config=config,now=now)
            c.fail=True
            b,again,_,m2=h.load(c,'MCX:TEST','5 minutes','7',config=config,now=now+300)
            self.assertEqual(rows,again);self.assertIn('outage',m2['history_error']);self.assertEqual(a['anchor'],b['anchor'])
    def test_bounded_range_and_final_mcxcandle_exit(self):
        now=datetime(2026,10,6,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
        with self.assertRaises(ValueError):selected_range('custom','2026-01-01','2026-10-01',now)
        def at(h,m):return datetime(2026,10,5,h,m,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
        s={};project_lifecycle(s,at(23,27),'BULLISH',None,60,110,100,'23:30')
        exit=project_lifecycle(s,at(23,29),None,None,60,110,100,'23:30')
        self.assertEqual(exit['lifecycle_event'],'BUY EXIT');self.assertEqual(exit['lifecycle_event_at'],at(23,30));self.assertIsNone(s['projected_position'])
    def test_no_data_today_is_valid_empty_and_completed_chunks_persist(self):
        now=datetime(2026,10,6,1,0,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp();c=Client();method=c.history
        def history(q):
            if q['range_to']=='2026-10-06':return {'s':'no_data','message':''}
            return method(q)
        c.history=history
        config={'underlying':'MCX:TEST','timeframe':'1 minute','session_deadline':'23:30'}
        with tempfile.TemporaryDirectory() as root:
            h=ChartHistory(root,min_interval=0);_,rows,_,m=h.load(c,'MCX:TEST','1 minute','7',config=config,now=now)
            self.assertIsNone(m['history_error']);self.assertTrue(rows)
            c.history=lambda q: {'s':'error','message':'must not refetch cached completed range'}
            _,again,_,m2=ChartHistory(root,min_interval=0).load(c,'MCX:TEST','1 minute','7',config=config,now=now)
            self.assertEqual(rows,again);self.assertIsNone(m2['history_error'])

class QualityTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,10,7,16,0,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
        self.config={'underlying':'MCX:TEST','timeframe':'1 minute','session_deadline':'23:30'}

    def client(self):
        client=Client();original=client.history
        client.corrupt=True
        def history(query):
            response=original(query)
            if client.corrupt:
                for row in response['candles']:
                    if datetime.fromtimestamp(row[0],ZoneInfo('Asia/Kolkata')).date().isoformat()=='2026-10-02' and row[0]%86400== (9*3600-19800)%86400:
                        row[3]=row[4]+1
            return response
        client.history=history
        return client

    def test_invalid_history_returns_broker_candles_and_explicit_gap_without_signals(self):
        client=self.client()
        with tempfile.TemporaryDirectory() as root:
            history=ChartHistory(root,min_interval=0)
            result,rows,_,meta=history.load(client,'MCX:TEST','1 minute','7',config=self.config,now=self.now)
            quality=meta['data_quality']
            self.assertFalse(quality['analysis_available']);self.assertEqual(quality['invalid_count'],1)
            self.assertEqual(len(quality['gaps']),1);self.assertIsNone(result['last'])
            self.assertTrue(rows);self.assertTrue(all('supertrend' not in row and 'entry_direction' not in row for row in rows))
            self.assertNotIn(quality['gaps'][0]['timestamp'],{row['timestamp'] for row in rows})
            calls=len(client.calls)
            history.load(client,'MCX:TEST','1 minute','7',config=self.config,now=self.now+1)
            self.assertEqual(len(client.calls),calls)
            client.corrupt=False
            repaired,_,_,meta=history.load(client,'MCX:TEST','1 minute','7',config=self.config,now=self.now+60)
            self.assertTrue(meta['data_quality']['analysis_available']);self.assertEqual(meta['data_quality']['invalid_count'],0)
            self.assertIsNotNone(repaired['last']);self.assertNotEqual(quality,meta['data_quality'])
            self.assertTrue(any(q['range_from']==q['range_to']=='2026-10-02' for q in client.calls[calls:]))

    def test_invalid_warmup_also_withholds_all_derived_analysis(self):
        client=self.client()
        with tempfile.TemporaryDirectory() as root:
            _,rows,_,meta=ChartHistory(root,min_interval=0).load(client,'MCX:TEST','1 minute','custom','2026-10-05','2026-10-06',self.config,now=self.now)
            self.assertFalse(meta['data_quality']['analysis_available']);self.assertEqual(meta['data_quality']['gaps'],[])
            self.assertTrue(rows);self.assertTrue(all('ema10' not in row for row in rows))

    def test_malformed_revision_cannot_replace_previously_valid_candle(self):
        client=Client();original=client.history
        with tempfile.TemporaryDirectory() as root:
            history=ChartHistory(root,min_interval=0)
            _,before,_,_=history.load(client,'MCX:TEST','1 minute','7',config=self.config,now=self.now)
            def corrupted(query):
                d=original(query)
                for row in d['candles']:row[3]=row[4]+1
                return d
            client.history=corrupted
            _,after,_,meta=history.load(client,'MCX:TEST','1 minute','7',config=self.config,now=self.now+60)
            self.assertEqual(before,after);self.assertTrue(meta['data_quality']['analysis_available'])
