import unittest
from core import sizes
from updated_sizing_policy import convert
from live import choose
from unittest.mock import patch
class Tests(unittest.TestCase):
    def test_factors_are_classification_only_and_ignore_delta_magnitude(self):
        for mode,factor in [('OTM',.25),('ATM',.5)]:
            for delta in [.1,.5,.9,-.1,-.9]:
                base,premium=sizes(400,delta,option_moneyness=mode)
                self.assertEqual(base,400/12);self.assertEqual(premium,base*factor)
    def test_all_parent_markets_preserve_base_and_classification_factor(self):
        for segment in ['INDEX','EQUITY','MCX_COMMODITY','CRYPTO','GLOBAL_COMMODITY']:
            for mode,factor in [('OTM',.25),('ATM',.5)]:
                base=convert(1000,segment=segment)['brick']
                option=convert(1000,segment=segment,is_option=True,option_moneyness=mode)
                self.assertEqual(option['brick'],base*factor)
                self.assertEqual(option['option_multiplier'],factor)
    def test_configuration_does_not_infer_classification_from_premium(self):
        from ui_bridge import configuration
        for premium in [5,40,100,500]:
            for mode,factor in [('OTM',.25),('ATM',.5)]:
                payload=dict(account_id='owner',broker='FYERS',underlying='NSE:NIFTY50-INDEX',timeframe='5 minutes',ai_execution_route='OPTIONS',target_premium=premium,ai_option_moneyness=mode)
                with patch('ui_bridge.owner_broker',return_value='FYERS'),patch('native_reference.resolve_reference',return_value=None):
                    c=configuration(payload,'owner')
                self.assertEqual(c['option_multiplier'],factor)
                self.assertEqual(c['option_moneyness'],mode)
    def test_atm_selects_nearest_strike_not_cheapest_or_target_premium(self):
        expiry='4102444800'
        class API:
            def optionchain(self,**kw):return dict(s='ok',data=dict(expiryData=[dict(expiry=expiry)],optionsChain=[
                dict(symbol='NSE:NIFTY50-INDEX',ex_symbol='NIFTY',ltp=101),
                dict(symbol='NSE:NEARCE',option_type='CE',strike_price=100,ltp=100,greeks=dict(delta=.5)),
                dict(symbol='NSE:FARCE',option_type='CE',strike_price=120,ltp=40,greeks=dict(delta=.1))]))
        master=lambda s:dict(expiry_epoch=expiry,option_type='CE',underlying_asset='NIFTY',lot_size=65)
        config=dict(underlying='NSE:NIFTY50-INDEX',market='NSE',reference_value=400,target_premium=40)
        atm,_=choose(API(),master,dict(config,option_moneyness='ATM'),'CE')
        otm,_=choose(API(),master,dict(config,option_moneyness='OTM'),'CE')
        self.assertEqual(atm['symbol'],'NSE:NEARCE');self.assertEqual(otm['symbol'],'NSE:FARCE')
        with self.assertRaisesRegex(ValueError,'not the current ATM'):
            choose(API(),master,dict(config,option_moneyness='ATM'),'CE',exact_symbol='NSE:FARCE')
