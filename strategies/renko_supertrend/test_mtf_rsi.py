import json
import unittest
from unittest.mock import patch
from . import mtf_rsi as mtf
from . import test_runner as fixtures
from .signals import series
from .runner import configuration, analysis, provisional


def candles(seconds, count=30, end=None, rising=True):
    end = count * seconds if end is None else end
    return [dict(timestamp=end-(count-i)*seconds,open=100+i if rising else 200-i,
                 high=101+i if rising else 201-i,low=99+i if rising else 199-i,
                 close=100+i if rising else 200-i) for i in range(count)]


def config(**extra):
    return dict(timeframe='1 minute', rsi_slope_length=14, rsi_htf_1_enabled=True,
                rsi_htf_1_timeframe='15 minutes',rsi_level_mode='THRESHOLD',
                rsi_bullish_above=60,rsi_bearish_below=40,**extra)


class RsiChecks(unittest.TestCase):
    def test_legacy_disabled_and_independent_slots(self):
        defaults=mtf.settings({})
        self.assertFalse(mtf.enabled(defaults))
        self.assertTrue(mtf.check({},defaults,'BULLISH',100)['allowed'])
        self.assertEqual(mtf.frames({**defaults,'rsi_htf_2_enabled':True}),['30 minutes'])
        raw={**config(),'rsi_htf_2_enabled':True,'rsi_htf_2_timeframe':'15 minutes'}
        self.assertEqual(mtf.frames(raw),['15 minutes'])
        self.assertEqual(len(mtf.check({'15 minutes':candles(900)},raw,'BULLISH',27000)['slots']),2)

    def test_configuration_validation_and_shared_levels(self):
        for raw in [config(rsi_htf_2_enabled='yes'),{**config(),'rsi_htf_1_timeframe':'1 minute'},
                    {**config(),'rsi_htf_1_timeframe':'2 minutes','broker':'DELTA_INDIA'},
                    {**config(),'rsi_bullish_above':float('nan')},
                    {**config(),'rsi_bullish_min':81,'rsi_bullish_max':80}]:
            with self.assertRaises(ValueError):mtf.settings(raw)
        result=mtf.query_settings({k:[str(v).lower() if isinstance(v,bool) else str(v)] for k,v in config().items()})
        self.assertEqual(result['rsi_bullish_above'],60)
        self.assertTrue(result['rsi_htf_1_enabled'])

    def test_exact_shared_threshold_and_range_boundaries(self):
        c=config()
        self.assertFalse(mtf.matches(60,'BULLISH',c));self.assertTrue(mtf.matches(60.01,'BULLISH',c))
        self.assertFalse(mtf.matches(40,'BEARISH',c));self.assertTrue(mtf.matches(39.99,'BEARISH',c))
        c.update(rsi_level_mode='BETWEEN',rsi_bullish_min=60,rsi_bullish_max=80,rsi_bearish_min=35,rsi_bearish_max=40)
        for value in (60,80):self.assertTrue(mtf.matches(value,'BULLISH',c))
        for value in (35,40):self.assertTrue(mtf.matches(value,'BEARISH',c))
        self.assertFalse(mtf.matches(81,'BULLISH',c));self.assertFalse(mtf.matches(34,'BEARISH',c))
        self.assertFalse(mtf.matches(70,'NEUTRAL',c))

    def test_future_forming_stale_missing_and_gap_evidence(self):
        c=config();rows=candles(900);at=27000
        baseline=mtf.check({'15 minutes':rows},c,'BULLISH',at)
        self.assertTrue(baseline['allowed']);self.assertEqual(baseline['slots'][0]['closed_at'],at)
        future=dict(timestamp=at,open=-100,high=-1,low=-100,close=-50)
        self.assertEqual(mtf.check({'15 minutes':rows+[future]},c,'BULLISH',at),baseline)
        forming={**rows[-1],'is_forming':True}
        self.assertFalse(mtf.check({'15 minutes':rows[:-1]+[forming]},c,'BULLISH',at)['allowed'])
        for source,event in [([],at),(rows,at+900),(rows[:-1],at)]:
            gate=mtf.check({'15 minutes':source},c,'BULLISH',event)
            self.assertFalse(gate['allowed']);self.assertEqual(gate['slots'][0]['reason'],'MISSING_OR_STALE')
        gate=mtf.check({'15 minutes':rows[:20]+rows[21:]},c,'BULLISH',at)
        self.assertFalse(gate['allowed']);self.assertEqual(gate['slots'][0]['reason'],'WARMUP')
        self.assertFalse(mtf.check({'15 minutes':candles(900,10)},c,'BULLISH',9000)['allowed'])

    def test_all_three_must_pass_and_every_slot_can_be_disabled(self):
        c={**config(),'rsi_htf_2_enabled':True,'rsi_htf_2_timeframe':'30 minutes',
           'rsi_htf_3_enabled':True,'rsi_htf_3_timeframe':'1 hour'}
        at=108000;sources={frame:candles(seconds,end=at) for frame,seconds in [('15 minutes',900),('30 minutes',1800),('1 hour',3600)]}
        self.assertTrue(mtf.check(sources,c,'BULLISH',at)['allowed'])
        sources['1 hour']=candles(3600,end=at,rising=False)
        self.assertFalse(mtf.check(sources,c,'BULLISH',at)['allowed'])
        c['rsi_htf_3_enabled']=False
        self.assertTrue(mtf.check(sources,c,'BULLISH',at)['allowed'])

    def test_chart_replay_uses_closed_htf_at_each_historical_event(self):
        c={**config(),'chart_entry_guards':True,'_chart_rsi_rows':{'15 minutes':candles(900)},'session_deadline':None}
        hosts=candles(60,450);rows=series(hosts,c)
        self.assertFalse(rows[0]['mtf_rsi']['allowed'])
        self.assertTrue(rows[-1]['mtf_rsi']['allowed'])
        for row in rows:
            point=row['mtf_rsi']['slots'][0]
            if point['closed_at'] is not None:self.assertLessEqual(point['closed_at'],row['timestamp']+60)
        c['_chart_rsi_rows']['15 minutes'].append(dict(timestamp=27000,open=1,high=1,low=1,close=1))
        self.assertEqual(rows,series(hosts,c))
        legacy={k:v for k,v in c.items() if not k.startswith('rsi_htf_') and k!='_chart_rsi_rows'}
        self.assertEqual(series(hosts,legacy),series(hosts,{**legacy,**mtf.settings({})}))


    def test_intrabar_chart_uses_tick_time_not_future_host_close(self):
        c={**config(),'underlying':'NSE:NIFTY50-INDEX','chart_entry_guards':True,'session_deadline':'23:59','_chart_rsi_rows':{'15 minutes':candles(900)}}
        host=candles(60,449)
        confirmed=analysis(host,c,.05,retain=None)
        forming=dict(timestamp=26940,open=550,high=552,low=549,close=551,is_forming=True,stream_exchange_at=26960)
        candidate=provisional(confirmed,forming,c,.05,26960)
        gate=candidate['mtf_rsi']
        self.assertEqual(gate['observed_at'],26960)
        self.assertEqual(gate['slots'][0]['closed_at'],26100)
        self.assertLessEqual(gate['slots'][0]['closed_at'],candidate['market_event_at'])


