import unittest
from .signals import project_lifecycle,series
from .test_signals import candle

class ProjectionTests(unittest.TestCase):
    def test_single_entry_then_exit_and_no_same_candle_flip(self):
        state={}
        inputs=[('BULLISH',None),('BULLISH',None),('BEARISH',None),('BEARISH','BEARISH'),(None,None),('BEARISH',None),('BEARISH',None),('BULLISH','BULLISH')]
        events=[project_lifecycle(state,i,entry,reversal)['lifecycle_event'] for i,(entry,reversal) in enumerate(inputs)]
        self.assertEqual(events,['BUY',None,None,'BUY EXIT',None,'SELL',None,'SELL EXIT'])
        self.assertIsNone(state['projected_position'])
    def test_no_fabricated_exit_on_narrowing_or_filtered_reversal(self):
        s={};project_lifecycle(s,0,'BULLISH',None)
        self.assertIsNone(project_lifecycle(s,1,None,None)['lifecycle_event'])
        self.assertEqual(s['projected_position']['direction'],'BULLISH')
        self.assertIsNone(project_lifecycle(s,2,'BEARISH',None)['lifecycle_event'])
        self.assertEqual(project_lifecycle(s,3,None,'BEARISH')['lifecycle_event'],'BUY EXIT')
    def test_full_history_events_alternate_and_keep_open_tail(self):
        rows=series([candle(i,p) for i,p in enumerate([100,110,120,130,140,150,80,70,60,50,40,150,160,170,180])],dict(atr_length=1,factor=.1,brick_mode='Manual',manual_brick=10))
        active=None
        for r in rows:
            e=r['lifecycle_event']
            if e in ('BUY','SELL'):
                self.assertIsNone(active);active=e
            elif e:
                self.assertEqual(e,active+' EXIT');active=None
        if active:self.assertIsNotNone(rows[-1]['projected_position'])

    def test_ema10_confirmed_exit_reason_and_cutoff(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        def at(h,m):return datetime(2026,10,5,h,m,tzinfo=ZoneInfo('Asia/Kolkata')).timestamp()
        s={};project_lifecycle(s,at(10,0),'BULLISH',None,300,110,100)
        self.assertEqual(project_lifecycle(s,at(10,5),None,None,300,99,100)['lifecycle_reason'],'EMA10_CONFIRMED_BREACH')
        project_lifecycle(s,at(10,10),'BEARISH',None,300,90,100)
        self.assertEqual(project_lifecycle(s,at(10,15),None,None,300,101,100)['lifecycle_event'],'SELL EXIT')
        self.assertIsNone(project_lifecycle(s,at(15,10),'BULLISH',None,300,110,100)['lifecycle_event'])
        project_lifecycle(s,at(15,5),'BULLISH',None,300,110,100)
        self.assertEqual(project_lifecycle(s,at(15,15),None,None,300,110,100)['lifecycle_reason'],'TIMED_SQUARE_OFF_1515')
