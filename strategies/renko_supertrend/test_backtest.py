import copy,json,tempfile,unittest
from datetime import date,datetime,timedelta
from pathlib import Path
from unittest.mock import patch
from . import backtest as bt
from .backtest_data import Archive,IST,session,in_session,valid_rows,aggregate

def epoch(day,h=9,m=15):return int(datetime.combine(day,datetime.min.time(),IST).replace(hour=h,minute=m).timestamp())
def row(t,p=1000):return dict(timestamp=t,open=p,high=p+1,low=p-1,close=p,volume=10)
def configuration(**kw):return dict(strategy='RENKO_SUPERTREND_V1',underlying='NSE:NIFTY50-INDEX',timeframe='1 minute',lots=1,mode='BACKTEST',atr_length=1,factor=.1,brick_mode='Manual',manual_brick=10,exit_policy='OPPOSITE_CONFIRMED_SIGNAL',rsi_slope_enabled=False,rsi_level_enabled=False,ema_exit_enabled=False,ema_proximity_enabled=False,ema_third_enabled=True,ema_third_length=100,**kw)

class Source:
    calls=0
    def __init__(self,missing=False,lot=25,exit_signal=True):
        self.evidence=[];self.selected=[];self.missing=missing;self.lot=lot;self.exit_signal=exit_signal
        self.rows=[row(epoch(date(2026,10,d))+i*60) for d in (13,14,15,16) for i in range(375)]
        self.quotes=[row(x['timestamp'],10+(x['timestamp']-epoch(date(2026,10,16),10,0))/60) for x in self.rows if x['timestamp']>=epoch(date(2026,10,16),9,58)]
        # Positive premiums across the whole held interval; exact entry 12, exit 14.
        for q in self.quotes:q.update(open=12,high=15,low=10,close=12)
        next(q for q in self.quotes if q['timestamp']==epoch(date(2026,10,16),10,3)).update(open=14,close=14)
    def underlying(self,symbol,first,last,minutes):return (self.rows if minutes==1 else aggregate(self.rows,minutes,session(symbol))),dict(provider='fixture')
    def select(self,symbol,at,direction,spot):
        self.selected.append((at,direction,spot));return dict(symbol='NSE:NIFTY26O191000CE',strike=1000,expiry='2026-10-19',option_type='CE',lot_size=self.lot,lot_size_source='Fixture historical contract metadata' if self.lot else None,lot_size_provenance=dict(provider='FYERS_SYMBOL_MASTER',symbol='NSE:NIFTY26O191000CE',expiry='2026-10-19',lot_size=self.lot,effective_from='2026-10-16',effective_to='2026-10-16',snapshot_as_of='2026-10-16',source_sha256='0'*64,source_url='https://public.fyers.in/sym_details/NSE_FO.csv') if self.lot else None)
    def premiums(self,contract,first,last,minutes):
        assert contract['symbol']=='NSE:NIFTY26O191000CE' and minutes==1
        return [q for q in self.quotes if not(self.missing and q['timestamp']==epoch(date(2026,10,16),10,2))]

class FakeEngine:
    def __init__(self,c,**kw):self.state={};self.c=c
    def update(self,bar):
        t=bar['timestamp'];enter=t==epoch(date(2026,10,16),10,0);exit=t==epoch(date(2026,10,16),10,2)
        return dict(timestamp=t,close=bar['close'],entry_direction='BULLISH' if enter else None,direction='BULLISH',ema10=1000,ema30=999,ema100=998,host_atr=5,raw_supertrend_cross_direction='BEARISH' if exit else None)

