import unittest
from updated_sizing_policy import convert,from_selected_broker
class UpdatedSizingTests(unittest.TestCase):
    def test_nifty_known_reference_and_option_division(self):
        self.assertAlmostEqual(convert(400,segment="INDEX")["brick"],400/12)
        self.assertAlmostEqual(convert(400,segment="INDEX",is_option=True)["brick"],400/48)
    def test_all_segment_timeframes_and_atr(self):
        for segment,hours,length in [("INDEX",6,5),("EQUITY",6,5),("STOCK_OPTION",6,5),("MCX_COMMODITY",14,5),("CRYPTO",23,7),("GLOBAL_COMMODITY",22,7)]:
            with self.subTest(segment=segment):
                result=convert(1000,segment=segment,is_option=segment=="STOCK_OPTION")
                self.assertEqual((result["parent_hours"],result["atr_length"]),(hours,length))
                self.assertEqual(result["divisor"],hours*2)
    def test_every_option_has_exact_extra_division(self):
        for segment in ("INDEX","EQUITY","MCX_COMMODITY","CRYPTO","GLOBAL_COMMODITY"):
            self.assertEqual(convert(997,segment=segment,is_option=True)["brick"],convert(997,segment=segment)["brick"]/4)
    def context(self):
        return dict(broker="FYERS",account="test-account",symbol="NSE:NIFTY50-INDEX",chart_type="Renko",
                    session="Regular trading hours",parent_hours=6,atr_length=5,
                    verified_native_size=True,completed_parent=True,as_of="2026-11-20",brick=400)
    def call(self,reference):
        return from_selected_broker(reference,selected_broker="FYERS",selected_account="test-account",
                                    selected_symbol="NSE:NIFTY50-INDEX",segment="INDEX")
    def test_context_acceptance(self):
        self.assertAlmostEqual(self.call(self.context())["brick"],400/12)
    def test_cross_account_broker_symbol_and_candle_substitution_rejected(self):
        for key,value in [("broker","DELTA_INDIA"),("account","other"),("symbol","MCX:CRUDEOIL"),("chart_type","Candles"),
                          ("session","Extended"),("parent_hours",14),("atr_length",7),("verified_native_size",False),
                          ("completed_parent",False),("as_of",None)]:
            with self.subTest(key=key):
                r=self.context();r[key]=value
                with self.assertRaises(ValueError):self.call(r)
    def test_invalid_values_rejected(self):
        for value in (0,-1,True,float("nan"),float("inf")):
            with self.assertRaises(ValueError):convert(value,segment="INDEX")
if __name__=="__main__":unittest.main()


class RuntimeConversionTests(unittest.TestCase):
    def test_option_runtime_uses_quarter_base_for_distinct_selection_deltas(self):
        from core import sizes
        for delta in (.19,.85,-.4):
            self.assertEqual(sizes(400,delta),(400/12,400/48))
    def test_mcx_exchange_wins_over_asset_and_category(self):
        from sizing_policy import scale_reference
        for asset in ('GOLD','SILVER'):
            result=scale_reference(784,'MCX',asset,delta=.8,explicit_category='GOLD')
            self.assertEqual((result['parent_hours'],result['atr_length'],result['premium_brick']),(14,5,7))
    def test_crypto_and_global_require_atr_seven(self):
        from sizing_policy import size_instrument
        for market,asset,hours in [('CRYPTO',None,23),('GLOBAL_COMMODITY','SILVER',22)]:
            instrument=dict(market=market,asset=asset,underlying='fixture',product_type='PERPETUAL')
            reference=dict(symbol='fixture',parent_hours=hours,atr_length=5,native_box=440,chart_session='Regular trading hours')
            with self.assertRaises(ValueError):size_instrument(instrument,reference)
            self.assertEqual(size_instrument(instrument,dict(reference,atr_length=7))['atr_length'],7)

class ParentCandleContractTests(unittest.TestCase):
    def test_every_market_has_exact_parent_candle_periods_in_renko_regular_mode(self):
        from sizing_policy import instrument_contract
        for market,asset,hours,length,divisor in [('NSE',None,6,5,12),('BSE',None,6,5,12),('MCX','GOLD',14,5,28),('MCX','SILVER',14,5,28),('CRYPTO',None,23,7,46),('GLOBAL_COMMODITY','GOLD',22,7,44),('GLOBAL_COMMODITY','SILVER',22,7,44),('FOREX',None,22,7,44)]:
            for option in (False,True):
                c=instrument_contract(market,asset,is_option=option)
                self.assertEqual((c['parent_hours'],c['parent_minutes'],c['atr_length'],c['divisor']),(hours,hours*60,length,divisor))
                self.assertEqual(c['chart_type'],'Renko');self.assertEqual(c['session'],'Regular trading hours')
                self.assertEqual(c['atr_period_basis'],'PARENT_CANDLES');self.assertTrue(c['completed_parent_only'])
                self.assertEqual(c['option_divisor'],4 if option else 1)
    def test_forex_sizing_conversion_does_not_invent_an_execution_adapter(self):
        from sizing_policy import size_instrument
        i=dict(market='FOREX',underlying='fixture:EURUSD',product_type='FOREX')
        r=dict(symbol=i['underlying'],parent_hours=22,atr_length=7,native_box=.044,chart_session='Regular trading hours')
        self.assertEqual(size_instrument(i,r)['brick'],.001)
    def test_draft_cannot_override_parent_contract(self):
        from unittest.mock import patch
        from ui_bridge import configuration
        p=dict(account_id='owner',broker='DELTA_INDIA',underlying='ETHUSD',ai_market='CRYPTO',ai_execution_route='DIRECT',timeframe='1 minute',ai_parent_hours=6,ai_atr_length=5)
        with patch('ui_bridge.owner_broker',return_value='DELTA_INDIA'),patch('native_reference.resolve_reference',return_value=None):
            c=configuration(p,'owner')
        self.assertEqual((c['parent_hours'],c['atr_length'],c['parent_minutes']),(23,7,1380))
        self.assertEqual(c['chart_type'],'Renko');self.assertEqual(c['session'],'Regular trading hours')
