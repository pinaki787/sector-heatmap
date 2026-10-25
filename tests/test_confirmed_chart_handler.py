"""Exercise the actual chart HTTP branch with broker IO deliberately unavailable."""
import os
from pathlib import Path
import textwrap
import threading
from types import SimpleNamespace
import unittest
from urllib.parse import parse_qs,urlparse
from strategies.renko_supertrend.runner import analysis,configuration
from strategies.renko_supertrend.signals import settings
from strategies.renko_supertrend.test_signals import candle


class ConfirmedChartHandlerTests(unittest.TestCase):
    def setUp(self):
        source=Path(os.environ.get('CONFIRMED_WEB_SOURCE','sector_heatmap/web.py')).read_text()
        start=source.index('            if path == "/api/renko-supertrend/chart":')
        end=source.index('            if path == "/api/ema-band/runner":',start)
        block=textwrap.dedent(source[start:end])
        self.config=configuration(dict(strategy='RENKO_SUPERTREND_V1',exit_policy='OPPOSITE_CONFIRMED_SIGNAL',underlying='NSE:NIFTY50-INDEX',timeframe='5 minutes',mode='PAPER',lots=1,brick_mode='Manual',manual_brick=10))
        self.engine=analysis([candle(i,100+i) for i in range(40)],self.config,.05)
        self.runner=SimpleNamespace(lock=threading.Lock(),state=dict(run_id='owned',config=self.config,renko_engine=self.engine))
        class Broker:
            def session_policy(self,c):return dict(session_deadline='15:10',master_regular_session='0915-1530')
            def route_availability(self,c):return dict(available=True)
            def host_tick_size(self,s):return .05
        class Chart:
            def observe(self,*args):pass
            def start(self):pass
            def candles(self,*args):raise RuntimeError('History unavailable')
            def forming(self,*args):raise ValueError('Forming candle unavailable')
        class NoHistory:
            def load(self,*args,**kwargs):raise AssertionError('Confirmed chart must not request history or replay independently')
        self.responses=[]
        env=dict(path='/api/renko-supertrend/chart',parse_qs=parse_qs,urlparse=urlparse,
            renko_supertrend_settings=settings,renko_supertrend=self.runner,renko_broker=Broker(),
            renko_chart_broker=Chart(),renko_chart_history=NoHistory(),renko_display_lock=threading.Lock(),
            renko_display_context={},time=__import__('time'),json=__import__('json'))
        exec('def exercise(self):\n'+textwrap.indent(block,'    '),env)
        self.exercise=env['exercise']

    def call(self,run='owned',frame='5 minutes',symbol='NSE:NIFTY50-INDEX'):
        from urllib.parse import urlencode
        request=SimpleNamespace(path='/api/renko-supertrend/chart?'+urlencode(dict(symbol=symbol,timeframe=frame,confirmed_run_id=run)),
            send_json=lambda status,data:self.responses.append((status,data)))
        self.exercise(request)
        return self.responses[-1]

    def test_confirmed_view_survives_history_and_forming_outage(self):
        status,data=self.call()
        self.assertEqual(status,200,data)
        self.assertEqual(data['rows'],self.engine['rows'])
        self.assertEqual(data['latest'],self.engine['last'])
        self.assertEqual(data['confirmed_source']['run_id'],'owned')
        self.assertEqual(data['host_bar_count'],self.engine['state']['count'])
        self.assertEqual(data['forming'],[])
        self.assertNotIn('_engine',data['confirmed_source'])

    def test_foreign_run_or_timeframe_is_rejected_without_history_fallback(self):
        for kw in [dict(run='other'),dict(frame='15 minutes'),dict(symbol='NSE:OTHER')]:
            with self.subTest(kw=kw):
                status,data=self.call(**kw)
                self.assertEqual(status,409)
                self.assertIn('identity changed',data['error'])