class BacktestTests(unittest.TestCase):
    def request(self,**kw):return dict(period='custom',from_date='2026-10-16',to_date='2026-10-16',settings=configuration(),**kw)
    def run_fixture(self,source=None,request=None):
        with patch.object(bt,'Engine',FakeEngine),patch.object(bt.ema_proximity,'check',return_value={}):return bt.run(request or self.request(),source or Source(),date(2026,10,25))
    def test_preset_boundaries_and_completed_dates(self):
        self.assertEqual(bt.period({'period':'1m'},date(2026,10,25)),(date(2026,9,25),date(2026,10,24)))
        for p in ({'period':'bad'},{'period':'custom','from_date':'2026-10-25','to_date':'2026-10-25'}):
            with self.assertRaises(ValueError):bt.period(p,date(2026,10,25))
    def test_actual_premiums_and_same_contract(self):
        source=Source();r=self.run_fixture(source);self.assertEqual(r['status'],'COMPLETE',r['issues']);self.assertEqual(len(source.selected),1)
        t=r['trades'][0];self.assertEqual((t['entry_premium'],t['exit_premium'],t['quantity'],t['gross_pnl']),(12,14,25,50));self.assertEqual(t['underlying_entry'],t['underlying_exit']);self.assertEqual(t['entry_at'],epoch(date(2026,10,16),10,1));self.assertEqual(t['exit_at'],epoch(date(2026,10,16),10,3));self.assertTrue(r['settings']['ema_third_enabled']);self.assertEqual(r['effective_settings']['ema_third_length'],100);json.dumps(r)
    def test_missing_held_quote_stops_without_proxy(self):
        r=self.run_fixture(Source(missing=True));self.assertIsNone(r['metrics']);self.assertEqual(r['trades'],[]);self.assertTrue(any(i['type']=='MISSING_HELD_CONTRACT' for i in r['issues']))
    def test_missing_historical_lot_withholds_pnl(self):
        r=self.run_fixture(Source(lot=None));self.assertIsNone(r['metrics']);self.assertIsNone(r['trades'][0]['quantity']);self.assertIsNone(r['trades'][0]['gross_pnl'])
    def test_explicit_quantity_assumption_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'substitutions are not allowed'):self.run_fixture(Source(lot=None),self.request(historical_units_per_lot='50'))
    def test_intrabar_selected_does_not_silently_downgrade(self):
        p=self.request();p['settings']['intrabar_entries']=True;r=self.run_fixture(request=p);self.assertIsNone(r['metrics']);self.assertEqual(r['trades'],[])
    def test_exact_cutoff_on_thirty_minute_signal(self):
        class Thirty(FakeEngine):
            def update(self,bar):
                s=super().update(bar);s['entry_direction']='BULLISH' if bar['timestamp']==epoch(date(2026,10,16),10,15) else None;s['raw_supertrend_cross_direction']=None;return s
        p=self.request();p['settings'].update(timeframe='30 minutes',ema_third_length=1)
        with patch.object(bt,'Engine',Thirty),patch.object(bt.ema_proximity,'check',return_value={}):r=bt.run(p,Source(),date(2026,10,25))
        self.assertEqual(r['trades'][0]['exit_at'],epoch(date(2026,10,16),15,10));self.assertEqual(r['trades'][0]['exit_reason'],'SESSION_CUTOFF')
    def test_provider_selection_uses_actual_ticker_and_fixed_side(self):
        with tempfile.TemporaryDirectory() as d:
            a=Archive(d);answers=[{'data':{'expiry_dates':{'options':['2026-10-19','2026-10-27']}}},{'data':{'symbol':'NIFTY','contracts':{'options':['NSE:NIFTY26O191000CE','NSE:NIFTY26O191050CE','NSE:NIFTY26O191000PE']}}}]
            with patch.object(a,'get',side_effect=answers):contract=a.select('NSE:NIFTY50-INDEX',epoch(date(2026,10,16)),'BULLISH',1025)
            self.assertEqual(contract['symbol'],'NSE:NIFTY26O191000CE');self.assertEqual(contract['expiry'],'2026-10-19');self.assertIsNone(contract['lot_size'])
    def test_calendar_and_ohlc_fail_closed(self):
        p=session('NSE:NIFTY50-INDEX');self.assertFalse(in_session(epoch(date(2026,10,16),9,14),p));self.assertFalse(in_session(epoch(date(2026,10,16),15,30),p));self.assertFalse(in_session(epoch(date(2026,10,17)),p))
        with self.assertRaises(ValueError):valid_rows([row(100),dict(row(100),close=900)])
    def test_quiet_period_missing_minute_is_incomplete(self):
        source=Source();source.rows=[r for r in source.rows if r['timestamp']!=epoch(date(2026,10,16),13,0)]
        r=self.run_fixture(source);self.assertIsNone(r['metrics']);self.assertTrue(any(i['type']=='UNDERLYING_MINUTE_GAPS' for i in r['issues']))
    def test_backtest_cannot_be_started_as_runner_mode(self):
        from .runner import configuration as validate
        from sector_heatmap.job_http import operation
        self.assertEqual(operation('/api/renko-supertrend/backtest'),('ANALYSIS','renko-supertrend'))
        with self.assertRaises(ValueError):validate(configuration())
    def test_saved_runner_without_third_ema_keeps_old_rules(self):
        from .runner import Runner,configuration as validate
        from .test_runner import FakeBroker
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'state.json';runner=Runner(FakeBroker(),path)
            state=copy.deepcopy(runner.state);state["schema"]=1;runner.release();state['config']=validate(dict(configuration(),mode='PAPER'));state['config'].pop('ema_third_enabled');state['config'].pop('ema_third_length');path.write_text(json.dumps(state));before=path.read_bytes()
            restored=Runner(FakeBroker(),path)
            try:self.assertFalse(restored.state['config']['ema_third_enabled']);self.assertEqual(restored.state['config']['ema_third_length'],100);self.assertEqual(path.read_bytes(),before)
            finally:restored.release()
    def test_durable_job_cancel_retains_partial_report_and_owner(self):
        import threading
        from sector_heatmap.persistent_jobs import JobStore
        with tempfile.TemporaryDirectory() as d:
            store=JobStore(Path(d)/'research.sqlite3');ready=threading.Event();release=threading.Event()
            def work(context):
                context.checkpoint('Partial contract audit saved.',{'revision':bt.REVISION,'partial_trades':[{'contract':'EXACT'}]});ready.set();release.wait(3);context.checkpoint('Next bar');return {}
            job=store.submit('user:fixture','ANALYSIS','renko-supertrend','Historical test',{'path':'/api/renko-supertrend/backtest','payload':self.request()},work,'fixture-once')
            try:
                self.assertTrue(ready.wait(3));store.cancel('user:fixture',job['job_id']);release.set();future=store.futures.get(job['job_id'])
                if future:future.result(timeout=3)
                saved=store.get('user:fixture',job['job_id']);self.assertEqual(saved['status'],'CANCELLED');self.assertEqual(saved['output']['partial_trades'][0]['contract'],'EXACT')
                with self.assertRaises(PermissionError):store.get('other:fixture',job['job_id'])
            finally:release.set();store.pool.shutdown(wait=True);store.runner_pool.shutdown(wait=True)
    def test_cnc_policy_is_not_silently_changed(self):
        p=self.request();p['settings'].update(execution_route='CASH_EQUITY',quantity=1,cash_product='CNC',underlying='NSE:TEST-EQ');r=self.run_fixture(request=p)
        self.assertEqual(r['trades'],[]);self.assertIsNone(r['metrics']);self.assertTrue(any(i['type']=='UNVERIFIED_CARRY_FORWARD' for i in r['issues']));self.assertEqual(r['effective_settings']['cash_product'],'CNC')
    def test_cancel_is_not_swallowed(self):
        from sector_heatmap.persistent_jobs import JobCancelled
        with patch.object(bt,'checkpoint',side_effect=JobCancelled):
            with self.assertRaises(JobCancelled):bt.run(self.request(),Source(),date(2026,10,25))

if __name__=='__main__':unittest.main()
