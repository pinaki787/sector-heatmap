import unittest
from unittest.mock import Mock,patch
from live import nearest_expiry,choose
class ExpiryTests(unittest.TestCase):
    def test_nearest_provider_epoch_and_cutoff(self):
        data={'expiryData':[{'expiry':'300'},{'expiry':'100'},{'expiry':'200'},{'expiry':'bad'}]}
        self.assertEqual(nearest_expiry(data,100),'200')
        self.assertEqual(nearest_expiry(data,199),'200')
        self.assertEqual(nearest_expiry(data,200),'300')
        with self.assertRaises(ValueError):nearest_expiry(data,300)
    def test_no_fabricated_calendar(self):
        with self.assertRaises(ValueError):nearest_expiry({'expiryData':[]},100)
    def test_auto_selection_ignores_old_manual_expiry(self):
        api=Mock();data={'expiryData':[{'expiry':'300'},{'expiry':'200'}],'optionsChain':[{'symbol':'NSE:NIFTY50-INDEX','option_type':''},
            {'symbol':'NSE:NIFTY-A','option_type':'CE','ltp':38,'greeks':{'delta':.2}},
            {'symbol':'NSE:NIFTY-B','option_type':'CE','ltp':41,'greeks':{'delta':.19}}]}
        api.optionchain.return_value={'s':'ok','data':data}
        master=Mock(return_value={'expiry_epoch':'200','option_type':'CE','lot_size':65})
        with patch('live.time.time',return_value=100):
            contract,delta=choose(api,master,{'expiry':'300','reference_value':250,'underlying':'NSE:NIFTY50-INDEX'},'CE')
        self.assertEqual(contract['expiry'],'200');self.assertEqual(contract['symbol'],'NSE:NIFTY-B')
        self.assertEqual(api.optionchain.call_args.kwargs['data']['timestamp'],'200')
    def test_master_mismatch_fails_closed(self):
        api=Mock();api.optionchain.return_value={'s':'ok','data':{'expiryData':[{'expiry':'200'}],'optionsChain':[{'symbol':'NSE:NIFTY50-INDEX','option_type':''},{'symbol':'NSE:NIFTY-A','option_type':'CE','ltp':40}]}}
        master=Mock(return_value={'expiry_epoch':'300','option_type':'CE'})
        with patch('live.time.time',return_value=100),self.assertRaisesRegex(ValueError,'mismatch'):choose(api,master,{'reference_value':250,'underlying':'NSE:NIFTY50-INDEX'},'CE')

class ScalingTests(unittest.TestCase):
    def test_selected_market_thirty_minute_divisors(self):
        from sizing_policy import scale_reference
        for market,asset,divisor in [('NSE',None,12),('BSE',None,12),('CRYPTO',None,46),('MCX','GOLD',44),('MCX','SILVER',28)]:
            for execution_minutes in [1,5,30]:
                result=scale_reference(400,market,asset,delta=.19)
                self.assertEqual(result['divisor'],divisor)
                self.assertEqual(result['base_brick'],400/divisor)
                self.assertEqual(result['premium_brick'],400/divisor*.19)
        self.assertIsNone(scale_reference(400,'CRYPTO')['premium_brick'])

    def test_direct_futures_and_stock_option_identity(self):
        from sizing_policy import size_instrument
        btc={'market':'CRYPTO','underlying':'BTCUSD','product_type':'PERPETUAL'}
        r={'symbol':'BTCUSD','parent_hours':23,'atr_length':5,'native_box':4600}
        self.assertEqual(size_instrument(btc,r)['brick'],100)
        with self.assertRaises(ValueError):size_instrument(btc,r,delta=.5)
        stock={'market':'NSE','underlying':'NSE:CUPID-EQ','product_type':'OPTION'}
        r={'symbol':'NSE:CUPID-EQ','parent_hours':6,'atr_length':5,'native_box':120,'chart_session':'Regular trading hours'}
        self.assertEqual(size_instrument(stock,r,delta=-.4)['brick'],4)
        with self.assertRaises(ValueError):size_instrument(stock,dict(r,symbol='NSE:NIFTY50-INDEX'),delta=.4)
        with self.assertRaises(ValueError):size_instrument({'market':'FOREX','underlying':'EURUSD','product_type':'FOREX'},r)

    def test_two_selected_underlyings_reach_fyers_chain(self):
        from live import choose
        for underlying,symbol in [('NSE:CUPID-EQ','NSE:CUPID26NOV300CE'),('BSE:SENSEX-INDEX','BSE:SENSEX26NOV80000CE')]:
            api=Mock();api.optionchain.return_value={'s':'ok','data':{'expiryData':[{'expiry':'200'}],'optionsChain':[{'symbol':underlying,'option_type':''},{'symbol':symbol,'option_type':'CE','ltp':40,'greeks':{'delta':.4}}]}}
            master=Mock(return_value={'expiry_epoch':'200','option_type':'CE','lot_size':1,'underlying_asset':underlying})
            with patch('live.time.time',return_value=100):c,d=choose(api,master,{'underlying':underlying,'reference_value':120},'CE')
            self.assertEqual(c['underlying'],underlying);self.assertEqual(c['symbol'],symbol)
            self.assertEqual(api.optionchain.call_args.kwargs['data']['symbol'],underlying)