class RunnerRsiChecks(unittest.TestCase):
    setUp=fixtures.RenkoLifecycleTests.setUp
    start=fixtures.RenkoLifecycleTests.start
    append=fixtures.RenkoLifecycleTests.append

    def source(self, rising=True):
        self.c.update(rsi_htf_1_enabled=True,rsi_htf_1_timeframe='15 minutes',rsi_bullish_above=60,rsi_bearish_below=40)
        original=self.b.candles
        end=int(self.b.now//900)*900
        self.b.candles=lambda c:candles(900,end=end,rising=rising) if c['timeframe']=='15 minutes' else original(c)

    def test_real_entry_gate_paper_fill_snapshot_and_exits_independent(self):
        self.source();self.start();self.r.step()
        self.assertIsNotNone(self.r.state['position'])
        evidence=self.r.state['position']['entry_indicator_snapshot']
        self.assertTrue(evidence['indicators']['mtf_rsi']['allowed'])
        self.assertTrue(evidence['mtf_rsi_preflight']['allowed'])
        original=self.b.candles
        self.b.candles=lambda c:[] if c['timeframe']=='15 minutes' else original(c)
        self.append(80);self.r.step()
        self.assertIsNone(self.r.state['position']);self.assertEqual(self.b.sent,[])

    def test_opposing_rsi_blocks_before_any_order(self):
        self.source(False);self.start();self.r.step()
        self.assertIsNone(self.r.state['position'])
        self.assertEqual(self.r.state['latest_entry_assessment']['code'],'RSI_HIGHER_TIMEFRAME')
        self.assertEqual(self.r.state.get('order_history',[]),[]);self.assertEqual(self.b.sent,[])

    def test_fresh_preflight_and_entry_authorization_recheck(self):
        self.source();self.start();self.r.signal()
        with patch.object(self.r,'rsi_agreement',return_value=dict(allowed=False,reason='RSI changed')):
            with self.assertRaisesRegex(ValueError,'RSI changed'):
                self.r.submit(dict(symbol='NSE:TESTCE',side=1,qty=20),dict(symbol='NSE:TESTCE',direction='BULLISH'),'RENKO_EMA_ENTRY')
            with self.assertRaisesRegex(ValueError,'RSI changed'):
                self.r.validate_entry_authorization(dict(direction='BULLISH'))
        self.assertEqual(self.r.state.get('order_history',[]),[]);self.assertEqual(self.b.sent,[])

    def test_disabled_slots_do_not_fetch_and_enabled_sources_keep_native_context(self):
        self.r.state['config']=configuration(self.c)
        with patch.object(self.b,'candles',side_effect=AssertionError('Unexpected history fetch')):
            self.assertTrue(self.r.rsi_agreement('BULLISH',self.b.now)['allowed'])
        self.source();self.start()
        original=self.b.candles;seen=[]
        def native(c):
            seen.append((c['underlying'],c['timeframe']))
            return original(c)
        self.b.candles=native
        self.assertTrue(self.r.rsi_agreement('BULLISH',self.b.now)['allowed'])
        self.assertEqual(seen,[(self.c['underlying'],'15 minutes')])
        self.b.candles=lambda c:(_ for _ in ()).throw(ValueError('Native feed unavailable'))
        gate=self.r.rsi_agreement('BULLISH',self.b.now)
        self.assertFalse(gate['allowed']);self.assertEqual(gate['slots'][0]['source_error'],'Native feed unavailable')

    def test_settings_saved_for_next_start_without_changing_active_config(self):
        self.start();before=json.loads(json.dumps(self.r.state['config']))
        self.r.save_preferences({'settings':{'rsi-htf-1-enabled':True,'rsi-htf-1-timeframe':'15 minutes'}})
        self.assertEqual(self.r.state['config'],before)
        self.assertFalse(mtf.enabled(before))
        self.assertEqual(self.r.snapshot()['mtf_rsi_revision'],mtf.REVISION)
        self.assertTrue(self.r.read_preferences()['settings']['rsi-htf-1-enabled'])
