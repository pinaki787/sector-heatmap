import copy
import json
import tempfile
import time
import unittest
from pathlib import Path
from sector_heatmap.delta_backtest import (DeltaBacktest, plan, audit, coverage, bollinger_features, simulate, INTERVALS)
from sector_heatmap.delta_signals import delta_rsi_series

NOW=1791018000
SETTINGS=dict(capital=10000,contracts=2,fee_bps=10,slippage_bps=0,half_spread_bps=0,funding_bps_day=0)
CFG=dict(resolution='1m',entry_rule='CURRENT',direction='BOTH',filter='BASELINE',adx_enabled=False,momentum_enabled=False,bb_length=5,bb_deviation=2,squeeze_lookback=20,squeeze_percentile=20,release_bars=3)

def candles(n=400,start=1705000020):
    rows=[]
    import math
    for i in range(n):
        close=100+8*math.sin(i/6)
        rows.append(dict(timestamp=start+i*60,open=close-.1,high=close+2,low=close-2,close=close,volume=100,is_forming=False))
    return rows

def payload(**values):
    return dict(symbol='BTCUSD',start_date='2026-09-25',end_date='2026-09-27',resolutions=['5m'],rsi_lengths=[14],ma_lengths=[14],ma_types=['EMA'],filters=['BASELINE','EXPANDING','SQUEEZE_RELEASE'],**values)

