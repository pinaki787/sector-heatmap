import copy,math,unittest,tempfile
from pathlib import Path
from strategies.renko_supertrend import anti_chop as a
from strategies.renko_supertrend.signals import Engine,settings
from strategies.renko_supertrend.preferences import write,read
from strategies.renko_supertrend.runner import Runner

def candle(i,seconds=300):
    price=100+i;spread=1+i*.025
    return dict(timestamp=1800000000+i*seconds,open=price-.2,high=price+spread,low=price-spread,close=price,volume=1)

class AntiChopTests(unittest.TestCase):
    def config(self,**extra):return dict(a.DEFAULTS,anti_chop_enabled=True,anti_chop_mode='Manual',anti_chop_slope_atr=.01,anti_chop_gap_atr=.01,anti_chop_overlap_percent=100,**extra)
    def test_trend_confirmation_truth_table_and_warmup(self):
        from itertools import product
        for values in product((False,True),repeat=4):
            checks=[dict(key=k,passed=v) for k,v in zip(('atr','slope','separation','structure'),values)]
            expected=values[1] and values[2] and (values[0] or values[3])
            allowed,result=a.combine(checks,True,'Trend')
            self.assertEqual(allowed,expected)
            self.assertFalse(a.combine(checks,False,'Trend')[0])
            self.assertEqual(a.combine(checks,True,'All')[0],all(values))
            self.assertEqual(len([x for x in result if x.get('mandatory') is False]),2)
            self.assertEqual(checks,[dict(key=k,passed=v) for k,v in zip(('atr','slope','separation','structure'),values)])
    def test_confirmation_save_and_validation(self):
        with self.assertRaises(ValueError):a.settings({'anti_chop_combination':'anything'})
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'prefs.json';write(p,{'settings':{'anti-chop-combination':'Trend','anti-chop-enabled':True,'anti-chop-role':'Entry','ema-exit-enabled':True,'ema-exit-length':10}},1)
            self.assertEqual(read(p)['settings']['anti-chop-combination'],'Trend')
    def test_runner_accepts_standalone_entry_and_ema_exit(self):
        from strategies.renko_supertrend.runner import configuration
        c=dict(strategy='RENKO_SUPERTREND_V1',underlying='NSE:NIFTY50-INDEX',timeframe='1 minute',lots=1,mode='PAPER',exit_policy='OPPOSITE_CONFIRMED_SIGNAL',anti_chop_enabled=True,anti_chop_role='Entry',supertrend_enabled=False,ema_fast_enabled=False,ema_slow_enabled=False,ema_third_enabled=False,ema_widening_enabled=False,rsi_slope_enabled=False,rsi_level_enabled=False,ema_exit_enabled=True,ema_exit_length=10)
        result=configuration(c)
        self.assertEqual(result['anti_chop_role'],'Entry');self.assertEqual(result['ema_exit_length'],10)
        with self.assertRaises(ValueError):configuration({**c,'anti_chop_role':'Filter'})
    def test_standalone_direction_and_episode(self):
        for sign,expected in [(1,'BULLISH'),(-1,'BEARISH')]:
            cfg=self.config(anti_chop_role='Entry');s={};entry={};events=[]
            for i in range(100):
                c=candle(i)
                if sign<0:
                    c.update(open=500-c['open'],high=500-c['low'],low=500-c['high'],close=500-c['close'])
                gate=a.observe(s,c,cfg,'NEUTRAL')
                a.generate_entry(entry,gate,s)
                if entry['entry_direction']:events.append(entry['entry_direction'])
            self.assertEqual(gate['direction'],expected);self.assertTrue(entry['entry_qualified'])
            self.assertEqual(events,[expected])
            a.generate_entry(entry,{**gate,'allowed':False},s);self.assertFalse(entry['entry_qualified'])
            a.generate_entry(entry,gate,s);self.assertEqual(entry['entry_direction'],expected)
    def test_chart_only_ema_does_not_conflict_with_standalone(self):
        cfg=self.config(anti_chop_role='Entry');cfg.update(chart_entry_guards=True,timeframe='1 minute')
        engine=Engine(cfg)
        for i in range(100):result=engine.update(candle(i,60))
        self.assertEqual(result['direction'],'BULLISH')
    def test_standalone_rejects_other_entry_rules(self):
        with self.assertRaises(ValueError):a.standalone_rules(dict(anti_chop_enabled=True,anti_chop_role='Entry',supertrend_enabled=True))
        a.standalone_rules(dict(anti_chop_enabled=True,anti_chop_role='Entry',ema_exit_enabled=True))
    def test_standalone_engine_emits_without_base_entries(self):
        cfg=self.config(anti_chop_role='Entry')
        cfg.update(supertrend_enabled=False,ema_fast_enabled=False,ema_slow_enabled=False,ema_third_enabled=False,ema_widening_enabled=False,rsi_slope_enabled=False,rsi_level_enabled=False,timeframe='1 minute',brick_mode='Manual',manual_brick=1)
        engine=Engine(cfg);events=[]
        for i in range(100):
            result=engine.update(candle(i,60))
            if result['entry_direction']:events.append(result['entry_direction'])
        self.assertEqual(events,['BULLISH']);self.assertEqual(result['direction'],'BULLISH')
    def test_off_preserves_state(self):
        s={};gate=a.observe(s,candle(0),{},'BULLISH');self.assertTrue(gate['allowed']);self.assertEqual(s,{})
    def test_settings_validation_and_zero_overlap(self):
        self.assertEqual(a.settings({'anti_chop_overlap_percent':0})['anti_chop_overlap_percent'],0)
        for payload in [dict(anti_chop_enabled='false'),dict(anti_chop_slope_bars=True),dict(anti_chop_structure_bars=1),dict(anti_chop_overlap_percent=101),dict(anti_chop_gap_atr=float('nan'))]:
            with self.assertRaises(ValueError):a.settings(payload)
    def test_follows_all_host_timeframes(self):
        for frame,seconds in [('1 minute',60),('2 minutes',120),('3 minutes',180),('5 minutes',300),('10 minutes',600),('15 minutes',900),('30 minutes',1800),('1 hour',3600)]:
            c=self.config();c['timeframe']=frame;s={}
            for i in range(100):g=a.observe(s,candle(i,seconds),c,'BULLISH',seconds)
            self.assertTrue(g['ready']);self.assertTrue(g['allowed'],(frame,g))
            self.assertEqual(len(g['checks']),4)
    def test_warmup_and_direction_alignment_fail_closed(self):
        s={};c=self.config()
        for i in range(49):g=a.observe(s,candle(i),c,'BULLISH')
        self.assertFalse(g['ready']);self.assertFalse(g['allowed'])
        for i in range(49,100):g=a.observe(s,candle(i),c,'BEARISH')
        self.assertFalse(g['allowed']);self.assertFalse(g['checks'][1]['passed'])
    def test_forming_does_not_mutate_confirmed_state(self):
        s={};before=copy.deepcopy(s);g=a.observe(s,{**candle(0),'is_forming':True},self.config(),'BULLISH')
        self.assertEqual(s,before);self.assertFalse(g['allowed'])
    def test_missing_bar_resets_structure(self):
        s={};c=self.config()
        for i in range(100):a.observe(s,candle(i),c,'BULLISH')
        g=a.observe(s,candle(102),c,'BULLISH');self.assertFalse(g['checks'][3]['passed'])
    def test_entry_filter_does_not_change_indicator_or_exit_math(self):
        base=dict(timeframe='1 minute',brick_mode='Manual',manual_brick=1,rsi_slope_enabled=False)
        off=Engine(base);on=Engine(dict(base,anti_chop_enabled=True))
        for i in range(100):
            c=candle(i,60);x=off.update(c);y=on.update(c)
            for key in ('supertrend','synthetic_close','box','ema10','ema30','ema100','cross_direction'):self.assertEqual(x[key],y[key],key)
            self.assertIn('anti_chop',y)
    def test_adaptive_thresholds_use_prior_candles_only(self):
        c=self.config();c.update(anti_chop_mode='Adaptive',anti_chop_adaptive_window=20)
        s={}
        for i in range(100):a.observe(s,candle(i),c,'BULLISH')
        prior=copy.deepcopy(s['anti_chop']['adaptive_history'])
        g=a.observe(s,candle(100),c,'BULLISH')
        def quantile(values,p):
            v=sorted(values);x=(len(v)-1)*p/100;j=int(x);return v[j]+(v[min(j+1,len(v)-1)]-v[j])*(x-j)
        self.assertTrue(g['calibration']['ready'])
        self.assertAlmostEqual(g['thresholds']['slope_atr'],quantile([x[0] for x in prior],60))
        self.assertAlmostEqual(g['thresholds']['gap_atr'],quantile([x[1] for x in prior],60))
        self.assertEqual(g['mode'],'Adaptive')
    def test_adaptive_is_scale_invariant_across_price_units(self):
        c=self.config();c.update(anti_chop_mode='Adaptive',anti_chop_adaptive_window=20)
        left={};right={}
        for i in range(120):
            x=candle(i);y={k:(v*10 if k in ('open','high','low','close') else v) for k,v in x.items()}
            g=a.observe(left,x,c,'BULLISH');h=a.observe(right,y,c,'BULLISH')
            self.assertEqual(g['allowed'],h['allowed'])
            if g['ready']:
                self.assertAlmostEqual(g['thresholds']['slope_atr'],h['thresholds']['slope_atr'],places=8)
                self.assertAlmostEqual(g['thresholds']['gap_atr'],h['thresholds']['gap_atr'],places=8)
    def test_configurable_ten_thirty_pair_and_atr_periods(self):
        c=self.config();c.update(anti_chop_ema_fast_length=10,anti_chop_ema_slow_length=30,anti_chop_atr_length=10,anti_chop_atr_average_length=30)
        s={}
        for i in range(100):g=a.observe(s,candle(i),c,'BULLISH')
        self.assertEqual(g['periods'],dict(atr=10,atr_average=30,ema_fast=10,ema_slow=30))
        self.assertEqual(g['checks'][0]['label'],'ATR10 above its 30-bar average')
        self.assertEqual(g['checks'][1]['label'],'EMA10 directional slope')
    def test_provisional_entry_combination_rejected(self):
        with self.assertRaises(ValueError):a.compatible(dict(anti_chop_enabled=True,intrabar_entries=True))
    def test_chart_query_deserializes_boolean_and_dynamic_periods(self):
        from .delta_service import Service
        class Broker:
            def session_policy(self,config):return {}
        service=Service.__new__(Service);service.instrument=None;service.chart_broker=Broker()
        for flag in ('true','false'):
            c=service.chart_config({'symbol':['BTCUSD'],'timeframe':['1 minute'],'anti_chop_enabled':[flag],'anti_chop_mode':['Adaptive'],'anti_chop_ema_fast_length':['10'],'anti_chop_ema_slow_length':['30']})
            self.assertEqual(c['anti_chop_enabled'],flag=='true');self.assertEqual(c['anti_chop_ema_fast_length'],10);self.assertEqual(c['anti_chop_ema_slow_length'],30)
    def test_preferences_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'prefs.json';fields={k.replace('_','-'):v for k,v in self.config().items()};fields['timeframe']='1 minute'
            write(p,{'settings':fields},123)
            saved=read(p)['settings'];self.assertTrue(saved['anti-chop-enabled']);self.assertEqual(saved['anti-chop-overlap-percent'],100)
    def test_submit_gate_rejects_missing_or_wrong_direction_evidence(self):
        r=Runner.__new__(Runner);r.clock=lambda:3600
        r.state={'config':dict(timeframe='1 minute',anti_chop_enabled=True),'last_signal':{'timestamp':3540}}
        with self.assertRaises(ValueError):r.anti_chop_entry_gate('BULLISH')
        r.state['last_signal']['anti_chop']=dict(revision=a.REVISION,ready=True,allowed=True,direction='BULLISH',last_completed_at=3540)
        r.anti_chop_entry_gate('BULLISH')
        with self.assertRaises(ValueError):r.anti_chop_entry_gate('BEARISH')
        r.clock=lambda:3661
        with self.assertRaises(ValueError):r.anti_chop_entry_gate('BULLISH')
if __name__=='__main__':unittest.main()
