import json,tempfile,unittest
from pathlib import Path
from .indicator_families import apply,restore,FAMILIES,DEFAULTS
from .signals import settings,Engine
from .runner import configuration
from .exit_indicators import reason
from . import preferences,destinations
class IndicatorFamilyTests(unittest.TestCase):
    def test_legacy_defaults_and_no_input_mutation(self):
        raw={'ema_fast_enabled':True,'retest_enabled':True}
        effective=apply(raw)
        self.assertEqual(raw,{'ema_fast_enabled':True,'retest_enabled':True})
        self.assertTrue(effective['ema_fast_enabled'])
        self.assertTrue(all(effective[k] for k in DEFAULTS))
    def test_every_master_masks_all_rules_and_roundtrips_choices(self):
        for family,keys in FAMILIES.items():
            with self.subTest(family=family):
                raw={k:True for rules in FAMILIES.values() for k in rules}
                raw[family+'_family_enabled']=False
                c=apply(raw)
                self.assertTrue(all(c[k] is False for k in keys))
                self.assertTrue(all(c['indicator_family_choices'][k] for k in keys))
                c[family+'_family_enabled']=True
                resumed=apply(json.loads(json.dumps(c)))
                self.assertTrue(all(resumed[k] for k in keys))
    def test_ema_off_disables_retest_and_exits_but_keeps_chart_choices(self):
        c=apply(dict(ema_family_enabled=False,ema_fast_enabled=True,retest_enabled=True,ema_exit_enabled=True,ema_exit_enabled_indicator=True))
        self.assertFalse(c['retest_enabled']);self.assertFalse(c['ema_exit_enabled'])
        self.assertTrue(c['ema_exit_enabled_indicator'])
        self.assertTrue(destinations.chart(c)['ema_exit_enabled'])
        self.assertNotIn('ema_family_enabled',destinations.chart(c))
    def test_disabled_rsi_adx_and_ema_do_not_block_supertrend_flip(self):
        from .indicator_selection import qualify
        cfg=settings(dict(ema_family_enabled=False,rsi_family_enabled=False,adx_family_enabled=False,rsi_level_enabled=True,rsi_slope_enabled=True,use_adx=True,retest_enabled=True))
        direction,ok,why=qualify(cfg,100,200,300,-1,True,False,'BULLISH',{'rsi14':1,'rsi14_slope':-10})
        self.assertTrue(ok,why);self.assertEqual(direction,-1)
        self.assertFalse(cfg['retest_enabled']);self.assertFalse(cfg['use_adx'])
    def test_family_off_cannot_exit_through_saved_rule(self):
        sig=dict(close=1,ema30=100,rsi14_slope=-1,adx=0,supertrend_cross_direction='BEARISH',exit_market_structure={'state':'BEARISH_LH_LL'})
        for family,rule in [('ema','ema_slow_exit_enabled'),('rsi','rsi_exit_enabled'),('adx','adx_exit_enabled'),('supertrend','supertrend_exit_enabled'),('structure','market_structure_exit_enabled')]:
            c={k:False for keys in FAMILIES.values() for k in keys};c.update({rule:True,family+'_family_enabled':False})
            self.assertIsNone(reason(c,sig,'BULLISH'),family)
    def test_invalid_master_is_rejected(self):
        for value in ['false',0,None]:
            with self.assertRaises(ValueError):apply({'ema_family_enabled':value})
    def test_preferences_preserve_subchoices_without_activation(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'prefs.json'
            fields={'ema-family-enabled':False,'ema-fast-enabled':True,'retest-enabled':True,'ema-exit-enabled':True,'ema-fast-length':10}
            preferences.write(p,{'settings':fields},10)
            self.assertEqual(preferences.read(p)['settings'],fields)
    def test_start_configuration_preserves_choices_masks_runtime_and_requires_direction(self):
        raw=dict(strategy='RENKO_SUPERTREND_V1',exit_policy='OPPOSITE_CONFIRMED_SIGNAL',underlying='NSE:NIFTY50-INDEX',timeframe='5 minutes',mode='PAPER',lots=1,max_trades=2,ema_family_enabled=False,rsi_family_enabled=False,ema_fast_enabled=True,retest_enabled=True,ema_exit_enabled=True)
        c=configuration(raw)
        self.assertFalse(c['ema_exit_enabled']);self.assertFalse(c['retest_enabled'])
        self.assertTrue(c['indicator_family_choices']['ema_exit_enabled'])
        self.assertTrue(c['indicator_family_choices']['retest_enabled'])
        raw.update(supertrend_family_enabled=False)
        with self.assertRaisesRegex(ValueError,'directional'):configuration(raw)