class BacktestTests(unittest.TestCase):
    def test_grid_deduplicates_baseline_and_caps_work(self):
        p=payload();p.update(rsi_lengths=[10,14],ma_types=['EMA','SMA'],bb_lengths=[20,30])
        result=plan(p,NOW)
        self.assertEqual(result['combination_count'],20)
        self.assertEqual(sum(c['filter']=='BASELINE' for c in result['combinations']),4)
        p.update(rsi_lengths=list(range(10,18)),ma_lengths=list(range(10,18)))
        with self.assertRaisesRegex(ValueError,'cap'):plan(p,NOW)
        p=payload();p.update(start_date='2024-01-01',resolutions=['1m'])
        with self.assertRaisesRegex(ValueError,'25,000'):plan(p,NOW)

    def test_dates_and_settings_are_strict(self):
        for change in [dict(symbol='C-BTC-90000-031026'),dict(end_date='2026-10-03'),dict(fee_bps=float('nan')),dict(rsi_lengths=[True]),dict(momentum_enabled='true')]:
            p=payload();p.update(change)
            with self.assertRaises(ValueError):plan(p,NOW)
        p=payload();p['filters']=['EXPANDING']
        self.assertEqual(plan(p,NOW)['combination_count'],2)

    def test_audit_completed_duplicates_conflicts_and_gaps(self):
        rows=candles(4);raw=[dict(time=r['timestamp'],**{k:r[k] for k in ('open','high','low','close','volume')}) for r in rows]
        lo=rows[0]['timestamp'];end=lo+240
        result,dupes=audit(raw+[raw[0]],60,lo,end,end-1)
        self.assertEqual((len(result),dupes),(3,1))
        b=dict(start=lo,end=end,interval=60,expected=4)
        self.assertEqual(coverage(result,b)['missing'],1)
        conflict=copy.deepcopy(raw[0]);conflict['close']+=.1
        with self.assertRaisesRegex(ValueError,'Conflicting'):audit(raw+[conflict],60,lo,end,end)
        raw[0]['time']+=1
        with self.assertRaisesRegex(ValueError,'alignment'):audit(raw,60,lo,end,end)

    def test_fill_uses_next_open_not_signal_close_and_no_same_signal_reversal(self):
        rows=[]
        for i,opening in enumerate([100,110,115,120,125]):
            rows.append(dict(timestamp=10020+i*60,open=opening,high=opening+2,low=opening-2,close=opening+1,volume=1,entry_direction='BULLISH' if i==0 else 'BEARISH' if i==2 else None,cross_direction='BEARISH' if i==2 else None,entry_reason='CROSSOVER'))
        out=simulate(rows,[dict(width_percent=1)]*5,{},CFG,SETTINGS,1,1,10020,10320)
        self.assertEqual(len(out['trades']),1)
        t=out['trades'][0]
        self.assertEqual((t['entry_price'],t['exit_price']),(110,120))
        self.assertEqual((t['entry_time'],t['exit_time']),(10080,10200))
        self.assertEqual(t['entry_signal_time'],t['entry_time'])
        self.assertAlmostEqual(t['net_pnl'],20-.22-.24)
        self.assertAlmostEqual(out['metrics']['net_pnl'],t['net_pnl'])

    def test_entry_gate_does_not_change_opposite_exit(self):
        rows=[]
        for i in range(6):
            rows.append(dict(timestamp=10020+i*60,open=100+i,high=102+i,low=98+i,close=101+i,entry_direction='BULLISH' if i==0 else None,cross_direction='BEARISH' if i==3 else None,entry_reason='CROSSOVER'))
        cfg=dict(CFG,filter='EXPANDING')
        features=[dict(width_percent=1,expanding=i==0,release=False) for i in range(6)]
        out=simulate(rows,features,{},cfg,SETTINGS,1,1,10020,10380)
        self.assertEqual(out['trades'][0]['exit_reason'],'OPPOSITE_CROSSOVER')
        self.assertEqual(out['trades'][0]['exit_price'],104)

    def test_period_boundary_costs_funding_and_capital_skip(self):
        rows=delta_rsi_series(candles(160),14,14,'EMA');features=bollinger_features(rows,CFG)
        free=simulate(rows,features,{},CFG,dict(SETTINGS,fee_bps=0),1,.01,rows[35]['timestamp'],rows[-1]['timestamp']+60)
        paid=simulate(rows,features,{},CFG,dict(SETTINGS,slippage_bps=5,half_spread_bps=3,funding_bps_day=5),1,.01,rows[35]['timestamp'],rows[-1]['timestamp']+60)
        self.assertEqual(len(free['trades']),len(paid['trades']))
        self.assertLess(paid['metrics']['net_pnl'],free['metrics']['net_pnl'])
        self.assertAlmostEqual(sum(t['net_pnl'] for t in paid['trades']),paid['metrics']['net_pnl'])
        self.assertGreater(paid['metrics']['funding_drag'],0)
        self.assertAlmostEqual(paid['equity'][-1]['equity'],paid['metrics']['ending_equity'])
        no=simulate(rows,features,{},CFG,dict(SETTINGS,capital=10),1,.01,rows[35]['timestamp'],rows[-1]['timestamp']+60)
        self.assertEqual(no['metrics']['trades'],0);self.assertGreater(no['metrics']['skipped_capital'],0)

    def test_indicators_and_candidates_are_prefix_causal(self):
        raw=candles();prefix=raw[:260]
        self.assertEqual(delta_rsi_series(raw,14,14,'EMA')[:260],delta_rsi_series(prefix,14,14,'EMA'))
        self.assertEqual(bollinger_features(raw,CFG)[:260],bollinger_features(prefix,CFG))
        # Future volatility cannot create earlier squeeze releases.
        changed=copy.deepcopy(raw)
        for r in changed[260:]:r['close']*=2
        self.assertEqual(bollinger_features(raw,CFG)[:260],bollinger_features(changed,CFG)[:260])

    def test_service_windows_cache_coverage_and_heldout(self):
        p=payload();p.update(resolutions=['1m'],start_date='2026-09-25',end_date='2026-09-25')
        cfg=plan(p,NOW);bounds=cfg['ranges']['1m'];calls=[]
        def read(path,params):
            self.assertEqual(path,'/v2/history/candles');self.assertLessEqual((params['end']-params['start'])//60,1500)
            calls.append(params)
            import math
            result=[]
            for t in range(params['start'],params['end']+60,60):
                c=100+8*math.sin(t/360)
                result.append(dict(time=t,open=c-.1,high=c+1,low=c-1,close=c,volume=10))
            return dict(success=True,result=result)
        metadata=lambda _:dict(symbol='BTCUSD',id=27,contract_type='perpetual_futures',notional_type='vanilla',is_quanto=False,quoting_currency='USD',settlement_currency='USD',underlying='BTC',contract_unit_currency='BTC',contract_value='0.001',tick_size='0.5')
        with tempfile.TemporaryDirectory() as folder:
            service=DeltaBacktest(folder,read,metadata,clock=lambda:NOW)
            started=service.start(p)
            deadline=time.monotonic()+15
            while service.status()['state'] in ('FETCHING','RUNNING') and time.monotonic()<deadline:time.sleep(.01)
            status=service.status();self.assertEqual(status['state'],'COMPLETE',status.get('message'))
            self.assertEqual(status['coverage']['1m']['missing'],0)
            self.assertGreater(len(calls),1)
            result=status['results'][0];detail=service.detail(result['id'])
            split=result['split']
            self.assertTrue(all(t['entry_time']>=split for t in detail['held_out']['trades']))
            self.assertTrue(all(t['exit_time']<=split for t in detail['train']['trades']))
            self.assertEqual([r['rank'] for r in status['results']],[1,2,3])
            returns=[r['train']['return_percent'] for r in status['results']];self.assertEqual(returns,sorted(returns,reverse=True))
            service.start(p)
            while service.status()['state'] in ('FETCHING','RUNNING') and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(service.status()['downloaded_windows'],0)
            reloaded=DeltaBacktest(folder,read,metadata,clock=lambda:NOW)
            self.assertEqual(reloaded.status()['state'],'COMPLETE')
            self.assertEqual(reloaded.detail(result['id'])['model'],detail['model'])

    def test_one_active_job_and_cancellation(self):
        import threading
        entered=threading.Event();released=threading.Event()
        def read(*args):
            entered.set();released.wait(2);return dict(result=[])
        metadata=lambda _:dict(contract_type='perpetual_futures',notional_type='vanilla',is_quanto=False,quoting_currency='USD',settlement_currency='USD',underlying='BTC',contract_unit_currency='BTC',contract_value='.001',tick_size='.5')
        with tempfile.TemporaryDirectory() as folder:
            service=DeltaBacktest(folder,read,metadata,clock=lambda:NOW)
            service.start(payload());self.assertTrue(entered.wait(2))
            with self.assertRaisesRegex(ValueError,'already running'):service.start(payload())
            service.cancel();released.set();deadline=time.monotonic()+2
            while service.status()['state'] in ('FETCHING','RUNNING') and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(service.status()['state'],'CANCELLED')
            self.assertEqual(service.status()['completed'],0)

    def test_missing_data_blocks_metrics_with_coverage(self):
        p=payload();cfg=plan(p,NOW)
        with tempfile.TemporaryDirectory() as folder:
            metadata=lambda _:dict(contract_type='perpetual_futures',notional_type='vanilla',is_quanto=False,quoting_currency='USD',settlement_currency='USD',underlying='BTC',contract_unit_currency='BTC',contract_value='.001',tick_size='.5')
            service=DeltaBacktest(folder,lambda *args:dict(result=[]),metadata,clock=lambda:NOW)
            service._update=lambda **v: service.job.update(v)
            service.job=dict(coverage={},downloaded_windows=0,cached_windows=0,plan=cfg)
            with self.assertRaisesRegex(ValueError,'missing'):service._fetch('BTCUSD','5m',cfg['ranges']['5m'],service.cancel_event)
            self.assertGreater(service.job['coverage']['5m']['missing'],0)


class ResearchWorkerTests(unittest.TestCase):
    def test_worker_rejects_other_origins_and_has_no_broker_routes(self):
        import requests
        import threading
        from http.server import ThreadingHTTPServer
        from sector_heatmap.delta_backtest_server import handler
        class Service:
            def status(self):return dict(state='IDLE',model='public research')
            def inspect(self,p):return plan(p,NOW)
            def start(self,p):return self.inspect(p)
            def cancel(self,p):return self.status()
        server=ThreadingHTTPServer(('127.0.0.1',0),handler(Service()))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            r=requests.get(base+'/api/delta-india/backtest/status',headers={'Origin':'http://127.0.0.1:8080'})
            self.assertEqual(r.status_code,200);self.assertEqual(r.headers['Access-Control-Allow-Origin'],'http://127.0.0.1:8080')
            self.assertEqual(r.headers['X-SectorPulse-Research'],'delta-public-v1')
            foreign=requests.post(base+'/api/delta-india/backtest/start',json=payload(),headers={'Origin':'https://example.com'})
            self.assertNotEqual(foreign.status_code,200);self.assertNotIn('Access-Control-Allow-Origin',foreign.headers)
            r=requests.post(base+'/api/delta-india/runner-start',json=payload())
            self.assertNotEqual(r.status_code,200)
            r=requests.post(base+'/api/delta-india/backtest/plan',json=payload())
            self.assertEqual(r.status_code,200);self.assertEqual(r.json()['combination_count'],3)
        finally:server.shutdown();server.server_close();thread.join(2)

    def test_public_reader_never_accepts_private_endpoints_and_reuses_worker(self):
        from unittest.mock import patch,Mock
        from sector_heatmap.delta_backtest_server import public_read,ensure_research_worker
        with patch('sector_heatmap.delta_backtest_server.requests.get') as read:
            for path in ('/v2/orders','/v2/wallet/balances','/v2/products/SOLUSD'):
                with self.assertRaises(ValueError):public_read(path)
            read.assert_not_called()
        with patch('sector_heatmap.delta_backtest_server.requests.get',return_value=Mock(headers={'X-SectorPulse-Research':'delta-public-v1'})),patch('subprocess.Popen') as start:
            self.assertIn('already running',ensure_research_worker());start.assert_not_called()
        with patch('sector_heatmap.delta_backtest_server.requests.get',return_value=Mock(headers={})),patch('subprocess.Popen') as start:
            self.assertIn('occupied',ensure_research_worker());start.assert_not_called()

if __name__=='__main__':unittest.main()

class ManualGridTests(unittest.TestCase):
    def test_selected_indicator_values_combine_and_ignore_unused_squeeze_values(self):
        p=payload();p.update(rsi_lengths=[10,14],ma_types=['EMA','SMA'],adx_modes=[False,True],adx_thresholds=[20,25],momentum_modes=[False,True],entry_rules=['CURRENT','CROSS_ONLY'],filters=['BASELINE'],bb_deviations=[1.5,2],squeeze_lookbacks=[50,100],release_windows=[2,3])
        result=plan(p,NOW);self.assertEqual(result['combination_count'],48)
        self.assertEqual({c['adx_enabled'] for c in result['combinations']},{False,True});self.assertEqual({c['momentum_enabled'] for c in result['combinations']},{False,True});self.assertEqual({c['entry_rule'] for c in result['combinations']},{'CURRENT','CROSS_ONLY'})
        self.assertEqual({c['adx_threshold'] for c in result['combinations'] if not c['adx_enabled']},{25})
        p=payload();p.update(bb_lengths=[20,30],bb_deviations=[1.5,2],squeeze_lookbacks=[50,100],squeeze_percentiles=[10,20],release_windows=[2,3]);result=plan(p,NOW)
        self.assertEqual(result['combination_count'],1+4+32)
        self.assertEqual(sum(c['filter']=='BASELINE' for c in result['combinations']),1)
    def test_grid_value_validation_and_early_cap(self):
        for changes in [dict(bb_deviations=[True]),dict(bb_deviations=[float('nan')]),dict(squeeze_lookbacks=[19]),dict(squeeze_percentiles=[51]),dict(release_windows=[11]),dict(adx_modes=[1]),dict(momentum_modes=[]),dict(entry_rules=['PRICE_EMA_CROSS'])]:
            p=payload();p.update(changes)
            with self.assertRaises(ValueError):plan(p,NOW)
        p=payload();p.update(rsi_lengths=list(range(10,18)),ma_lengths=list(range(10,18)),bb_deviations=[1,2,3,4])
        with self.assertRaisesRegex(ValueError,'96 cap'):plan(p,NOW)
    def test_bollinger_cache_covers_each_selected_parameter(self):
        # Different lookbacks/percentiles/release windows must never share a length-only cache.
        from unittest.mock import patch
        p=payload();p.update(filters=['BASELINE','SQUEEZE_RELEASE'],squeeze_lookbacks=[50,100],release_windows=[2,3]);config=plan(p,NOW);bounds=config['ranges']['5m'];raw=candles(300+576,start=bounds['fetch_start']);raw=[dict(r,timestamp=bounds['fetch_start']+i*300) for i,r in enumerate(raw)]
        meta={'contract_type':'perpetual_futures','notional_type':'vanilla','is_quanto':False,'quoting_currency':'USD','settlement_currency':'USD','contract_unit_currency':'BTC','underlying':'BTC','contract_value':'.001','tick_size':'.5'}
        with tempfile.TemporaryDirectory() as tmp:
            service=DeltaBacktest(tmp,None,lambda _:meta,lambda:NOW);service.job={'id':'test','state':'RUNNING','results':[],'completed':0,'plan':config};service._fetch=lambda *_:raw
            seen=[]
            def features(rows,cfg):seen.append((cfg['squeeze_lookback'],cfg['release_bars']));return bollinger_features(rows,cfg)
            import threading
            with patch('sector_heatmap.delta_backtest.bollinger_features',side_effect=features):service._run(config,threading.Event())
            self.assertEqual(service.status()['state'],'COMPLETE');self.assertEqual(set(seen),{(50,2),(50,3),(100,2),(100,3)})
