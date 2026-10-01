import time
import unittest
from unittest.mock import MagicMock, patch
from strategies.ema_crossover.broker import FyersBroker
from strategies.ema_crossover.valuation import amount


class ValuationTests(unittest.TestCase):
    def test_mcx_requires_explicit_valid_multiplier(self):
        for symbol in ('MCX:TESTCE','NSE:TESTCE','BSE:TESTCE'):
            for value in (None, 0, -1, float('nan'), float('inf')):
                with self.assertRaises(ValueError):
                    amount(dict(symbol=symbol, quantity_multiplier=value), 1, 402)

    def test_nifty_and_mcx_amounts(self):
        self.assertEqual(amount(dict(symbol='NSE:NIFTYCE',quantity_multiplier=1), 65, 100), 6500)
        self.assertEqual(amount(dict(symbol='MCX:TESTCE',quantity_multiplier=10),1,402),4020)

    def test_master_multiplier_and_identity_validation(self):
        b=FyersBroker('/tmp',None,None)
        expiry=int(time.time()+86400)
        row=['']*17
        for i,v in {0:'123',3:'1',4:'.05',8:str(expiry),9:'MCX:TESTCE',15:'8900',16:'CE'}.items():row[i]=v
        b.rows=lambda s:[row]
        record=dict(fyToken='123',tickSize=.05,symTicker='MCX:TESTCE',minLotSize=1,expiryDate=str(expiry),optType='CE',strikePrice=8900,qtyMultiplier=10)
        response=MagicMock();response.json.return_value={'MCX:TESTCE':record}
        with patch('strategies.ema_crossover.broker.requests.get',return_value=response) as get:
            self.assertEqual(b.contract('MCX:TESTCE')['quantity_multiplier'],10)
            self.assertEqual(b.contract('MCX:TESTCE')['lot_size'],1)
            self.assertEqual(get.call_count,1)
            record['strikePrice']=8950
            with self.assertRaisesRegex(ValueError,'masters disagree'):b.contract('MCX:TESTCE')

    def test_arbitrary_master_multiplier_is_used_without_symbol_mapping(self):
        self.assertEqual(amount(dict(symbol='MCX:UNKNOWNCE',quantity_multiplier=37.5),2,4),300)
