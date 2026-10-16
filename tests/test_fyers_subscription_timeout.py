import unittest
from unittest.mock import patch
from strategies.ema_crossover.broker import IndependentDataSocket
from fyers_apiv3.FyersWebsocket import data_ws

class SubscriptionTimeoutTests(unittest.TestCase):
    def test_private_decoder_lookup_is_bounded_without_global_request_patch(self):
        observed={}
        original=data_ws.SymbolConversion.symbol_to_hsmtoken
        def lookup(self,symbols):
            response=requests.post("https://api-t1.fyers.in/data/symbol-token",json={"symbols":symbols})
            return response
        def decoder(self,symbols):
            return SymbolConversion("fake","SymbolUpdate","").symbol_to_hsmtoken(symbols)
        def request(self,method,url,**kwargs):
            observed.update(kwargs)
            return {"lookup":"ok"}
        with patch.object(data_ws.SymbolConversion,"symbol_to_hsmtoken",lookup), patch.object(data_ws.FyersDataSocket,"_FyersDataSocket__symbol_conversion",decoder), patch("requests.Session.request",request), patch.object(data_ws.SymbolConversion,"__init__",lambda *a:None):
            sock=object.__new__(IndependentDataSocket)
            result=sock._FyersDataSocket__symbol_conversion(["BSE:SENSEX-INDEX"])
        self.assertEqual(result,{"lookup":"ok"})
        self.assertEqual(observed["timeout"],(5,10))
        self.assertIs(data_ws.SymbolConversion.symbol_to_hsmtoken,original)
